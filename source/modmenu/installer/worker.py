"""Local-only installer orchestration; the original game and setup are read-only."""
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid


def game_running():
    class Entry(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('usage', wintypes.DWORD), ('pid', wintypes.DWORD),
                    ('heap', ctypes.c_size_t), ('module', wintypes.DWORD), ('threads', wintypes.DWORD),
                    ('parent', wintypes.DWORD), ('priority', wintypes.LONG), ('flags', wintypes.DWORD),
                    ('exe', wintypes.WCHAR * 260)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(Entry)]
    kernel.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(Entry)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateToolhelp32Snapshot(2, 0)
    if handle == ctypes.c_void_p(-1).value:
        raise OSError('Nao foi possivel verificar se o jogo esta aberto.')
    try:
        entry = Entry(); entry.size = ctypes.sizeof(entry)
        more = kernel.Process32FirstW(handle, ctypes.byref(entry))
        while more:
            if entry.exe.lower() == 'totk.exe':
                return True
            more = kernel.Process32NextW(handle, ctypes.byref(entry))
        return False
    finally:
        kernel.CloseHandle(handle)


def run(command, cwd, log):
    with subprocess.Popen(list(map(str, command)), cwd=cwd, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace',
                          creationflags=subprocess.CREATE_NO_WINDOW) as process:
        for line in process.stdout:
            log(line.rstrip())
        if process.wait():
            raise RuntimeError('Uma etapa falhou. Consulte o registro acima; a instalacao original foi preservada.')


def cache_candidates(setup, install):
    result = []
    for root in (setup / 'temp', install / 'build-cache'):
        if (root / 'gen/layout.json').is_file() and (root / 'build/build.ninja').is_file():
            result.append(root)
        if root.is_dir():
            for candidate in sorted(root.iterdir()):
                if candidate.is_dir() and (candidate / 'gen/layout.json').is_file() and (candidate / 'build/build.ninja').is_file():
                    result.append(candidate)
    return result


def install(payload, setup, game, destination, log=print, check_only=False):
    payload, setup, game, destination = map(lambda p: Path(p).resolve(), (payload, setup, game, destination))
    if game_running():
        raise ValueError('Salve e feche o jogo antes de instalar o Mod Menu.')
    for relative in ('totk.exe', 'exefs/main', 'romfs/index.json', 'romfs/romfs.bin'):
        if not (game / relative).is_file():
            raise ValueError('Pasta do jogo incompleta: falta ' + relative)
    for relative in ('python/python.exe', 'llvm/bin/clang.exe', 'runtime/libtotkrt.a'):
        if not (setup / relative).is_file():
            raise ValueError('Selecione a pasta do setup original: falta ' + relative)
    # Validate all source/dependency files before using or copying the payload.
    manifest = json.loads((payload / 'payload.json').read_text())
    for relative, expected in manifest['files'].items():
        path = (payload / relative).resolve()
        if not path.is_relative_to(payload) or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('O instalador esta incompleto ou alterado: ' + relative)
    source = payload / 'source'
    sys.path.insert(0, str(source))
    from modmenu.compatibility import validate_inputs
    cache = None
    for candidate in cache_candidates(setup, game):
        try:
            validate_inputs(setup, candidate, game)
            cache = candidate
            break
        except (ValueError, OSError) as error:
            log('Cache ignorado: ' + str(error))
    if cache is None:
        raise ValueError('Cache compativel nao encontrado. Conclua a compilacao no setup 0.3.1 e mantenha sua pasta temp.')
    log('Compatibilidade confirmada. Cache: ' + str(cache))
    if check_only:
        return {'cache': str(cache), 'game': str(game), 'setup': str(setup)}
    # Each attempt has its own workspace. A failed attempt cannot replace a working install.
    identity = hashlib.sha256(str(game).casefold().encode()).hexdigest()[:12]
    home = destination / identity
    home.mkdir(parents=True, exist_ok=True)
    latest = home / 'latest.json'
    profile = game / 'profile'
    if latest.is_file():
        previous = json.loads(latest.read_text())
        previous_profile = Path(previous['output']) / 'profile'
        if previous_profile.is_dir():
            profile = previous_profile
    workspace = home / ('install-' + uuid.uuid4().hex[:12])
    log('Preparando codigo e ferramentas locais...')
    shutil.copytree(source, workspace)
    shutil.copytree(payload / 'deps', workspace / 'build/icon-python-deps')
    decoder = workspace / 'build/tools/astcenc-sse2.exe'
    decoder.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(payload / 'tools/astcenc-sse2.exe', decoder)
    python = setup / 'python/python.exe'
    log('Gerando catalogo, miniaturas e executavel. Esta etapa pode levar alguns minutos...')
    command = [python, '-X', 'utf8', '-u', workspace / 'tools/build_modmenu_release.py', '--setup', setup,
               '--cache', cache, '--install', game, '--decoder', decoder,
               '--source-manifest', workspace / 'source-manifest.json']
    if profile.is_dir():
        command += ['--profile-source', profile]
    run(command, workspace, log)
    output = workspace / 'build/modmenu-release'
    run([python, workspace / 'modmenu/launch.py', output / 'release-install.json', '--check-only'], workspace, log)
    # Commit the pointer only after every build and launch check succeeds.
    receipt = dict(output=str(output), workspace=str(workspace), setup=str(setup), game=str(game))
    temporary = home / 'latest.tmp'
    temporary.write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    temporary.replace(latest)
    log('INSTALACAO_CONCLUIDA: ' + str(output / 'Abrir Mod Menu.cmd'))
    return receipt


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('payload', 'setup', 'game', 'destination'):
        ap.add_argument('--' + name, type=Path, required=True)
    ap.add_argument('--check-only', action='store_true')
    args = ap.parse_args()
    install(args.payload, args.setup, args.game, args.destination, check_only=args.check_only)


if __name__ == '__main__':
    if sys.stdout:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
    main()
