"""Ceres CLI — manage testcases and testplans from the shell.

Examples:
    python manage.py ceres case list --project sample
    python manage.py ceres case get 219
    python manage.py ceres case run 219 --env Sample_prod
    python manage.py ceres plan list
    python manage.py ceres plan run 3 --env Sample_prod
    python manage.py ceres plan add-cases 3 480 481 482
    python manage.py ceres plan sync 3 --all

Every subcommand supports `--output table` (default) or `--output json`.
"""
import argparse

from django.core.management.base import BaseCommand, CommandError

from ceres.cli import case as case_cli
from ceres.cli import plan as plan_cli


class Command(BaseCommand):
    help = 'Ceres CLI — CRUD and run testcases and testplans.'

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(dest='resource', metavar='<resource>', required=True)

        case_parser = subparsers.add_parser('case', help='Manage testcases')
        case_cli.register(case_parser)

        plan_parser = subparsers.add_parser('plan', help='Manage testplans')
        plan_cli.register(plan_parser)

    def handle(self, *args, **options):
        handler_fn = options.get('handler')
        if handler_fn is None:
            raise CommandError(f"No action given. Run with --help for options.")
        ns = argparse.Namespace(**options)
        handler_fn(ns)
