import contextlib
import io
import json
import os
from pathlib import Path
import shutil
from unittest.mock import patch

from backup_pilot.backup import execute_backup, list_snapshots, plan_backup
from backup_pilot.cli import main
from backup_pilot.errors import BackupPilotError
from backup_pilot.profiles import load_profile
from helpers import ProfileCase


class BackupTest(ProfileCase):
    def setUp(self):
        super().setUp()
        (self.source / 'a.txt').write_text('учебный файл', encoding='utf-8')
        (self.source / 'z.bin').write_bytes(bytes(range(256)))
        (self.source / 'empty').mkdir()
        (self.source / 'sub').mkdir()
        (self.source / 'sub' / 'nested.tmp').write_bytes(b'excluded')
        (self.source / 'notes.tmp').write_bytes(b'excluded')
        (self.source / 'cache').mkdir()
        (self.source / 'cache' / 'item.txt').write_bytes(b'excluded')
        self.profile = load_profile(self.config)

    def test_copy_exclusions_empty_dirs_and_multiple_snapshots(self):
        before = {p.relative_to(self.source): p.read_bytes() for p in self.source.rglob('*') if p.is_file()}
        self.assertEqual(list_snapshots(self.profile), [])
        first = execute_backup(plan_backup(self.profile))
        second = execute_backup(plan_backup(self.profile))
        self.assertEqual(list_snapshots(self.profile), sorted([first, second]))
        self.assertNotEqual(first, second)
        for snapshot in (first, second):
            self.assertEqual((snapshot / 'data' / 'a.txt').read_bytes(), (self.source / 'a.txt').read_bytes())
            self.assertEqual((snapshot / 'data' / 'z.bin').read_bytes(), bytes(range(256)))
            self.assertTrue((snapshot / 'data' / 'empty').is_dir())
            for relative in ('notes.tmp', 'sub/nested.tmp', 'cache/item.txt'):
                self.assertFalse((snapshot / 'data' / relative).exists())
            self.assertFalse((snapshot / 'manifest.json').exists())
        self.assertEqual(before, {p.relative_to(self.source): p.read_bytes()
                                  for p in self.source.rglob('*') if p.is_file()})

    def test_failure_keeps_previous_copy_and_hides_partial(self):
        first = execute_backup(plan_backup(self.profile))
        with patch('backup_pilot.backup.shutil.copy2', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                execute_backup(plan_backup(self.profile))
        self.assertEqual(list_snapshots(self.profile), [first])
        partials = list(first.parent.glob('.partial-*'))
        self.assertEqual(len(partials), 1)
        self.assertFalse((partials[0] / 'snapshot.json').exists())
        self.assertEqual((first / 'data' / 'z.bin').read_bytes(), bytes(range(256)))
        self.assertEqual((self.source / 'z.bin').read_bytes(), bytes(range(256)))

    def test_source_changed_after_plan_or_during_copy(self):
        plan = plan_backup(self.profile)
        (self.source / 'a.txt').write_text('changed', encoding='utf-8')
        with self.assertRaises(BackupPilotError):
            execute_backup(plan)
        real_copy = shutil.copy2

        def changing_copy(source, destination, **kwargs):
            result = real_copy(source, destination, **kwargs)
            Path(source).write_bytes(b'changed during copy')
            return result

        with patch('backup_pilot.backup.shutil.copy2', side_effect=changing_copy):
            with self.assertRaises(BackupPilotError):
                execute_backup(plan_backup(self.profile))
        self.assertEqual(list_snapshots(self.profile), [])

    def test_bad_metadata_is_not_completed(self):
        snapshot = execute_backup(plan_backup(self.profile))
        metadata = json.loads((snapshot / 'snapshot.json').read_text())
        bad_values = [[], {}, dict(metadata, profile='other'), dict(metadata, schema_version=True),
                      dict(metadata, snapshot_id='../escape'), dict(metadata, completed_at='invalid'),
                      dict(metadata, completed_at='2026-11-04T12:00:00')]
        for value in bad_values:
            with self.subTest(value=value):
                (snapshot / 'snapshot.json').write_text(json.dumps(value))
                self.assertEqual(list_snapshots(self.profile), [])

    def test_symlink_is_rejected_or_explicitly_excluded(self):
        target = self.source / 'link'
        try:
            target.symlink_to(self.source / 'a.txt')
        except (OSError, NotImplementedError):
            self.skipTest('creating symlinks is unavailable for this user')
        with self.assertRaises(BackupPilotError):
            plan_backup(self.profile)
        self.write_profile(exclude=['link'])
        plan_backup(load_profile(self.config))

    def test_cli_run_and_snapshots(self):
        prefix = ['--profiles-dir', str(self.profiles)]
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(prefix + ['run', 'demo']), 0)
        self.assertIn('BP-09', output.getvalue())
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(prefix + ['snapshots', 'demo']), 0)
        self.assertEqual(output.getvalue().strip(), list_snapshots(self.profile)[0].name)

    def test_special_file_rejected(self):
        if not hasattr(os, 'mkfifo'):
            self.skipTest('FIFO test requires Unix')
        os.mkfifo(self.source / 'pipe')
        with self.assertRaises(BackupPilotError):
            plan_backup(self.profile)
