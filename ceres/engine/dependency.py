import re

# Regex patterns for static analysis of scripts
SET_VAR_PATTERN = re.compile(r'''mercury\.setVar\(\s*(['"])([\w]+)\1''')
GET_VAR_PATTERN = re.compile(r'''mercury\.getVar\(\s*(['"])([\w]+)\1''')
# Detect dynamic setVar/getVar calls (variable name is not a string literal)
DYNAMIC_SET_PATTERN = re.compile(r'''mercury\.setVar\(\s*(?!['"])''')
DYNAMIC_GET_PATTERN = re.compile(r'''mercury\.getVar\(\s*(?!['"])''')
PLACEHOLDER_PATTERN = re.compile(r'\{\{(\w+)\}\}')


def analyze_case(testcase, env_var_names=None):
    """Analyze a testcase to extract produced and consumed variables.

    Returns (produces: set, consumes: set, is_dynamic: bool)
    - produces: variable names set via mercury.setVar() in scripts
    - consumes: variable names referenced via {{var}} or mercury.getVar()
    - is_dynamic: True if scripts use computed variable names
    """
    env_var_names = env_var_names or set()
    produces = set()
    consumes = set()
    is_dynamic = False

    # Analyze scripts for setVar/getVar
    for script in (testcase.pre_request_script or '', testcase.post_request_script or ''):
        if not script:
            continue
        for m in SET_VAR_PATTERN.finditer(script):
            produces.add(m.group(2))
        for m in GET_VAR_PATTERN.finditer(script):
            consumes.add(m.group(2))
        if DYNAMIC_SET_PATTERN.search(script) and not SET_VAR_PATTERN.search(script):
            is_dynamic = True

    # Analyze URL, headers, params, body for {{var}} placeholders
    texts = []
    if testcase.url:
        texts.append(testcase.url)

    if isinstance(testcase.headers, list):
        for h in testcase.headers:
            if h.get('enabled', True):
                texts.append(str(h.get('value', '')))
    elif isinstance(testcase.headers, dict):
        texts.extend(str(v) for v in testcase.headers.values())

    if isinstance(testcase.params, list):
        for p in testcase.params:
            if p.get('enabled', True):
                texts.append(str(p.get('value', '')))
    elif isinstance(testcase.params, dict):
        texts.extend(str(v) for v in testcase.params.values())

    if testcase.body:
        if isinstance(testcase.body, str):
            texts.append(testcase.body)
        elif isinstance(testcase.body, dict):
            texts.append(str(testcase.body))

    for text in texts:
        for m in PLACEHOLDER_PATTERN.finditer(text):
            consumes.add(m.group(1))

    return produces, consumes, is_dynamic


def build_layers(testcases, env_var_names=None):
    """Build topological execution layers from testcases.

    Cases in the same layer have no dependencies on each other and can run in parallel.
    Layers are executed sequentially.

    Returns list of layers, where each layer is a list of testcases.
    """
    if not testcases:
        return []

    env_var_names = set(env_var_names or [])
    n = len(testcases)

    # Step 1: Analyze each case
    analysis = []
    all_produced = set()
    for tc in testcases:
        produces, consumes, is_dynamic = analyze_case(tc)
        analysis.append((produces, consumes, is_dynamic))
        all_produced |= produces

    # Env-only vars: exist in env and no case ever setVar's them — safe to ignore
    env_only_vars = env_var_names - all_produced

    # Step 2: Build dependency edges
    # deps[i] = set of indices that case i depends on
    deps = [set() for _ in range(n)]

    # For each variable, track the latest producer index (by sort order)
    var_latest_producer = {}  # var_name -> index of latest producer

    for i in range(n):
        produces_i, consumes_i, is_dynamic_i = analysis[i]
        # Remove env-only vars from consumes (no case overwrites them)
        consumes_i = consumes_i - env_only_vars

        # Dynamic cases conservatively depend on all prior cases
        if is_dynamic_i:
            for j in range(i):
                deps[i].add(j)
        else:
            # Find dependencies based on consumed variables
            for var in consumes_i:
                if var in var_latest_producer:
                    deps[i].add(var_latest_producer[var])

        # Two cases producing the same variable must be serialized
        for var in produces_i:
            if var in var_latest_producer:
                deps[i].add(var_latest_producer[var])
            var_latest_producer[var] = i

    # Step 3: Topological layering (modified Kahn's algorithm)
    layer_of = [0] * n
    for i in range(n):
        if deps[i]:
            layer_of[i] = max(layer_of[j] for j in deps[i]) + 1

    # Group by layer, preserving original order within each layer
    max_layer = max(layer_of) if layer_of else 0
    layers = []
    for l in range(max_layer + 1):
        layer = [testcases[i] for i in range(n) if layer_of[i] == l]
        if layer:
            layers.append(layer)

    return layers
