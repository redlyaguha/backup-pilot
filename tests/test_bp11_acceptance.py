"""Acceptance coverage for BP-11: exclusions, dry-run and integrity failures."""
import contextlib
import io
import json
import stat

from backup_pilot.backup import execute_backup, plan_backup
from backup_pilot.cli import main
from backup_pilot.integrity import verify_snapshot
from backup_pilot.profiles import load_profile
from helpers import ProfileCase


def filesystem_state(root):
    """Capture file contents and metadata, including service files."""
    state = {}
    for path in sorted(root.rglob('*')):
        info = path.lstat()
        state[path.relative_to(root).as_posix()] = (
            stat.S_IMODE(info.st_mode), info.st_mtime_ns,
            path.read_bytes() if path.is_file() else None,
        )
    return state


class BP11AcceptanceTest(ProfileCase):
    def setUp(self):
        super().setUp()
        (self.source / 'keep.bin').write_bytes(bytes(range(256)) * 8)
        (self.source / 'ignored.tmp').write_bytes(b'must not be copied')
        self.profile = load_profile(self.config)

    def test_a1_and_a3_exclude_files_and_dry_run_changes_nothing(self):
        snapshot = execute_backup(plan_backup(self.profile))
        self.assertFalse((snapshot / 'data' / 'ignored.tmp').exists())

        before = filesystem_state(self.root)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                main(['--profiles-dir', str(self.profiles), 'run', 'demo', '--dry-run']), 0
            )
        self.assertEqual(before, filesystem_state(self.root))

    def test_a5_corrupt_manifest_refuses_without_modifying_existing_data(self):
        snapshot = execute_backup(plan_backup(self.profile))
        manifest = snapshot / 'manifest.json'
        document = json.loads(manifest.read_text(encoding='utf-8'))
        document['files'][0]['sha256'] = '0' * 64
        manifest.write_text(json.dumps(document), encoding='utf-8')
        before = filesystem_state(self.root)

        with self.assertRaisesRegex(Exception, 'hash mismatch'):
            verify_snapshot(self.profile, snapshot.name)
        self.assertEqual(before, filesystem_state(self.root))
