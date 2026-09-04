"""Re-render the Mercury-managed crontab block from active ScheduledTask rows.

Used by ops to force a re-sync without restarting the server; the
ScheduledTask API also triggers this automatically on every write.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Sync active ScheduledTask rows into the managed crontab block.'

    def handle(self, *args, **options):
        from ceres.scheduler import sync_crontab

        count = sync_crontab()
        if count < 0:
            self.stdout.write(self.style.WARNING(
                'crontab binary unavailable (likely not on a Linux host); skipped.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Synced {count} active schedule(s) to crontab.'
            ))
