"""Tests for the crontab-backed scheduler and the cron-only serializer."""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from ceres import scheduler


def _task(id_, name, cron, plan_id=42, active=True):
    """Build a ScheduledTask-shaped namespace good enough for the renderer."""
    return SimpleNamespace(
        id=id_,
        name=name,
        cron_expression=cron,
        trigger_type='cron',
        is_active=active,
        testplan_id=plan_id,
        testplan=SimpleNamespace(id=plan_id, name=f'plan-{plan_id}'),
    )


class ValidateCronExpressionTests(SimpleTestCase):

    def test_accepts_five_field_expression(self):
        self.assertEqual(scheduler._validate_cron_expression('*/15 * * * *'), '*/15 * * * *')

    def test_strips_whitespace(self):
        self.assertEqual(scheduler._validate_cron_expression('  0 9 * * 1  '), '0 9 * * 1')

    def test_rejects_empty(self):
        with self.assertRaises(ValueError):
            scheduler._validate_cron_expression('')

    def test_rejects_wrong_field_count(self):
        with self.assertRaises(ValueError):
            scheduler._validate_cron_expression('* * * *')
        with self.assertRaises(ValueError):
            scheduler._validate_cron_expression('* * * * * *')


class BuildCronLineTests(SimpleTestCase):

    def test_renders_with_repo_path_and_log_path(self):
        task = _task(7, 'nb-prod hourly', '0 * * * *')
        line = scheduler._build_cron_line(task)
        self.assertTrue(line.startswith('0 * * * * '))
        self.assertIn(f'cd {scheduler.REPO_DIR}', line)
        self.assertIn('python3 manage.py run_scheduled_task 7', line)
        self.assertIn(f'>> {scheduler.LOG_PATH} 2>&1', line)


class SpliceBlockTests(SimpleTestCase):

    def test_appends_block_when_markers_absent(self):
        existing = '15 * * * * curl /api/morningbrew\n'
        block = f'{scheduler.BEGIN_MARKER}\n# [1] x\n0 * * * * a\n{scheduler.END_MARKER}'
        out = scheduler._splice_block(existing, block)
        self.assertIn('curl /api/morningbrew', out)
        self.assertIn('# [1] x', out)
        self.assertTrue(out.endswith('\n'))
        self.assertEqual(out.count(scheduler.BEGIN_MARKER), 1)
        self.assertEqual(out.count(scheduler.END_MARKER), 1)

    def test_replaces_existing_block_preserving_surroundings(self):
        existing = (
            '15 * * * * curl /api/morningbrew\n'
            f'{scheduler.BEGIN_MARKER}\n'
            '# [99] stale\n'
            '0 * * * * stale\n'
            f'{scheduler.END_MARKER}\n'
            '0 9 * * * curl /api/something_else\n'
        )
        block = f'{scheduler.BEGIN_MARKER}\n# [1] fresh\n0 * * * * fresh\n{scheduler.END_MARKER}'
        out = scheduler._splice_block(existing, block)
        self.assertIn('curl /api/morningbrew', out)
        self.assertIn('curl /api/something_else', out)
        self.assertIn('# [1] fresh', out)
        self.assertNotIn('# [99] stale', out)
        self.assertNotIn('0 * * * * stale', out)

    def test_idempotent_when_block_unchanged(self):
        block = f'{scheduler.BEGIN_MARKER}\n# [1] x\n0 * * * * a\n{scheduler.END_MARKER}'
        existing = 'foo\n' + block + '\nbar\n'
        once = scheduler._splice_block(existing, block)
        twice = scheduler._splice_block(once, block)
        self.assertEqual(once, twice)


class RenderBlockTests(SimpleTestCase):

    def test_skips_tasks_with_invalid_cron(self):
        ok = _task(1, 'ok', '*/15 * * * *')
        bad = _task(2, 'bad', 'not a cron')

        class _QS(list):
            def select_related(self, *_a, **_kw):
                return self

            def order_by(self, *_a, **_kw):
                return self

            def filter(self, *_a, **_kw):
                return self

        qs = _QS([ok, bad])
        with mock.patch('ceres.scheduler.ScheduledTask', create=True) as fake_model, \
                mock.patch.dict('sys.modules'):
            fake_model.objects.filter.return_value = qs
            # _render_block does its own import, so patch on the module path
            with mock.patch.object(scheduler, '_render_block', wraps=scheduler._render_block):
                # Re-import path: easier to just monkeypatch the helper that
                # accesses the model. Stub the import inline.
                with mock.patch('ceres.models.ScheduledTask') as model:
                    model.objects.filter.return_value = qs
                    out = scheduler._render_block()
        self.assertIn('# [1] ok', out)
        self.assertNotIn('# [2] bad', out)
        self.assertIn(scheduler.BEGIN_MARKER, out)
        self.assertIn(scheduler.END_MARKER, out)


