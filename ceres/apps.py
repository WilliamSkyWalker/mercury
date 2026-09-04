import os
import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)


class CeresConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ceres'

    def ready(self):
        # Mark stale running executions as interrupted (only for server processes)
        is_server = os.environ.get('RUN_MAIN') == 'true' or os.environ.get('MERCURY_SCHEDULER') == 'true'
        if is_server:
            try:
                from ceres.models import ExecutionRecord
                count = ExecutionRecord.all_objects.filter(status='running').update(status='interrupted')
                if count:
                    logger.info(f"Marked {count} stale running execution(s) as interrupted")
            except Exception:
                pass

        # Sync the Mercury-managed crontab block at boot time. Linux cron
        # itself is the timing engine now; we just need to make sure the
        # block reflects the current ScheduledTask rows after every restart.
        # Skipped for the runserver autoreload parent (RUN_MAIN unset) so we
        # don't double-write on every code change in dev.
        is_reloader_child = os.environ.get('RUN_MAIN') == 'true'
        is_production_server = os.environ.get('MERCURY_SCHEDULER') == 'true'
        if is_reloader_child or is_production_server:
            import threading
            def _deferred_sync():
                import time
                time.sleep(3)
                try:
                    from ceres.scheduler import sync_crontab
                    sync_crontab()
                except Exception as e:
                    logger.error(f"Crontab sync failed: {e}", exc_info=True)
            threading.Thread(target=_deferred_sync, daemon=True).start()
