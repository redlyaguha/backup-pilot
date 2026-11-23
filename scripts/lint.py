#!/usr/bin/env python3
"""Stdlib-only static lint for the backup-pilot codebase.

Checks that must hold across the repository:
- every Python file parses (syntax);
- external commands are invoked as argument lists, never with ``shell=True``;
- no ``eval``/``exec`` usage.

Exit code 0 means clean; any violation is printed to stderr and returns 1.
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = (ROOT / 'src', ROOT / 'tests', ROOT / 'scripts')

SUB = ('run', 'call', 'Popen', 'check_call', 'check_output')

problems = []
for target in TARGETS:
    for path in sorted(target.rglob('*.py')):
        text = path.read_text(encoding='utf-8')
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError as exc:
            problems.append(f'{path}: syntax error: {exc.msg} (line {exc.lineno})')
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr in SUB:
                for kw in node.keywords:
                    if kw.arg == 'shell' and isinstance(kw.value, ast.Constant) and kw.value.value:
                        problems.append(
                            f'{path}:{node.lineno}: subprocess.{func.attr}(shell=True) запрещён '
                            f'— передавайте команду списком аргументов')
            elif isinstance(func, ast.Name) and func.id in ('eval', 'exec'):
                problems.append(f'{path}:{node.lineno}: {func.id}() запрещён')

if problems:
    print('\n'.join(problems), file=sys.stderr)
    sys.exit(1)
print('lint: OK (syntax, без shell=True, без eval/exec)')
