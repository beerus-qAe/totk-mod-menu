"""Apply a source release to a supported, unmodified upstream checkout."""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def apply(package, checkout, check_only=False):
    package, checkout = package.resolve(), checkout.resolve()
    manifest = json.loads((package / 'package.json').read_text())
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=checkout, text=True).strip()
    if head != manifest['upstream_commit']:
        raise ValueError('Unsupported upstream commit. No files changed; a validated adapter is required.')
    payload = package / 'source'
    for relative, expected in manifest['files'].items():
        path = Path(relative)
        if path.is_absolute() or '..' in path.parts or not (payload / path).resolve().is_relative_to(payload):
            raise ValueError('Invalid package path: ' + relative)
        if digest(payload / path) != expected:
            raise ValueError('Package checksum mismatch: ' + relative)
        target = checkout / path
        if not target.resolve().is_relative_to(checkout):
            raise ValueError('Target escapes checkout: ' + relative)
        if target.exists() and digest(target) != expected:
            raise ValueError('Existing local file differs; no files changed: ' + relative)
    patch = package / 'integration.patch'
    if digest(patch) != manifest['patch_sha256']:
        raise ValueError('Integration patch checksum mismatch')
    command = ['git', 'apply', '--whitespace=nowarn']
    subprocess.run([*command, '--check', str(patch)], cwd=checkout, check=True)
    if check_only:
        print('SOURCE_APPLY_CHECK_OK')
        return
    subprocess.run([*command, str(patch)], cwd=checkout, check=True)
    for relative in manifest['files']:
        target = checkout / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(payload / relative, target)
    print('SOURCE_APPLIED. Follow source/modmenu/README.md to build locally.')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--checkout', type=Path, required=True)
    ap.add_argument('--check-only', action='store_true')
    args = ap.parse_args()
    apply(Path(__file__).resolve().parent, args.checkout, args.check_only)


if __name__ == '__main__':
    main()
