from contextlib import nullcontext, redirect_stderr, redirect_stdout
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from backup_pilot import cli
from backup_pilot.errors import BackupPilotError
from backup_pilot.scheduler import Scheduler, validate_calendar
from helpers import ProfileCase


class ScheduleCLITest(ProfileCase):
    def test_preview_does_not_contact_systemd_manager(self):
        self.write_profile(schedule='Mon..Fri *-*-* 22:30:00')
        with patch.object(cli, 'DEFAULT_PROFILES_DIR', self.profiles), \
                patch('backup_pilot.scheduler.subprocess.run',
                      return_value=subprocess.CompletedProcess([], 0)) as analyze, \
                patch.object(Scheduler, '_systemctl', side_effect=AssertionError('called systemctl')), \
                redirect_stdout(io.StringIO()) as output:
            code = cli.main(['schedule', 'demo', 'enable', '--dry-run'])
        self.assertEqual(code, 0)
        self.assertIn('22:30:00', output.getvalue())
        self.assertTrue(analyze.call_args.args[0][0].endswith('/systemd-analyze'))
        self.assertFalse(self.destination.exists())

    def test_disable_preview_works_when_profile_has_been_removed(self):
        self.config.unlink()
        with patch.object(cli, 'DEFAULT_PROFILES_DIR', self.profiles), \
                patch.object(Scheduler, '_systemctl', side_effect=AssertionError('called systemctl')), \
                redirect_stdout(io.StringIO()) as output:
            self.assertEqual(cli.main(['schedule', 'demo', 'disable', '--dry-run']), 0)
        self.assertIn('backup-pilot@demo.timer', output.getvalue())

    def test_alternate_profile_directory_cannot_configure_system_timer(self):
        with patch.object(Scheduler, 'apply', side_effect=AssertionError('changed system timer')), \
                redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(['--profiles-dir', str(self.profiles), 'schedule', 'demo', 'enable']), 2)

    def test_calendar_cannot_add_unit_directives(self):
        with patch('backup_pilot.scheduler.subprocess.run') as analyze:
            for value in ('daily\nPersistent=yes', 'daily\\', '%i', '\t'):
                with self.subTest(value=value), self.assertRaises(BackupPilotError) as error:
                    validate_calendar(value)
                self.assertEqual(error.exception.code, 2)
            analyze.assert_not_called()


@unittest.skipUnless(hasattr(os, 'fchmod'), 'systemd configuration requires POSIX')
class ScheduleTransactionTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.scheduler = Scheduler('test-profile_1', Path(temporary.name).resolve())
        self.active = False
        self.enabled = False
        self.fail_start = False
        self.fail_disable = False

    def systemctl(self, *args):
        if args[0] == 'show':
            unit = args[-1]
            if unit == self.scheduler.service:
                output = 'LoadState=loaded\n'
            else:
                output = (f'LoadState=loaded\nActiveState={"active" if self.active else "inactive"}\n'
                          f'UnitFileState={"enabled" if self.enabled else "disabled"}\n')
            return subprocess.CompletedProcess(args, 0, stdout=output)
        operation = args[0]
        if operation == 'stop':
            self.active = False
        elif operation == 'start':
            if self.fail_start:
                self.fail_start = False
                raise BackupPilotError('Systemd start failed', 4)
            self.active = True
        elif operation == 'enable':
            self.enabled = True
        elif operation == 'disable':
            self.enabled = False
            if self.fail_disable:
                self.fail_disable = False
                raise BackupPilotError('Systemd disable failed after unlinking', 4)

    def apply(self, calendar):
        with patch.object(self.scheduler, '_lock', return_value=nullcontext()), \
                patch.object(self.scheduler, '_systemctl', side_effect=self.systemctl), \
                patch('backup_pilot.scheduler.validate_calendar', side_effect=lambda value: value):
            self.scheduler.apply(calendar)

    def test_update_failure_restores_old_calendar_and_running_timer(self):
        self.apply('daily')
        original = self.scheduler.drop_in.read_bytes()
        self.fail_start = True
        with self.assertRaisesRegex(BackupPilotError, 'Прежнее расписание восстановлено') as error:
            self.apply('weekly')
        self.assertEqual(error.exception.code, 4)
        self.assertEqual(self.scheduler.drop_in.read_bytes(), original)
        self.assertTrue(self.active)
        self.assertTrue(self.enabled)

    def test_first_enable_failure_removes_new_drop_in_and_enablement(self):
        self.fail_start = True
        with self.assertRaises(BackupPilotError):
            self.apply('daily')
        self.assertFalse(self.scheduler.drop_in.parent.exists())
        self.assertFalse(self.active)
        self.assertFalse(self.enabled)

    def test_disable_failure_restores_enablement_and_leaves_configuration(self):
        self.apply('daily')
        original = self.scheduler.drop_in.read_bytes()
        self.fail_disable = True
        with self.assertRaisesRegex(BackupPilotError, 'Прежнее расписание восстановлено'):
            self.apply(None)
        self.assertTrue(self.active)
        self.assertTrue(self.enabled)
        self.apply(None)
        self.assertFalse(self.active)
        self.assertFalse(self.enabled)
        self.assertEqual(self.scheduler.drop_in.read_bytes(), original)
