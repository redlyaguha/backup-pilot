import contextlib
import io
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from backup_pilot.cli import main
from backup_pilot.errors import BackupPilotError
from backup_pilot.profiles import list_profiles, load_named_profile, load_profile
from helpers import ProfileCase


class ProfilesTest(ProfileCase):
    def profile_commands(self):
        return [
            ['profiles', 'validate', '--config', str(self.config)],
            ['--profiles-dir', str(self.profiles), 'profiles', 'list'],
            ['--profiles-dir', str(self.profiles), 'run', 'demo'],
            ['--profiles-dir', str(self.profiles), 'run', 'demo', '--dry-run'],
        ]

    def assert_non_regular_profile_rejected(self):
        with patch.object(Path, 'open', side_effect=AssertionError('opened a special profile')):
            with self.assertRaises(BackupPilotError) as error:
                load_profile(self.config)
        self.assertEqual(error.exception.code, 2)
        launcher = Path(__file__).resolve().parents[1] / 'backup-pilot'
        for command in self.profile_commands():
            with self.subTest(command=command):
                result = subprocess.run([sys.executable, '-B', str(launcher), *command],
                                        capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertTrue(result.stderr.strip())
                self.assertNotIn('Traceback', result.stderr)
                self.assertEqual(result.stdout, '')
        self.assertFalse(self.destination.exists())

    def test_directory_profile_is_configuration_error(self):
        self.config.unlink()
        self.config.mkdir()
        self.assert_non_regular_profile_rejected()

    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'FIFO test requires Unix')
    def test_fifo_profile_is_configuration_error_without_blocking(self):
        self.config.unlink()
        os.mkfifo(self.config)
        self.assert_non_regular_profile_rejected()

    def test_load_and_list(self):
        profile = load_profile(self.config)
        self.assertEqual(profile.source, self.source)
        self.assertEqual(profile.exclude, ('*.tmp', 'cache/**'))
        self.assertEqual(list_profiles(self.profiles), [profile])
        self.assertEqual(load_named_profile(self.profiles, 'demo'), profile)
        self.assertFalse(self.destination.exists())

    def test_bad_types_and_values(self):
        for changes in (dict(name='../escape'), dict(name=3), dict(keep_last=True),
                        dict(keep_last=0), dict(keep_last=2.5), dict(source=5),
                        dict(source='relative'), dict(schedule=''), dict(schedule=7),
                        dict(exclude='*.tmp'), dict(exclude=['../escape']),
                        dict(exclude=['/absolute']), dict(exclude=[4]),
                        dict(exclude=['cache\\*']), dict(destination=str(self.source))):
            with self.subTest(changes=changes):
                self.write_profile(**changes)
                with self.assertRaises(BackupPilotError):
                    load_profile(self.config)

    def test_nested_paths(self):
        for source, destination in ((self.source, self.source / 'backup'),
                                    (self.source, self.root),
                                    (self.source / '..' / 'source', self.destination)):
            with self.subTest(source=source, destination=destination):
                self.write_profile(source=str(source), destination=str(destination))
                with self.assertRaises(BackupPilotError):
                    load_profile(self.config)

    def test_missing_source_and_non_directory(self):
        for source in (self.root / 'absent', self.config):
            self.write_profile(source=str(source))
            with self.assertRaises(BackupPilotError):
                load_profile(self.config)

    def test_missing_malformed_and_incomplete_profile(self):
        for content in ('name = [', 'name = "demo"', 'name = "\u0000"'):
            self.config.write_text(content, encoding='utf-8')
            with self.assertRaises(BackupPilotError):
                load_profile(self.config)
        self.config.unlink()
        with self.assertRaises(BackupPilotError):
            load_profile(self.config)

    def test_name_match_and_traversal(self):
        self.write_profile(name='different')
        with self.assertRaises(BackupPilotError):
            load_named_profile(self.profiles, 'demo')
        with self.assertRaises(BackupPilotError):
            load_named_profile(self.profiles, '../demo')

    def test_cli_profile_and_access_error(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(['profiles', 'validate', '--config', str(self.config)]), 0)
        self.assertIn('demo: OK', output.getvalue())
        with patch('backup_pilot.cli.load_profile', side_effect=PermissionError('denied')):
            with contextlib.redirect_stderr(io.StringIO()) as output:
                self.assertEqual(main(['profiles', 'validate', '--config', str(self.config)]), 3)
            self.assertNotIn('Traceback', output.getvalue())
