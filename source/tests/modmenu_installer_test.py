"""Installer rejection, cache discovery and transactional update checks."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modmenu.installer import worker


class InstallerTests(unittest.TestCase):
    def fixture(self, root):
        game, setup, payload = (root / name for name in ('game', 'setup', 'payload'))
        for base, names in ((game, ('totk.exe', 'exefs/main', 'romfs/index.json', 'romfs/romfs.bin', 'profile/save/test')),
                            (setup, ('python/python.exe', 'llvm/bin/clang.exe', 'runtime/libtotkrt.a',
                                     'temp/cache/gen/layout.json', 'temp/cache/build/build.ninja')),
                            (payload, ('source/tools/build_modmenu_release.py', 'deps/dependency.py', 'tools/astcenc-sse2.exe'))):
            for name in names:
                path = base / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(b'fixture')
        manifest = {'files': {p.relative_to(payload).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in payload.rglob('*') if p.is_file()}}
        (payload / 'payload.json').write_text(json.dumps(manifest))
        return game, setup, payload

    def test_tampered_payload_stops_without_output(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'build/checks') as temp:
            root = Path(temp); game, setup, payload = self.fixture(root)
            (payload / 'deps/dependency.py').write_text('changed')
            with patch.object(worker, 'game_running', return_value=False):
                with self.assertRaisesRegex(ValueError, 'alterado'):
                    worker.install(payload, setup, game, root / 'output')
            self.assertFalse((root / 'output').exists())
            self.assertEqual((game / 'totk.exe').read_bytes(), b'fixture')

    def test_running_game_blocks_install(self):
        with patch.object(worker, 'game_running', return_value=True):
            with self.assertRaisesRegex(ValueError, 'feche o jogo'):
                worker.install('.', '.', '.', '.')

    def test_cache_detection_and_failed_update_preserve_previous_install(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'build/checks') as temp:
            root = Path(temp); game, setup, payload = self.fixture(root)
            caches = worker.cache_candidates(setup, game)
            self.assertEqual(caches, [setup / 'temp/cache'])
            destination = root / 'output'
            identity = hashlib.sha256(str(game.resolve()).casefold().encode()).hexdigest()[:12]
            home = destination / identity; home.mkdir(parents=True)
            old = home / 'previous'; (old / 'profile').mkdir(parents=True)
            original = json.dumps({'output': str(old)})
            (home / 'latest.json').write_text(original)
            with patch.object(worker, 'game_running', return_value=False), patch('modmenu.compatibility.validate_inputs'), patch.object(worker, 'run', side_effect=RuntimeError('compile failed')):
                with self.assertRaisesRegex(RuntimeError, 'compile failed'):
                    worker.install(payload, setup, game, destination, log=lambda _: None)
            self.assertEqual((home / 'latest.json').read_text(), original)
            self.assertEqual((game / 'profile/save/test').read_bytes(), b'fixture')
            self.assertEqual((game / 'totk.exe').read_bytes(), b'fixture')


if __name__ == '__main__':
    unittest.main()
