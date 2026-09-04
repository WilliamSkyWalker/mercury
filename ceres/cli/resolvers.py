"""Shared helpers: locate models by id or name, parse JSON input, model → dict."""
import json
import sys
from django.core.management.base import CommandError


def parse_json_arg(args):
    """Read JSON from --json-file / --json / --stdin, or return None."""
    if getattr(args, 'stdin', False):
        return json.load(sys.stdin)
    path = getattr(args, 'json_file', None)
    if path:
        with open(path, 'r') as f:
            return json.load(f)
    raw = getattr(args, 'json', None)
    if raw:
        return json.loads(raw)
    return None


def resolve_project(ident):
    from ceres.models import Project
    if ident is None:
        return None
    try:
        if str(ident).isdigit():
            return Project.objects.get(id=int(ident))
        return Project.objects.get(name=ident)
    except Project.DoesNotExist:
        raise CommandError(f"Project '{ident}' not found")


def resolve_env(ident, project=None):
    from ceres.models import Env
    if ident is None or ident == '':
        return None
    qs = Env.objects.filter()
    if project is not None:
        qs = qs.filter(project=project)
    try:
        if str(ident).isdigit():
            return qs.get(id=int(ident))
        return qs.get(name=ident)
    except Env.DoesNotExist:
        where = f" in project {project.name}" if project else ''
        raise CommandError(f"Env '{ident}'{where} not found")


def resolve_folder(ident, project=None):
    from ceres.models import Folder
    if ident is None or ident == '':
        return None
    qs = Folder.objects.filter()
    if project is not None:
        qs = qs.filter(project=project)
    try:
        if str(ident).isdigit():
            return Folder.objects.get(id=int(ident))
        return qs.get(name=ident)
    except Folder.DoesNotExist:
        where = f" in project {project.name}" if project else ''
        raise CommandError(f"Folder '{ident}'{where} not found")
    except Folder.MultipleObjectsReturned:
        raise CommandError(f"Multiple folders named '{ident}'; use folder id instead.")


def resolve_testcase(ident, project=None):
    from ceres.models import Testcase
    qs = Testcase.objects.filter()
    if project is not None:
        qs = qs.filter(project=project)
    try:
        if str(ident).isdigit():
            return Testcase.objects.get(id=int(ident))
        return qs.get(case_name=ident)
    except Testcase.DoesNotExist:
        raise CommandError(f"Testcase '{ident}' not found")
    except Testcase.MultipleObjectsReturned:
        raise CommandError(f"Multiple testcases named '{ident}'; use id instead.")


def resolve_testplan(ident, project=None):
    from ceres.models import Testplan
    qs = Testplan.objects.filter()
    if project is not None:
        qs = qs.filter(project=project)
    try:
        if str(ident).isdigit():
            return Testplan.objects.get(id=int(ident))
        return qs.get(name=ident)
    except Testplan.DoesNotExist:
        raise CommandError(f"Testplan '{ident}' not found")
    except Testplan.MultipleObjectsReturned:
        raise CommandError(f"Multiple testplans named '{ident}'; use id instead.")


def model_to_dict(instance, fields):
    """Shallow-serialize a model to a plain dict for output."""
    out = {}
    for f in fields:
        val = getattr(instance, f, None)
        out[f] = val
    return out
