#!/usr/bin/env python3
"""Read-only BP-06 preflight; this is not acceptance of the backup scenario."""
import argparse
import ast
import importlib.util
from pathlib import Path
import platform
import subprocess
import sys


def check(repo: Path, probe: bool = False) -> int:
    print('BP-06 runtime preflight (not product acceptance)')
    print('Python:', platform.python_version())
    print('Architecture:', platform.machine())
    build = Path('/etc/astra/build_version')
    target = build.is_file() and platform.machine() == 'x86_64'
    print('Astra:', build.read_text().strip() if build.is_file() else 'NOT RUN (not Astra)')
    print('Python >= 3.11:', 'OK' if sys.version_info >= (3, 11) else 'FAIL')
    print('tomllib:', 'OK' if importlib.util.find_spec('tomllib') else 'FAIL')
    try:
        commit = subprocess.check_output(
            ['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = 'NOT RUN (source commit unavailable)'
    print('Source commit:', commit)
    package = repo / 'src' / 'backup_pilot'
    files = sorted(package.rglob('*.py')) if package.is_dir() else []
    if not files:
        print('BLOCKED: BP-04/BP-05 prototype missing (src/backup_pilot has no Python files).')
        print('CLI and backup scenario: NOT RUN')
        return 2
    external = set()
    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeError) as exc:
            print('FAIL: source parse error:', path.relative_to(repo), type(exc).__name__)
            return 1
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name.split('.')[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module.split('.')[0]]
            external.update(name for name in names if name != 'backup_pilot'
                            and name not in sys.stdlib_module_names)
    print('External imports (static scan):', ', '.join(sorted(external)) or 'none')
    if external:
        print('FAIL: review imports against the no-PyPI runtime contract; optional imports also require review.')
        return 1
    print('Dynamic imports and system commands require manual review.')
    if sys.version_info < (3, 11) or not importlib.util.find_spec('tomllib'):
        return 1
    if probe:
        if not (package / '__main__.py').is_file():
            print('BLOCKED: python -m backup_pilot entry point not implemented; agree CLI with BP-04.')
            return 2
        if hasattr(__import__('os'), 'geteuid') and __import__('os').geteuid() == 0:
            print('FAIL: run CLI as bpuser, not root.')
            return 1
        # -I -S excludes user site, site-packages and PYTHONPATH; only explicit src and stdlib remain.
        launcher = 'import sys,runpy;sys.path.insert(0,sys.argv.pop(1));runpy.run_module("backup_pilot",run_name="__main__")'
        for flag in ('--help', '--version'):
            print('CLI probe:', flag, flush=True)
            try:
                result = subprocess.run([sys.executable, '-I', '-S', '-c', launcher,
                                         str(repo / 'src'), flag], cwd=repo, timeout=30)
            except (OSError, subprocess.TimeoutExpired) as exc:
                print('FAIL:', type(exc).__name__)
                return 1
            if result.returncode:
                print('FAIL: CLI exit code', result.returncode)
                return 1
    else:
        print('CLI: NOT RUN (use --probe-cli after BP-04 is implemented)')
    print('Backup scenario: NOT RUN (follow docs/astra-prototype.md)')
    if not target:
        print('NOT RUN: Astra SE 1.8 x86-64 target acceptance required.')
        return 2
    print('Preflight OK; BP-06 still requires actual backup evidence.')
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--probe-cli', action='store_true')
    args = parser.parse_args()
    sys.exit(check(args.repo.resolve(), args.probe_cli))
