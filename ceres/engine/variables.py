import re
import json
import copy
import threading


class VariableContext:
    """Manages environment variables and runtime variables for test execution.

    Merges env vars with runtime vars. Supports {{var}} placeholder resolution
    in strings, dicts, and lists. Tracks extracted variables for chaining
    between cases. Thread-safe for concurrent execution.
    """

    PLACEHOLDER_PATTERN = re.compile(r'\{\{(\w+)\}\}')

    def __init__(self, env_variables=None):
        self.env_variables = dict(env_variables or {})
        self.runtime_variables = {}
        self._lock = threading.Lock()

    def get_var(self, name):
        with self._lock:
            if name in self.runtime_variables:
                return self.runtime_variables[name]
        return self.env_variables.get(name)

    def set_var(self, name, value):
        with self._lock:
            self.runtime_variables[name] = value

    def get_env_var(self, name):
        return self.env_variables.get(name)

    def get_all_variables(self):
        with self._lock:
            merged = {}
            merged.update(self.env_variables)
            merged.update(self.runtime_variables)
            return merged

    def resolve(self, text):
        if not isinstance(text, str):
            return text

        all_vars = self.get_all_variables()

        def replacer(match):
            var_name = match.group(1)
            if var_name in all_vars:
                return str(all_vars[var_name])
            return match.group(0)

        return self.PLACEHOLDER_PATTERN.sub(replacer, text)

    def resolve_dict(self, d):
        if not isinstance(d, dict):
            return d
        result = {}
        for key, value in d.items():
            resolved_key = self.resolve(key)
            if isinstance(value, str):
                result[resolved_key] = self.resolve(value)
            elif isinstance(value, dict):
                result[resolved_key] = self.resolve_dict(value)
            elif isinstance(value, list):
                result[resolved_key] = self.resolve_list(value)
            else:
                result[resolved_key] = value
        return result

    def resolve_list(self, lst):
        if not isinstance(lst, list):
            return lst
        result = []
        for item in lst:
            if isinstance(item, str):
                result.append(self.resolve(item))
            elif isinstance(item, dict):
                result.append(self.resolve_dict(item))
            elif isinstance(item, list):
                result.append(self.resolve_list(item))
            else:
                result.append(item)
        return result

    def resolve_json(self, obj):
        if isinstance(obj, str):
            return self.resolve(obj)
        elif isinstance(obj, dict):
            return self.resolve_dict(obj)
        elif isinstance(obj, list):
            return self.resolve_list(obj)
        return obj

    def get_extracted_variables(self):
        with self._lock:
            return dict(self.runtime_variables)
