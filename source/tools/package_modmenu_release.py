"""Create an allowlisted source-only ZIP; never package a private game build."""
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path
from check_content import problems_for

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ['runtime/ui/menu.cpp', 'runtime/ui/menu.h', 'runtime/ui/menu_win.cpp', 'THIRD_PARTY_NOTICES.md']
TOOLS = ['build_modmenu_release.py', 'build_spawn_diagnostic.py', 'item_catalog.py',
         'make_item_icon_atlas.py', 'player_position_probe.py', 'package_modmenu_release.py', 'check_modmenu_release.py', 'build_modmenu_installer.py']
TESTS = ['modmenu_release_test.py', 'apple_request_test.c', 'apple_experiment_test.c',
         'spawn_menu_test.c', 'beta_catalog_test.c', 'items_window_test.cpp', 'item_icons_test.cpp', 'modmenu_installer_test.py']


def main():
    release = json.loads((ROOT / 'modmenu/release.json').read_text())
    files = sorted(p for p in (ROOT / 'modmenu').rglob('*')
                   if p.is_file() and p.suffix in ('.py', '.cpp', '.c', '.h', '.json', '.md', '.txt', '.manifest')
                   and '__pycache__' not in p.parts)
    files += [ROOT / 'tools' / name for name in TOOLS]
    files += [ROOT / 'tests' / name for name in TESTS]
    files += [ROOT / 'LICENSE']
    # Reject generated code, game containers, large binaries and key material.
    for path in files:
        errors = problems_for(path)
        if errors:
            raise ValueError(str(path) + ': ' + ', '.join(errors))
    patch = subprocess.check_output(['git', 'diff', '--binary', release['upstream_commit'], '--', *INTEGRATION], cwd=ROOT)
    if not patch:
        raise ValueError('Missing integration patch')
    manifest = dict(release, files={str(p.relative_to(ROOT)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
                    patch_sha256=hashlib.sha256(patch).hexdigest(), package_kind='source-only')
    out = ROOT / 'build/releases' / ('TotK-ModMenu-' + release['version'] + '-source.zip')
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('package.json', json.dumps(manifest, indent=2))
        archive.writestr('integration.patch', patch)
        archive.write(ROOT / 'modmenu/apply.py', 'apply.py')
        archive.write(ROOT / 'modmenu/RELEASE.md', 'README.md')
        archive.write(ROOT / 'LICENSE', 'LICENSE')
        archive.write(ROOT / 'THIRD_PARTY_NOTICES.md', 'THIRD_PARTY_NOTICES.md')
        for path in files:
            archive.write(path, 'source/' + str(path.relative_to(ROOT)).replace('\\', '/'))
    checksum = hashlib.sha256(out.read_bytes()).hexdigest()
    out.with_suffix('.zip.sha256').write_text(checksum + '  ' + out.name + '\n')
    print('SOURCE_PACKAGE_OK:', out, out.stat().st_size, 'bytes')
    print('SHA256:', checksum)


if __name__ == '__main__':
    main()
