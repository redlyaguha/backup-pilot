from backup_pilot.backup import execute_backup, plan_backup
from backup_pilot.cli import main
from backup_pilot.errors import BackupPilotError
from backup_pilot.integrity import verify_snapshot
from backup_pilot.profiles import load_profile
from helpers import ProfileCase


class IntegrityTest(ProfileCase):
    def setUp(self):
        super().setUp()
        (self.source / 'a.txt').write_text('учебный файл', encoding='utf-8')
        (self.source / 'z.bin').write_bytes(bytes(range(256)))
        self.profile = load_profile(self.config)

    def test_verify_good_snapshot(self):
        snapshot = execute_backup(plan_backup(self.profile))
        verify_snapshot(self.profile, snapshot.name)

    def test_verify_corrupted_file(self):
        snapshot = execute_backup(plan_backup(self.profile))
        target = snapshot / 'data' / 'a.txt'
        target.write_bytes(b'X' + target.read_bytes()[1:])
        
        with self.assertRaises(BackupPilotError) as error:
            verify_snapshot(self.profile, snapshot.name)
        self.assertEqual(error.exception.code, 5)
        self.assertIn('Integrity violation: hash mismatch', str(error.exception))

    def test_verify_missing_file(self):
        snapshot = execute_backup(plan_backup(self.profile))
        (snapshot / 'data' / 'z.bin').unlink()
        
        with self.assertRaises(BackupPilotError) as error:
            verify_snapshot(self.profile, snapshot.name)
        self.assertEqual(error.exception.code, 5)
        self.assertIn('Integrity violation: файл отсутствует', str(error.exception))

    def test_verify_cli_exit_code_5(self):
        snapshot = execute_backup(plan_backup(self.profile))
        (snapshot / 'data' / 'a.txt').write_text('corrupted', encoding='utf-8')
        exit_code = main(['--profiles-dir', str(self.profiles), 'verify', 'demo', snapshot.name])
        self.assertEqual(exit_code, 5)