#!/usr/bin/env python3
"""Run the real BP-04/BP-05 CLI on the BP-02 stand as an unprivileged user."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib

LAUNCHER = ('import sys,runpy;sys.path.insert(0,sys.argv.pop(1));'
            'runpy.run_module("backup_pilot",run_name="__main__")')


def require(condition, message):
    if not condition:
        raise RuntimeError(message)
    print('PASS:', message, flush=True)


def hashes(directory):
    return {p.relative_to(directory).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(directory.rglob('*')) if p.is_file()}


def verify(repo):
    require(os.geteuid() != 0, 'unprivileged execution')
    build = Path('/etc/astra/build_version')
    require(build.is_file() and build.read_text().strip().split('.')[:2] == ['1', '8']
            and platform.machine() == 'x86_64', 'Astra SE 1.8 x86-64 target')
    print('Astra:', build.read_text().strip())
    print('Python:', platform.python_version())
    rootfs = subprocess.check_output(['findmnt', '-n', '-o', 'FSTYPE', '/'], text=True).strip()
    require(rootfs not in {'overlay', 'squashfs'}
            and 'boot=live' not in Path('/proc/cmdline').read_text().split(),
            'installed disk system, not Live')
    commit = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
    print('Prototype commit:', commit)
    dirty = subprocess.check_output(['git', '-C', str(repo), 'status', '--porcelain',
                                     '--untracked-files=no'], text=True)
    require(not dirty, 'tracked prototype files unchanged')
    profile_file = repo / 'examples/profile.toml'
    profile = tomllib.loads(profile_file.read_text())
    require(profile['name'] == 'demo' and profile['exclude'] == ['*.tmp', 'cache/**'],
            'expected demo profile and exclusions')
    source = Path(profile['source'])
    destination = Path(profile['destination']) / profile['name']
    before = hashes(source)
    require(set(before) == {'docs/readme.txt', 'bin/sample.bin', 'notes.tmp', 'cache/item.txt'},
            'BP-02 sample files present')
    with tempfile.TemporaryDirectory(prefix='bp06-') as temporary:
        work = Path(temporary)
        profiles = work / 'profiles'
        profiles.mkdir()
        shutil.copyfile(profile_file, profiles / 'demo.toml')

        def cli(*arguments, expected=0, named=False):
            args = ['--profiles-dir', str(profiles), *arguments] if named else list(arguments)
            print('$ backup-pilot', ' '.join(args).replace(str(work), '<fixtures>'), flush=True)
            result = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', LAUNCHER,
                                     str(repo / 'src'), *args], text=True, capture_output=True,
                                    timeout=120, cwd=repo)
            output = result.stdout + result.stderr
            print(output.replace(str(work), '<fixtures>'), end='', flush=True)
            print('exit:', result.returncode, flush=True)
            require(result.returncode == expected, 'CLI exit code matches expected ' + str(expected))
            return result.stdout.splitlines()

        cli('--help')
        cli('--version')
        cli('profiles', 'validate', '--config', str(profile_file))
        old = cli('snapshots', 'demo', named=True)
        cli('run', 'demo', named=True)
        current = cli('snapshots', 'demo', named=True)
        new = set(current) - set(old)
        require(len(new) == 1 and len(current) == len(old) + 1, 'one new completed snapshot listed')
        snapshot = destination / new.pop()
        require(re.fullmatch(r'\d{8}T\d{12}Z-[0-9a-f]{8}', snapshot.name) is not None,
                'completed snapshot identifier')
        copied = hashes(snapshot / 'data')
        expected_files = {name: before[name] for name in ('docs/readme.txt', 'bin/sample.bin')}
        require(copied == expected_files, 'copied bytes match source; both exclusions applied')
        metadata = json.loads((snapshot / 'snapshot.json').read_text())
        require(metadata['snapshot_id'] == snapshot.name and metadata['profile'] == 'demo',
                'snapshot completion metadata matches listing')
        require(hashes(source) == before, 'source file hashes unchanged')
        print('Completed snapshot:', snapshot.name)
        for name, digest in copied.items():
            print('SHA256:', digest, name)

        # Real filesystem denial after a readable first file, without touching the stand source.
        fail_source = work / 'failure-source'
        fail_dest = work / 'failure-destination'
        fail_source.mkdir()
        (fail_source / 'a.txt').write_text('readable first file\n')
        unreadable = fail_source / 'z.txt'
        unreadable.write_text('unreadable fixture\n')
        unreadable.chmod(0)
        config = ('name = "bp06-denied"\nsource = ' + json.dumps(str(fail_source)) + '\n'
                  'destination = ' + json.dumps(str(fail_dest)) + '\n'
                  'exclude = []\nkeep_last = 1\nschedule = "daily"\n')
        (profiles / 'bp06-denied.toml').write_text(config)
        try:
            cli('run', 'bp06-denied', named=True, expected=3)
            require(cli('snapshots', 'bp06-denied', named=True) == [],
                    'failed copy absent from completed snapshot listing')
            partials = list((fail_dest / 'bp06-denied').glob('.partial-*'))
            require(len(partials) == 1 and (partials[0] / 'data/a.txt').is_file()
                    and not (partials[0] / 'snapshot.json').exists(),
                    'actual incomplete copy retained without success metadata')
        finally:
            unreadable.chmod(0o600)
    print('BP-06 scenario: PASS (integrity/restore/retention modules are outside this check)')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True, type=Path, help='clean checkout of the BP-05 prototype')
    args = parser.parse_args()
    try:
        verify(args.repo.resolve())
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as exc:
        print('FAIL:', exc, file=sys.stderr)
        sys.exit(1)
