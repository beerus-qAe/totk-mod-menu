"""Exercise actual Windows shortcut creation with the project icon and no console."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modmenu.installer.shortcuts import create_shortcut
from modmenu import launch


@unittest.skipUnless(os.name == 'nt', 'Windows shortcut integration')
class ShortcutTests(unittest.TestCase):
    def test_game_and_observer_launch_without_console(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'build/checks') as temp:
            root = Path(temp)
            config = {'repo': str(ROOT), 'output': str(root), 'install': str(root),
                      'python': sys.executable, 'release': {'version': 'test'}}
            path = root / 'release-install.json'; path.write_text(json.dumps(config))
            with patch.object(sys, 'argv', ['launch.py', str(path)]), patch.object(launch, 'verify', return_value=(ROOT, root)), patch.object(launch.subprocess, 'Popen') as popen:
                popen.return_value.pid = 123
                launch.main()
                self.assertEqual(popen.call_count, 2)
                for call in popen.call_args_list:
                    self.assertEqual(call.kwargs['creationflags'], subprocess.CREATE_NO_WINDOW)

    def test_real_shortcut_icon_and_pythonw_target(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'build/checks') as temp:
            root = Path(temp) / "menu's test"; root.mkdir()
            (root / 'modmenu').mkdir()
            (root / 'modmenu/launch.py').write_text('# Test fixture, never executed\n')
            shutil.copy2(ROOT / 'modmenu/assets/modmenu.ico', root / 'modmenu.ico')
            config = {'python': sys.executable, 'repo': str(root)}
            (root / 'release-install.json').write_text(json.dumps(config))
            shortcut = root / 'Mod Menu.lnk'
            create_shortcut(root, shortcut)
            escaped = str(shortcut).replace("'", "''")
            script = "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('" + escaped + "'); @{target=$s.TargetPath; arguments=$s.Arguments; icon=$s.IconLocation; workdir=$s.WorkingDirectory}|ConvertTo-Json -Compress"
            result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                                    capture_output=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            actual = json.loads(result.stdout.decode('utf-8-sig'))
            self.assertTrue(actual['target'].lower().endswith('pythonw.exe'))
            self.assertIn('modmenu.ico', actual['icon'])
            self.assertEqual(Path(actual['icon'].rsplit(',', 1)[0]), root / 'modmenu.ico')
            self.assertIn('launch.py', actual['arguments'])
            self.assertIn('release-install.json', actual['arguments'])
            self.assertEqual(Path(actual['workdir']), root)


if __name__ == '__main__':
    unittest.main()
