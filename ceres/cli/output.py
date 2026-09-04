"""Output formatters for the `ceres` management command."""
import json
import sys
from datetime import datetime


def _stringify(value, max_len=60):
    if value is None:
        return ''
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d %H:%M')
    if isinstance(value, (dict, list)):
        s = json.dumps(value, ensure_ascii=False, default=str)
    else:
        s = str(value)
    if max_len and len(s) > max_len:
        return s[: max_len - 1] + '…'
    return s


def print_table(rows, columns, stream=None):
    """Render a list of dicts as a column-aligned table.

    columns: list of (header, key, max_width) or (header, key).
    """
    stream = stream or sys.stdout
    if not rows:
        stream.write('(no rows)\n')
        return

    norm = []
    for col in columns:
        if len(col) == 2:
            norm.append((col[0], col[1], 60))
        else:
            norm.append(col)

    widths = []
    for header, key, max_w in norm:
        w = len(header)
        for r in rows:
            w = max(w, len(_stringify(r.get(key), max_w)))
        widths.append(min(w, max_w))

    line = '  '.join(h.ljust(w) for (h, _, _), w in zip(norm, widths))
    stream.write(line + '\n')
    stream.write('  '.join('-' * w for w in widths) + '\n')
    for r in rows:
        stream.write('  '.join(
            _stringify(r.get(k), max_w).ljust(w)
            for ((_, k, max_w), w) in zip(norm, widths)
        ) + '\n')


def print_json(data, stream=None):
    stream = stream or sys.stdout
    json.dump(data, stream, ensure_ascii=False, indent=2, default=str)
    stream.write('\n')


def emit(data, output, table_columns, stream=None):
    """Render `data` (single dict or list of dicts) as table or JSON.

    table_columns: list of (header, key[, max_width]) used in table mode.
    """
    if output == 'json':
        print_json(data, stream)
        return
    rows = data if isinstance(data, list) else [data]
    print_table(rows, table_columns, stream)
