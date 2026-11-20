"""End-to-end acceptance coverage for the BP-18 A1-A5 workflow."""
from dataclasses import replace
import shutil

from backup_pilot.backup import execute_backup, plan_backup
from backup_pilot.integrity import verify_snapshot
from backup_pilot.profiles import load_profile
from backup_pilot.restore import restore_snapshot
from backup_pilot.retention import apply_retention, plan_retention
from helpers import ProfileCase


class BP18AcceptanceTest(ProfileCase):
    def test_profile_backup_verify_restore_and_retention(self):
        source_file = self.source / 'payload.bin'
        source_file.write_bytes(bytes(range(256)) * 32)
        excluded = self.source / 'ignored.tmp'
        excluded.write_bytes(b'excluded')
        profile = replace(load_profile(self.config), keep_last=1)

        first = execute_backup(plan_backup(profile))
        source_file.write_bytes(b'new version\x00' + bytes(range(256)) * 16)
        second = execute_backup(plan_backup(profile))
        verify_snapshot(profile, second.name)

        target = self.root / 'restored'
        restore_snapshot(profile, second.name, target)
        self.assertEqual((target / 'payload.bin').read_bytes(), source_file.read_bytes())
        self.assertFalse((target / 'ignored.tmp').exists())

        root = self.destination / profile.name
        foreign = root / 'foreign'
        partial = root / '.partial-interrupted'
        foreign.mkdir()
        partial.mkdir()
        plan = plan_retention(profile)
        self.assertEqual(plan.remove, (first,))
        self.assertEqual(plan.keep, (second,))
        self.assertTrue(foreign.exists())
        self.assertTrue(partial.exists())

        if shutil.rmtree.avoids_symlink_attacks:
            apply_retention(profile)
            self.assertFalse(first.exists())
            self.assertTrue(second.exists())
            self.assertTrue(foreign.exists())
            self.assertTrue(partial.exists())
