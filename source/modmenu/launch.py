"""Validate a local installation and launch the game with its Player observer."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from modmenu.compatibility import sha256, validate_game


def verify(config):
    repo, out = Path(config['repo']), Path(config['output'])
    release = json.loads((repo / 'modmenu/release.json').read_text())
    if config['release'] != release:
        raise ValueError('Release metadata changed. Rebuild the local installation.')
    adapter = json.loads((repo / 'modmenu/adapters' / release['adapter']).read_text())
    validate_game(config['install'], adapter)
    for path, expected in ((out / 'totk.exe', config['exe_sha256']),
                           (Path(config['install']) / 'exefs/main', config['main_sha256'])):
        if sha256(path) != expected:
            raise ValueError('Installation changed; rebuild before launching: ' + str(path))
    return repo, out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('config', type=Path)
    ap.add_argument('--check-only', action='store_true')
    args = ap.parse_args()
    config = json.loads(args.config.read_text(encoding='utf-8'))
    repo, out = verify(config)
    if args.check_only:
        print('LAUNCH_COMPATIBILITY_OK')
        return
    # Never copy or overwrite a profile at launch. Each installation owns its profile.
    install = Path(config['install'])
    game = subprocess.Popen([str(out / 'totk.exe'), '--exefs', str(install / 'exefs'),
                             '--romfs', str(install / 'romfs'), '--profile', str(out / 'profile')], cwd=out)
    recording = out / 'position-recording'
    recording.mkdir(exist_ok=True)
    with (recording / 'observer.log').open('ab') as log:
        subprocess.Popen([config['python'], str(repo / 'tools/player_position_probe.py'),
                          '--pid', str(game.pid), '--exe', str(out / 'totk.exe'),
                          '--config', str(out / 'player-config.json'), '--out', str(recording),
                          '--publish', str(out), '--seconds', '0', '--status-only'], cwd=repo,
                         stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
    print('Mod Menu ' + config['release']['version'] + ': F1 > Cheats > Adicionar itens.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError) as error:
        sys.exit('Launch blocked: ' + str(error))