class SyncCrontabTests(SimpleTestCase):

    def _patch_render(self, block):
        return mock.patch.object(scheduler, '_render_block', return_value=block)

    def test_writes_when_block_differs(self):
        block = f'{scheduler.BEGIN_MARKER}\n# [1] x\n0 * * * * a\n{scheduler.END_MARKER}'
        existing = 'other-line\n'
        with self._patch_render(block), \
                mock.patch.object(scheduler, '_read_crontab', return_value=existing) as read, \
                mock.patch.object(scheduler, '_write_crontab') as write:
            count = scheduler.sync_crontab()
        read.assert_called_once()
        write.assert_called_once()
        written = write.call_args[0][0]
        self.assertIn('other-line', written)
        self.assertIn('0 * * * * a', written)
        self.assertEqual(count, 1)

    def test_skips_write_when_already_in_sync(self):
        block = f'{scheduler.BEGIN_MARKER}\n# [1] x\n0 * * * * a\n{scheduler.END_MARKER}'
        existing = 'other-line\n' + block + '\n'
        with self._patch_render(block), \
                mock.patch.object(scheduler, '_read_crontab', return_value=existing), \
                mock.patch.object(scheduler, '_write_crontab') as write:
            count = scheduler.sync_crontab()
        write.assert_not_called()
        self.assertEqual(count, 1)

    def test_returns_minus_one_when_crontab_binary_missing(self):
        with mock.patch.object(scheduler, '_read_crontab', side_effect=FileNotFoundError()):
            self.assertEqual(scheduler.sync_crontab(), -1)


class ReadCrontabSubprocessTests(SimpleTestCase):

    def test_treats_no_crontab_for_user_as_empty(self):
        proc = mock.Mock(returncode=1, stdout='', stderr='no crontab for ubuntu\n')
        with mock.patch('subprocess.run', return_value=proc):
            self.assertEqual(scheduler._read_crontab(), '')

    def test_raises_on_other_error(self):
        proc = mock.Mock(returncode=2, stdout='', stderr='permission denied\n')
        with mock.patch('subprocess.run', return_value=proc):
            with self.assertRaises(RuntimeError):
                scheduler._read_crontab()


class ScheduledTaskSerializerTests(SimpleTestCase):
    """Validate cron-only enforcement without touching the database.

    ``ScheduledTaskSerializer`` has a FK to Testplan, which hits the DB on
    ``is_valid()`` even when validation should short-circuit. We exercise the
    custom ``validate`` and ``validate_cron_expression`` hooks directly so the
    tests stay hermetic.
    """

    def _serializer(self):
        from ceres.serializers import ScheduledTaskSerializer
        s = ScheduledTaskSerializer()
        s.initial_data = {}
        return s

    def test_validate_rejects_interval_trigger(self):
        from rest_framework.exceptions import ValidationError
        s = self._serializer()
        s.initial_data = {'trigger_type': 'interval'}
        with self.assertRaises(ValidationError) as ctx:
            s.validate({'cron_expression': '0 * * * *'})
        self.assertIn('trigger_type', ctx.exception.detail)

    def test_validate_cron_expression_rejects_garbage(self):
        from rest_framework.exceptions import ValidationError
        s = self._serializer()
        with self.assertRaises(ValidationError):
            s.validate_cron_expression('not a cron')

    def test_validate_cron_expression_accepts_five_fields(self):
        s = self._serializer()
        self.assertEqual(s.validate_cron_expression('*/15 * * * *'), '*/15 * * * *')

    def test_validate_requires_cron_expression_on_create(self):
        from rest_framework.exceptions import ValidationError
        s = self._serializer()
        s.initial_data = {'trigger_type': 'cron'}
        with self.assertRaises(ValidationError) as ctx:
            s.validate({})
        self.assertIn('cron_expression', ctx.exception.detail)
