"""Create a Windows shortcut with the project icon and a console-free launcher."""
import base64
import json
from pathlib import Path
import subprocess


def create_shortcut(output, shortcut=None):
    output = Path(output).resolve()
    config = json.loads((output / 'release-install.json').read_text(encoding='utf-8'))
    python = Path(config['python']).with_name('pythonw.exe')
    launcher = Path(config['repo']) / 'modmenu/launch.py'
    icon = output / 'modmenu.ico'
    if not all(path.is_file() for path in (python, launcher, icon)):
        raise ValueError('Incomplete shortcut inputs: Python, launcher or icon is missing')
    quote = lambda value: "'" + str(value).replace("'", "''") + "'"
    location = quote(Path(shortcut).resolve()) if shortcut else "[IO.Path]::Combine([Environment]::GetFolderPath('Desktop'),'TotK Mod Menu.lnk')"
    arguments = '"' + str(launcher) + '" "' + str(output / 'release-install.json') + '"'
    script = "$ErrorActionPreference='Stop'; $w=New-Object -ComObject WScript.Shell; $s=$w.CreateShortcut(" + location + '); '
    script += '$s.TargetPath=' + quote(python) + '; $s.Arguments=' + quote(arguments) + '; '
    script += '$s.WorkingDirectory=' + quote(output) + '; $s.IconLocation=' + quote(str(icon) + ',0') + '; '
    script += "$s.Description='TotK Mod Menu'; $s.WindowStyle=1; $s.Save()"
    encoded = base64.b64encode(script.encode('utf-16-le')).decode('ascii')
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded],
                            capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise RuntimeError('Could not create the Windows shortcut: ' + result.stderr.decode(errors='replace'))


def open_modmenu(receipt):
    output = Path(receipt['output'])
    config = json.loads((output / 'release-install.json').read_text(encoding='utf-8'))
    return subprocess.Popen([str(Path(config['python']).with_name('pythonw.exe')),
                             str(Path(config['repo']) / 'modmenu/launch.py'),
                             str(output / 'release-install.json')], cwd=output,
                            creationflags=subprocess.CREATE_NO_WINDOW)
