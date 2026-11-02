"""Fail closed before using version-specific game hooks or cached runtime code."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def validate_game(install, adapter):
    expected = adapter['build_id']
    # NSO build IDs are padded to 32 bytes. Compare the complete padded field.
    with (Path(install) / 'exefs/main').open('rb') as source:
        header = source.read(0x60)
    if header[:4] != b'NSO0' or header[0x40:0x60].hex() != expected.ljust(64, '0'):
        raise ValueError('Unsupported game build. This release requires TotK 1.4.3.')


def validate_inputs(setup, cache, install):
    release = json.loads((ROOT / 'modmenu/release.json').read_text())
    adapter = json.loads((ROOT / 'modmenu/adapters' / release['adapter']).read_text())
    validate_game(install, adapter)
    lock = json.loads((ROOT / 'modmenu/adapters/setup-0.3.1-lock.json').read_text())
    for location, entries in lock.items():
        base = Path(setup if location == 'setup' else cache)
        for relative, expected in entries.items():
            path = base / relative
            if not path.is_file() or sha256(path) != expected:
                raise ValueError('Unsupported or modified recomp cache: ' + str(path))
    # The upstream loader enforces these hashes at runtime, including direct exe
    # launches. Check cached link metadata before compiling as well.
    modules = (Path(cache) / 'build/modules.c').read_text()
    if sha256(Path(install) / 'exefs/main') not in modules:
        raise ValueError('Cached game objects belong to a different ExeFS main module.')
    return release, adapter
