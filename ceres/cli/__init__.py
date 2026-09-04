import argparse


def common_parser():
    """Return a parent parser carrying shared flags like --output."""
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument('--output', '-o', choices=['table', 'json'], default='table',
                   help='Output format (default: table)')
    return p
