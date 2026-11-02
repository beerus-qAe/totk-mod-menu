"""Build the standalone Windows installer from source and approved local tools."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--setup', type=Path, required=True)
    args = ap.parse_args()
    release = json.loads((ROOT / 'modmenu/release.json').read_text())
    out = ROOT / 'build/installer-package';out.mkdir(parents=True, exist_ok=True)
    files = {}
    paths = ['runtime', 'recomp', 'tools/cheats.py', 'tools/shader_census.py', 'tools/button_icons.py',
             'tools/check_content.py', 'LICENSE', 'THIRD_PARTY_NOTICES.md']
    data = subprocess.check_output(['git', 'archive', release['upstream_commit'], *paths], cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        for entry in archive:
            if entry.isfile():files['source/' + entry.name] = archive.extractfile(entry).read()
    # Overlay only intentional module/UI/tool source, never private build output.
    for path in (ROOT / 'modmenu').rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts:
            files['source/' + path.relative_to(ROOT).as_posix()] = path.read_bytes()
    for name in ('runtime/ui/menu.cpp', 'runtime/ui/menu_win.cpp', 'runtime/ui/menu.h', 'THIRD_PARTY_NOTICES.md',
                 'tools/build_modmenu_release.py', 'tools/build_spawn_diagnostic.py', 'tools/item_catalog.py',
                 'tools/make_item_icon_atlas.py', 'tools/player_position_probe.py'):
        files['source/' + name] = (ROOT / name).read_bytes()
    snapshot = dict(upstream_commit=release['upstream_commit'], files={k[7:]: digest(v) for k,v in files.items()})
    files['source/source-manifest.json'] = json.dumps(snapshot, indent=2).encode()
    deps = ROOT / 'build/icon-python-deps'
    for name in ('PIL', 'fontTools', 'pillow-13.0.0.dist-info', 'fonttools-4.68.0.dist-info'):
        for path in (deps / name).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts:
                files['deps/' + path.relative_to(deps).as_posix()] = path.read_bytes()
    for name in ('gui.py','worker.py'):
        files[name] = (ROOT / 'modmenu/installer' / name).read_bytes()
    decoder_archive = ROOT / 'build/icon-tools/astcenc.zip'
    if digest(decoder_archive.read_bytes()) != 'cbde7c78adcc90d0d90ecf10f32d03f3340fbe1720cb6d6c892147d625e74d2d':
        raise ValueError('Official astcenc archive checksum mismatch')
    with zipfile.ZipFile(decoder_archive) as archive:
        files['tools/astcenc-sse2.exe'] = archive.read('bin/astcenc-sse2.exe')
    files['licenses/astcenc-LICENSE.txt'] = (ROOT / 'build/icon-tools/astcenc-LICENSE.txt').read_bytes()
    files['LICENSE'] = (ROOT / 'LICENSE').read_bytes()
    files['THIRD_PARTY_NOTICES.md'] = (ROOT / 'THIRD_PARTY_NOTICES.md').read_bytes()
    # No game-derived cache, data or generated code may enter the embedded payload.
    import check_content
    for name, content in files.items():
        if check_content.GENERATED_MARKER.encode() in content:
            raise ValueError('Generated game code in installer: ' + name)
        if Path(name).suffix.lower() in check_content.BLOCKED_SUFFIXES or check_content.KEY_LINE.search(content.decode('utf-8', errors='ignore')):
            raise ValueError('Blocked game content in installer: ' + name)
    files['payload.json'] = json.dumps(dict(version=release['version'], files={k:digest(v) for k,v in files.items()}), indent=2).encode()
    payload = out / 'payload.zip'
    with zipfile.ZipFile(payload,'w',zipfile.ZIP_DEFLATED) as archive:
        for name, content in sorted(files.items()):archive.writestr(name,content)
    (out / 'payload_size.h').write_text('#define PAYLOAD_SIZE ' + str(payload.stat().st_size) + '\n')
    manifest = ROOT / 'modmenu/installer/launcher.manifest'
    (out / 'payload.rc').write_text('101 RCDATA "' + payload.as_posix() + '"\n1 24 "' + manifest.as_posix() + '"\n')
    compiler = args.setup / 'llvm/bin/clang.exe'
    resource = out / 'payload.o'
    subprocess.run([str(args.setup / 'llvm/bin/llvm-windres.exe'),str(out / 'payload.rc'),'-O','coff','-o',str(resource)],check=True)
    target = ROOT / 'build/releases' / ('TotK-ModMenu-Installer-' + release['version'] + '.exe')
    target.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run([str(compiler),'-O2','-mwindows','-municode','-I',str(out),str(ROOT / 'modmenu/installer/launcher.c'),
                    str(resource),'-lshell32','-lole32','-luser32','-o',str(target)],check=True)
    target.with_suffix('.exe.sha256').write_text(digest(target.read_bytes()) + '  ' + target.name + '\n')
    print('INSTALLER_BUILD_OK:',target, target.stat().st_size,'bytes; payload',len(files),'files')


if __name__ == '__main__':
    main()
