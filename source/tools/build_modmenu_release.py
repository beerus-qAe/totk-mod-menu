"""Build a private release candidate using the supported upstream setup cache.

Run with the setup's Python 3.14, after installing modmenu/requirements-build.txt.
No downloads, automatic game extraction or updates to the original install.
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modmenu.compatibility import sha256, validate_inputs


def run(*args):
    subprocess.run([sys.executable, *map(str, args)], cwd=ROOT, check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('setup', 'cache', 'install', 'decoder'):
        ap.add_argument('--' + name, type=Path, required=True)
    ap.add_argument('--check-only', action='store_true')
    ap.add_argument('--source-manifest', type=Path, help='Verified installer source snapshot instead of a Git checkout')
    ap.add_argument('--profile-source', type=Path, help='Initial profile source; never replaces an existing release profile')
    args = ap.parse_args()
    release, adapter = validate_inputs(args.setup, args.cache, args.install)
    if args.source_manifest:
        snapshot = json.loads(args.source_manifest.read_text())
        head = snapshot['upstream_commit']
        for relative, expected in snapshot['files'].items():
            path = (ROOT / relative).resolve()
            if not path.is_relative_to(ROOT) or sha256(path) != expected:
                ap.error('Installer source integrity check failed: ' + relative)
    else:
        head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if head != release['upstream_commit']:
        ap.error('Unsupported upstream revision. Add and validate an adapter before building.')
    if not args.decoder.is_file():
        ap.error('Supply an official astcenc executable with --decoder')
    # Verify that every compiled cheat still matches its source text and patch set.
    sys.path.insert(0, str(ROOT / 'tools'))
    from cheats import parse, fnv, cheat_files
    status_file = args.install / 'build-cache/cheats.status'
    status = {r.split('\t')[0]: r.split('\t') for r in status_file.read_text().splitlines()} if status_file.exists() else {}
    patches = (args.cache / 'gen/patches.h').read_text()
    cheats = [cheat for mod, path in cheat_files(args.install / 'mods', adapter['build_id'][:16].upper())
              for cheat in parse(path.read_text(encoding='utf-8-sig'), mod)]
    for cheat in cheats:
        content = fnv(' '.join(f'{w:08X}' for w in cheat.words).encode())
        row = status.get(cheat.key)
        if not row or row[1] != content or row[2] not in ('heading', 'code', 'key', 'master', 'data', 'restore'):
            ap.error('Cached cheats do not match this release: ' + cheat.name)
        if row[2] in ('code', 'key', 'master') and 'TOTK_CHEAT_' + cheat.key not in patches:
            ap.error('Missing compiled cheat patch: ' + cheat.name)
    print('COMPATIBILITY_OK:', release['upstream_tag'], adapter['build_id'], flush=True)
    if args.check_only:
        return
    run(ROOT / 'tools/item_catalog.py', '--romfs', args.install / 'romfs')
    run(ROOT / 'tools/make_item_icon_atlas.py', '--romfs', args.install / 'romfs', '--decoder', args.decoder)
    run(ROOT / 'tools/build_spawn_diagnostic.py', '--setup', args.setup, '--cache', args.cache,
        '--install', args.install, '--targets', ROOT / 'modmenu/adapters' / release['adapter'],
        '--out-name', 'modmenu-release', '--apple-experiment', '--menu-mode', '--beta',
        '--frame-queue', '--beta-version', '0.4', '--icons', '--release-mode',
        *(['--profile-source', args.profile_source] if args.profile_source else []))
    out = ROOT / 'build/modmenu-release'
    config = {
        'release': release, 'game_build_id': adapter['build_id'],
        'exe_sha256': sha256(out / 'totk.exe'),
        'main_sha256': sha256(args.install / 'exefs/main'),
        'install': str(args.install.resolve()), 'python': sys.executable,
        'repo': str(ROOT), 'output': str(out),
    }
    (out / 'release-install.json').write_text(json.dumps(config, indent=2), encoding='utf-8')
    shutil.copy2(ROOT / 'modmenu/assets/modmenu.ico', out / 'modmenu.ico')
    # Use paths from this machine only in ignored installation output.
    launcher = '@echo off\n"' + sys.executable + '" "' + str(ROOT / 'modmenu/launch.py') + '" "' + str(out / 'release-install.json') + '"\nif errorlevel 1 pause\n'
    (out / 'Abrir Mod Menu.cmd').write_text(launcher, encoding='utf-8')
    print('PRIVATE_RELEASE_READY:', out, flush=True)
    print('This folder contains game-derived data. Distribute the source ZIP instead.')


if __name__ == '__main__':
    main()
