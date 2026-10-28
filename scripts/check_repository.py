#!/usr/bin/env python3
"""Check the project scaffold; this is not product testing or acceptance."""
from pathlib import Path
import sys
import tomllib

root = Path(__file__).resolve().parents[1]
required = [
    'README.md', 'CHANGELOG.md', 'LICENSE', 'CONTRIBUTING.md', 'CHECKLIST.md',
    'gitflic-ci.yaml', 'src/README.md', 'tests/README.md', 'debian/README.md',
    'docs/architecture.md', 'docs/user-guide.md', 'docs/admin-guide.md',
    'docs/test-plan.md', 'docs/demo.md', 'docs/project-plan.md', 'docs/team.md',
    'docs/backlog.md', 'docs/requirements/common.md', 'docs/requirements/case-04.md',
    'examples/profile.toml', 'scripts/lint.sh', 'scripts/test.sh', 'scripts/package.sh',
    'dist/.gitkeep', '.github/pull_request_template.md',
    '.github/workflows/repository-checks.yml', '.github/workflows/branch-policy.yml',
]
missing = [name for name in required if not (root / name).is_file()]
if missing:
    sys.exit('Missing required project files: ' + ', '.join(missing))
with (root / 'examples/profile.toml').open('rb') as stream:
    profile = tomllib.load(stream)
if not {'name', 'source', 'destination', 'exclude', 'keep_last', 'schedule'} <= profile.keys():
    sys.exit('Example profile does not match the documented contract')
print('Repository scaffold is consistent. Product tests and Astra acceptance have NOT run.')
