import contextlib
import io
import json

from backup_pilot.backup import execute_backup, plan_backup
from backup_pilot.cli import main
from backup_pilot.errors import BackupPilotError
from backup_pilot.profiles import load_profile
from backup_pilot.restore import restore_snapshot
from helpers import ProfileCase


class RestoreTest(ProfileCase):
    def setUp(self):
        super().setUp()
        (self.source / 'nested').mkdir()
        (self.source / 'nested' / 'binary.bin').write_bytes(bytes(range(256)) * 16)
        (self.source / 'note.txt').write_text('source remains unchanged', encoding='utf-8')
        self.profile = load_profile(self.config)
        self.snapshot = execute_backup(plan_backup(self.profile))

    def test_restore_preserves_binary_bytes_in_new_target(self):
        target = self.root / 'recovered'
        actual = restore_snapshot(self.profile, self.snapshot.name, target)
        self.assertEqual(actual, target)
        self.assertEqual((target / 'nested' / 'binary.bin').read_bytes(),
                         (self.source / 'nested' / 'binary.bin').read_bytes())
        self.assertEqual((target / 'note.txt').read_text(encoding='utf-8'),
                         'source remains unchanged')

    def test_existing_target_and_source_target_are_refused(self):
        existing = self.root / 'existing'
        existing.mkdir()
        sentinel = existing / 'keep.txt'
        sentinel.write_text('keep', encoding='utf-8')
        for target in (existing, self.source / 'must-not-write-here'):
            with self.subTest(target=target), self.assertRaises(BackupPilotError):
                restore_snapshot(self.profile, self.snapshot.name, target)
        self.assertEqual(sentinel.read_text(encoding='utf-8'), 'keep')

    def test_corruption_and_escape_manifest_refuse_without_target(self):
        manifest = self.snapshot / 'manifest.json'
        document = json.loads(manifest.read_text(encoding='utf-8'))
        document['files'][0]['path'] = '../escape'
        manifest.write_text(json.dumps(document), encoding='utf-8')
        target = self.root / 'recovered'
        with self.assertRaises(BackupPilotError) as error:
            restore_snapshot(self.profile, self.snapshot.name, target)
        self.assertEqual(error.exception.code, 5)
        self.assertFalse(target.exists())

    def test_dry_run_writes_nothing(self):
        target = self.root / 'recovered'
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(['--profiles-dir', str(self.profiles), 'restore', 'demo',
                                   self.snapshot.name, '--to', str(target), '--dry-run']), 0)
        self.assertFalse(target.exists())
        self.assertFalse((self.root / '.backup-pilot-locks').exists())

    def test_default_target_is_under_restored_directory(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(['--profiles-dir', str(self.profiles), 'restore', 'demo',
                                   self.snapshot.name, '--dry-run']), 0)
        self.assertIn('restored', output.getvalue())
