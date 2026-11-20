import contextlib
import io
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
from backup_pilot.backup import execute_backup, plan_backup, list_snapshots
from backup_pilot.cli import main
from backup_pilot.errors import BackupPilotError
from backup_pilot.locking import profile_lock
from backup_pilot.profiles import load_profile
from helpers import ProfileCase

class LockingTest(ProfileCase):
    def setUp(self):
        super().setUp()
        (self.source/'a').write_bytes(b'original')
        self.profile=load_profile(self.config)

    def test_second_process_gets_busy_then_lock_releases(self):
        code = (
            'from pathlib import Path; from backup_pilot.profiles import load_profile; '
            'from backup_pilot.locking import profile_lock; import sys; '
            'p=load_profile(Path(sys.argv[1])); '
            'ctx=profile_lock(p); ctx.__enter__(); print("ready",flush=True); '
            'sys.stdin.readline(); ctx.__exit__(None,None,None)'
        )
        child=subprocess.Popen([sys.executable,'-B','-c',code,str(self.config)],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            self.assertEqual(child.stdout.readline().strip(),'ready')
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(['--profiles-dir',str(self.profiles),'run','demo']),6)
            self.assertEqual(list_snapshots(self.profile),[])
        finally:
            child.communicate(chr(10),timeout=10)
        self.assertEqual(child.returncode,0)
        snapshot=execute_backup(plan_backup(self.profile))
        self.assertTrue(snapshot.exists())

    def test_failure_releases_lock_and_preserves_previous_snapshot(self):
        previous=execute_backup(plan_backup(self.profile))
        with patch('backup_pilot.backup.shutil.copy2',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                execute_backup(plan_backup(self.profile))
        self.assertEqual(list_snapshots(self.profile),[previous])
        self.assertEqual((previous/'data'/'a').read_bytes(),b'original')
        self.assertEqual((self.source/'a').read_bytes(),b'original')
        execute_backup(plan_backup(self.profile))
        self.assertEqual(len(list_snapshots(self.profile)),2)

    def test_run_and_prune_share_the_same_lock(self):
        from backup_pilot.retention import apply_retention
        import shutil
        with profile_lock(self.profile):
            with self.assertRaises(BackupPilotError) as error:
                execute_backup(plan_backup(self.profile))
            self.assertEqual(error.exception.code,6)
            if shutil.rmtree.avoids_symlink_attacks:
                with self.assertRaises(BackupPilotError) as error:
                    apply_retention(self.profile)
                self.assertEqual(error.exception.code,6)
