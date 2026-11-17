from contextlib import ExitStack, redirect_stdout
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import unittest
from unittest.mock import patch

from backup_pilot.backup import BackupPlan, FileEntry, execute_backup, plan_backup, preview_lines
from backup_pilot.cli import main
from backup_pilot.profiles import load_profile
from helpers import ProfileCase


def tree_state(root):
    result = {}
    for path in sorted(root.rglob('*')):
        info = path.lstat()
        result[str(path.relative_to(root))] = (stat.S_IMODE(info.st_mode), info.st_mtime_ns,
                                               path.read_bytes() if path.is_file() else None)
    return result


class DryRunTest(ProfileCase):
    def setUp(self):
        super().setUp()
        (self.source / 'empty').mkdir()
        (self.source / 'b.txt').write_bytes(b'copy me')
        (self.source / 'a.tmp').write_bytes(b'excluded')
        self.profile = load_profile(self.config)

    def test_absent_and_existing_destination_unchanged(self):
        for existing in (False, True):
            with self.subTest(existing=existing):
                if existing:
                    execute_backup(plan_backup(self.profile))
                    (self.destination / 'foreign.txt').write_bytes(b'keep me')
                before = tree_state(self.root)
                with redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(main(['--profiles-dir', str(self.profiles), 'run', 'demo', '--dry-run']), 0)
                self.assertEqual(before, tree_state(self.root))
                self.assertIn('copy "b.txt"', output.getvalue())
                self.assertNotIn('copy "a.tmp"', output.getvalue())
                if not existing:
                    self.assertFalse(self.destination.exists())

    def test_no_write_operations_and_execution_uses_same_plan(self):
        real_open = Path.open

        def read_only_open(path, mode='r', *args, **kwargs):
            if any(flag in mode for flag in ('w', 'a', 'x', '+')):
                raise AssertionError('write during preview')
            return real_open(path, mode, *args, **kwargs)

        with ExitStack() as stack:
            stack.enter_context(patch.object(Path, 'open', read_only_open))
            for method in ('mkdir', 'write_text', 'write_bytes', 'rename', 'unlink', 'touch'):
                stack.enter_context(patch.object(Path, method, side_effect=AssertionError('write during preview')))
            stack.enter_context(patch('backup_pilot.backup.shutil.copy2', side_effect=AssertionError('copy during preview')))
            plan = plan_backup(self.profile)
            lines = preview_lines(plan)
        snapshot = execute_backup(plan)
        copied = sorted(path.relative_to(snapshot / 'data').as_posix()
                        for path in (snapshot / 'data').rglob('*') if path.is_file())
        self.assertEqual(copied, sorted(json.loads(line[5:]) for line in lines if line.startswith('copy ')))

    def test_preview_quotes_every_path_without_extra_lines(self):
        special = Path('a\ncopy nonexistent.txt\r\t\x1b"\\имя')
        plan = BackupPlan(self.profile, (special,), (FileEntry(special, ()),))
        lines = preview_lines(plan)
        self.assertEqual(len(lines), 4)
        self.assertEqual(len('\n'.join(lines).splitlines()), 4)
        destination = self.profile.destination / self.profile.name / '<new-snapshot>' / 'data'
        self.assertEqual(json.loads(lines[0].split(': ', 1)[1]), destination.as_posix())
        self.assertEqual(json.loads(lines[1][6:]), '.')
        self.assertEqual(json.loads(lines[2][6:]), special.as_posix())
        self.assertEqual(json.loads(lines[3][5:]), special.as_posix())
        self.assertIn('\\ncopy nonexistent.txt\\r\\t\\u001b\\"', lines[3])
        self.assertTrue(lines[3].isascii())

    @unittest.skipIf(os.name == 'nt', 'control characters in filenames require Unix')
    def test_real_special_names_match_preview_and_copy(self):
        names = ('a\ncopy nonexistent.txt', 'cr\rname', 'tab\tname', 'esc\x1bname',
                 'quote"name', 'back\\slash', 'имя')
        directory = self.source / 'directory\nmkdir fake'
        directory.mkdir()
        for name in names:
            (directory / name).write_bytes(name.encode('utf-8'))
        self.destination = self.root / 'destination\n\r\t\x1b"\\имя'
        self.write_profile()
        profile = load_profile(self.config)
        plan = plan_backup(profile)
        before = tree_state(self.root)
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(['--profiles-dir', str(self.profiles), 'run', 'demo', '--dry-run']), 0)
        self.assertEqual(before, tree_state(self.root))
        self.assertFalse(self.destination.exists())
        lines = output.getvalue().splitlines()
        self.assertEqual(lines, preview_lines(plan))
        self.assertEqual(len(lines), 2 + len(plan.directories) + len(plan.files))
        destination = profile.destination / profile.name / '<new-snapshot>' / 'data'
        self.assertEqual(json.loads(lines[0].split(': ', 1)[1]), destination.as_posix())
        snapshot = execute_backup(plan)
        copied = sorted(path.relative_to(snapshot / 'data').as_posix()
                        for path in (snapshot / 'data').rglob('*') if path.is_file())
        self.assertEqual(copied, sorted(json.loads(line[5:]) for line in lines if line.startswith('copy ')))
        for name in names:
            self.assertEqual((snapshot / 'data' / directory.name / name).read_bytes(), name.encode('utf-8'))

    def test_fresh_launcher_does_not_create_bytecode(self):
        repo = Path(__file__).resolve().parents[1]
        checkout = self.root / 'checkout'
        (checkout / 'src').mkdir(parents=True)
        shutil.copytree(repo / 'src' / 'backup_pilot', checkout / 'src' / 'backup_pilot',
                        ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copy2(repo / 'backup-pilot', checkout / 'backup-pilot')
        before = tree_state(self.root)
        result = subprocess.run([sys.executable, str(checkout / 'backup-pilot'), '--profiles-dir',
                                 str(self.profiles), 'run', 'demo', '--dry-run'], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, tree_state(self.root))
