import json
from pathlib import Path
import tempfile
import unittest


class ProfileCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        self.destination = self.root / 'backups'
        self.profiles = self.root / 'profiles'
        self.profiles.mkdir()
        self.config = self.profiles / 'demo.toml'
        self.write_profile()

    def write_profile(self, **changes):
        fields = dict(name='demo', source=str(self.source), destination=str(self.destination),
                      exclude=['*.tmp', 'cache/**'], keep_last=7, schedule='daily')
        fields.update(changes)
        self.config.write_text('\n'.join(f'{key} = {json.dumps(value)}' for key, value in fields.items()),
                               encoding='utf-8')
