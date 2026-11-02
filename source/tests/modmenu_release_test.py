"""Compatibility rejection, package integrity and real patch application checks."""
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modmenu import compatibility as compat
from modmenu.launch import verify
from modmenu.apply import apply


def fake_main(path, build_id):
    path.parent.mkdir(parents=True, exist_ok=True)
    header = bytearray(0x60)
    header[:4] = b'NSO0'
    header[0x40:0x60] = bytes.fromhex(build_id.ljust(64, '0'))
    path.write_bytes(header)


class CompatibilityTests(unittest.TestCase):
    def test_launcher_rejects_changed_executable(self):
        release = json.loads((ROOT / 'modmenu/release.json').read_text())
        adapter = json.loads((ROOT / 'modmenu/adapters' / release['adapter']).read_text())
        with tempfile.TemporaryDirectory(dir=ROOT / 'build/checks') as temp:
            root = Path(temp)
            fake_main(root / 'game/exefs/main', adapter['build_id'])
            (root / 'totk.exe').write_bytes(b'synthetic executable, never launched')
            config = dict(repo=str(ROOT), output=str(root), install=str(root / 'game'), release=release,
                          exe_sha256=compat.sha256(root / 'totk.exe'),
                          main_sha256=compat.sha256(root / 'game/exefs/main'))
            verify(config)
            (root / 'totk.exe').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'Installation changed'):
                verify(config)

    def test_correct_build_and_wrong_build(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'build/checks') as temp:
            install = Path(temp)
            adapter = {'build_id': '12' * 20}
            fake_main(install / 'exefs/main', adapter['build_id'])
            compat.validate_game(install, adapter)
            fake_main(install / 'exefs/main', '34' * 20)
            with self.assertRaisesRegex(ValueError, 'Unsupported game'):
                compat.validate_game(install, adapter)
            (install / 'exefs/main').write_bytes(b'bad')
            with self.assertRaises(ValueError):
                compat.validate_game(install, adapter)

    def test_cache_tampering_and_wrong_cached_game(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'build/checks') as temp:
            root = Path(temp)
            (root / 'modmenu/adapters').mkdir(parents=True)
            adapter = {'build_id': '12' * 20}
            (root / 'modmenu/release.json').write_text(json.dumps({'adapter': 'test.json'}))
            (root / 'modmenu/adapters/test.json').write_text(json.dumps(adapter))
            fake_main(root / 'game/exefs/main', adapter['build_id'])
            (root / 'runtime.a').write_bytes(b'valid runtime')
            lock = {'setup': {'runtime.a': compat.sha256(root / 'runtime.a')}, 'cache': {}}
            (root / 'modmenu/adapters/setup-0.3.1-lock.json').write_text(json.dumps(lock))
            (root / 'build').mkdir()
            modules = root / 'build/modules.c'
            modules.write_text(compat.sha256(root / 'game/exefs/main'))
            with patch.object(compat, 'ROOT', root):
                compat.validate_inputs(root, root, root / 'game')
                modules.write_text('different game')
                with self.assertRaisesRegex(ValueError, 'different ExeFS'):
                    compat.validate_inputs(root, root, root / 'game')
                (root / 'runtime.a').write_bytes(b'changed runtime')
                with self.assertRaisesRegex(ValueError, 'modified recomp'):
                    compat.validate_inputs(root, root, root / 'game')

    def test_real_package_applies_to_upstream_and_rejects_tampering(self):
        release = json.loads((ROOT / 'modmenu/release.json').read_text())
        archive = ROOT / 'build/releases' / ('TotK-ModMenu-' + release['version'] + '-source.zip')
        if not archive.exists():
            self.fail('Build the source package before running this test')
        with tempfile.TemporaryDirectory(dir=ROOT / 'build/checks') as temp:
            temp = Path(temp)
            package, checkout = temp / 'package', temp / 'checkout'
            checkout.mkdir()
            with zipfile.ZipFile(archive) as source:
                for name in source.namelist():
                    self.assertFalse(any(part in ('build', 'generated', 'profile', '__pycache__') for part in Path(name).parts), name)
                    self.assertNotIn(Path(name).suffix.lower(), ('.exe', '.dll', '.bin', '.rgba', '.png', '.keys', '.tsv'), name)
                source.extractall(package)
            names = ['runtime/ui/menu.cpp', 'runtime/ui/menu.h', 'runtime/ui/menu_win.cpp', 'THIRD_PARTY_NOTICES.md']
            original = subprocess.check_output(['git', 'archive', release['upstream_commit'], *names], cwd=ROOT)
            with tarfile.open(fileobj=io.BytesIO(original)) as source:
                source.extractall(checkout, filter='data')
            with patch('modmenu.apply.subprocess.check_output', return_value=release['upstream_commit']), patch.dict(os.environ, {'GIT_CEILING_DIRECTORIES': str(temp.parent)}):
                apply(package, checkout, check_only=True)
                self.assertFalse((checkout / 'modmenu').exists())
                apply(package, checkout)
                self.assertIn('../../modmenu/integration/ui.h', (checkout / 'runtime/ui/menu.cpp').read_text())
                # Integrity failures must happen before git apply or file mutations.
                payload = package / 'source/modmenu/release.json'
                payload.write_text('{}')
                with self.assertRaisesRegex(ValueError, 'checksum'):
                    apply(package, checkout)


if __name__ == '__main__':
    unittest.main()
