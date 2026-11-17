import json
import os
import shutil
import unittest
from dataclasses import replace
from backup_pilot.backup import execute_backup, plan_backup
from backup_pilot.retention import plan_retention, apply_retention
from backup_pilot.profiles import load_profile
from helpers import ProfileCase

class RetentionTest(ProfileCase):
    def setUp(self):
        super().setUp()
        (self.source / 'a').write_bytes(b'original')
        self.profile = replace(load_profile(self.config), keep_last=2)
        self.snapshots = [execute_backup(plan_backup(self.profile)) for _ in range(4)]

    def test_plan_keeps_newest_and_never_writes(self):
        before = {p.relative_to(self.destination): p.read_bytes() for p in self.destination.rglob('*') if p.is_file()}
        plan = plan_retention(self.profile)
        self.assertEqual(plan.keep, tuple(self.snapshots[-2:]))
        self.assertEqual(plan.remove, tuple(self.snapshots[:2]))
        self.assertEqual(before, {p.relative_to(self.destination):p.read_bytes() for p in self.destination.rglob('*') if p.is_file()})

    @unittest.skipUnless(shutil.rmtree.avoids_symlink_attacks, 'safe deletion requires dir_fd')
    def test_apply_preserves_foreign_partial_and_minimum_one(self):
        root = self.destination / self.profile.name
        foreign = root / 'foreign'; foreign.mkdir()
        partial = root / '.partial-old'; partial.mkdir()
        apply_retention(replace(self.profile,keep_last=1))
        self.assertTrue(self.snapshots[-1].exists())
        self.assertFalse(self.snapshots[0].exists())
        self.assertTrue(foreign.exists())
        self.assertTrue(partial.exists())
        self.assertEqual((self.source/'a').read_bytes(), b'original')

    def test_malformed_manifest_is_never_candidate(self):
        (self.snapshots[0]/'manifest.json').write_text('{}')
        self.assertNotIn(self.snapshots[0], plan_retention(self.profile).remove)

    def test_other_profile_metadata_is_never_candidate(self):
        path=self.snapshots[0]/'manifest.json'
        manifest=json.loads(path.read_text()); manifest['profile']='other'
        path.write_text(json.dumps(manifest))
        self.assertNotIn(self.snapshots[0], plan_retention(self.profile).remove)
