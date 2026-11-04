import contextlib
import io
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from backup_pilot.backup import BackupPlan, FileEntry, execute_backup, list_snapshots, plan_backup
from backup_pilot.cli import main
from backup_pilot.errors import BackupPilotError
from backup_pilot.profiles import load_profile
from helpers import ProfileCase


class ErrorsTest(ProfileCase):
    def test_expected_service_errors_use_shared_codes(self):
        failures = [(PermissionError('denied'), 3), (FileNotFoundError('missing'), 4),
                    (OSError('disk full'), 4), (BackupPilotError('invalid'), 2),
                    (BackupPilotError('integrity failure', 5), 5), (BackupPilotError('busy', 6), 6),
                    (subprocess.CalledProcessError(9, ['systemctl'], stderr='private output'), 4),
                    (subprocess.TimeoutExpired(['systemctl'], 5), 4)]
        for error, code in failures:
            with self.subTest(error=type(error), code=code):
                with patch('backup_pilot.cli.execute_backup', side_effect=error):
                    with contextlib.redirect_stderr(io.StringIO()) as output:
                        actual = main(['--profiles-dir', str(self.profiles), 'run', 'demo'])
                self.assertEqual(actual, code)
                self.assertNotIn('Traceback', output.getvalue())
                self.assertNotIn('private output', output.getvalue())
                self.assertFalse(self.destination.exists())

    def test_profile_error_is_code_two_without_traceback(self):
        with contextlib.redirect_stderr(io.StringIO()) as output:
            self.assertEqual(main(['--profiles-dir', str(self.profiles), 'run', '../escape']), 2)
        self.assertNotIn('Traceback', output.getvalue())
        self.assertFalse(self.destination.exists())

    def test_subprocess_entrypoints_and_parser_failures(self):
        repo = Path(__file__).resolve().parents[1]
        for command in ([sys.executable, '-B', str(repo / 'backup-pilot')],
                        [sys.executable, '-B', '-m', 'backup_pilot']):
            for arguments, code in ((['--help'], 0), (['--version'], 0), (['unknown'], 2),
                                    (['profiles', 'validate'], 2)):
                with self.subTest(command=command, arguments=arguments):
                    result = subprocess.run(command + arguments, capture_output=True, cwd=repo)
                    self.assertEqual(result.returncode, code, result.stderr)
                    self.assertNotIn(b'Traceback', result.stderr)

    def test_relative_plan_cannot_escape_destination(self):
        profile = load_profile(self.config)
        for relative in (Path('../escape'), self.root / 'escape'):
            with self.subTest(relative=relative):
                plan = BackupPlan(profile, (), (FileEntry(relative, ()),))
                with self.assertRaises(BackupPilotError):
                    execute_backup(plan)
        self.assertFalse(self.destination.exists())

    def test_real_unix_read_permissions(self):
        if not hasattr(os, 'geteuid') or os.geteuid() == 0:
            self.skipTest('requires an unprivileged Unix user')
        restricted = self.source / 'restricted.txt'
        restricted.write_bytes(b'private')
        restricted.chmod(0)
        self.addCleanup(restricted.chmod, 0o600)
        with contextlib.redirect_stderr(io.StringIO()) as output:
            code = main(['--profiles-dir', str(self.profiles), 'run', 'demo', '--dry-run'])
        self.assertEqual(code, 3)
        self.assertNotIn('Traceback', output.getvalue())
        self.assertFalse(self.destination.exists())

    def test_symlink_ancestors_and_destination_are_rejected(self):
        link = self.root / 'alias'
        try:
            link.symlink_to(self.source, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest('creating symlinks is unavailable for this user')
        for fields in (dict(source=str(link)), dict(destination=str(link / 'nested'))):
            self.write_profile(**fields)
            with self.assertRaises(BackupPilotError):
                load_profile(self.config)
        self.write_profile()
        profile = load_profile(self.config)
        self.destination.mkdir()
        (self.destination / 'demo').symlink_to(self.source, target_is_directory=True)
        with self.assertRaises(BackupPilotError):
            execute_backup(plan_backup(profile))

    def test_linked_snapshot_or_metadata_not_reported(self):
        snapshot = execute_backup(plan_backup(load_profile(self.config)))
        metadata = snapshot / 'snapshot.json'
        original = snapshot / 'original.json'
        metadata.rename(original)
        try:
            metadata.symlink_to(original)
        except (OSError, NotImplementedError):
            self.skipTest('creating symlinks is unavailable for this user')
        self.assertEqual(list_snapshots(load_profile(self.config)), [])

    def test_unreadable_directory_is_not_an_empty_plan(self):
        if not hasattr(os, 'geteuid') or os.geteuid() == 0:
            self.skipTest('requires an unprivileged Unix user')
        self.source.chmod(0)
        self.addCleanup(self.source.chmod, 0o700)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(['--profiles-dir', str(self.profiles), 'run', 'demo']), 3)
        self.assertFalse(self.destination.exists())
