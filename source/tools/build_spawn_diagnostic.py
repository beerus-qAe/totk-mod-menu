"""Link a private Windows diagnostic using the installed setup's cached objects.

Generated sources and existing objects are read-only inputs. Selected chunks are
recompiled with a forced header that extends FN_ENTER. No instruction lifting,
function discovery, generated source, or original runtime archive is changed.
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'recomp'))
from nso import Nso
from check_content import GENERATED_MARKER


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--setup', type=Path, required=True)
    ap.add_argument('--install', type=Path, required=True)
    ap.add_argument('--cache', type=Path, required=True)
    ap.add_argument('--targets', type=Path, required=True)
    ap.add_argument('--out-name', default='spawn-diagnostic')
    ap.add_argument('--apple-experiment', action='store_true')
    ap.add_argument('--menu-mode',action='store_true')
    ap.add_argument('--beta',action='store_true')
    ap.add_argument('--frame-queue',action='store_true')
    ap.add_argument('--beta-version',default='0.2')
    ap.add_argument('--icons',action='store_true')
    ap.add_argument('--release-mode', action='store_true', help='Require the supported adapter and cache fingerprints')
    ap.add_argument('--profile-source', type=Path, help='Copy this profile only when output has no profile yet')
    args = ap.parse_args()
    if not re.fullmatch(r'[0-9]+\.[0-9]+',args.beta_version):ap.error('Invalid beta version')
    if args.menu_mode and not args.apple_experiment:
        ap.error('--menu-mode requires --apple-experiment')
    if args.beta and not args.menu_mode:ap.error('--beta requires --menu-mode')
    if args.frame_queue and not args.beta:ap.error('--frame-queue requires --beta')
    if args.icons and not args.beta:ap.error('--icons requires --beta')
    setup, install, cache = args.setup.resolve(), args.install.resolve(), args.cache.resolve()
    if args.release_mode:
        sys.path.insert(0, str(ROOT))
        from modmenu.compatibility import validate_inputs
        release, adapter = validate_inputs(setup, cache, install)
        if not (args.beta and args.frame_queue and args.icons):
            ap.error('Release mode requires beta, frame queue and icons')
        if json.loads(args.targets.read_text()) != adapter:
            ap.error('Release targets must equal the supported adapter')
    if not re.fullmatch(r'(?:spawn-diagnostic(?:-[a-zA-Z0-9]+)?|modmenu-release)', args.out_name):
        ap.error('Output name must be a spawn-diagnostic build folder name')
    out = ROOT / 'build' / args.out_name
    out.mkdir(parents=True, exist_ok=True)
    catalog_ids=[]
    if args.beta:
        catalog_rows=[line.split('\t') for line in (ROOT/'build/item-catalog/items.tsv').read_text(encoding='utf-8').splitlines() if line and not line.startswith('#')]
        catalog_ids=[row[1] for row in catalog_rows]
        chest_ids=[row[1] for row in catalog_rows if row[0] in ('Armaduras','Alimentos','Tecidos','Equipamento de cavalo','Itens especiais')]
        if len(set(catalog_ids))!=len(catalog_ids) or not all(re.fullmatch(r'[A-Za-z0-9_]{1,127}',s) for s in catalog_ids):
            ap.error('Malformed catalog IDs')
        (out/'spawn_catalog_ids.h').write_text('// '+GENERATED_MARKER+': private item catalog; do not commit.\n#pragma once\nstatic const char *const spawn_catalog_ids[]={\n'+',\n'.join(json.dumps(s) for s in catalog_ids)+'\n};\nstatic const char *const spawn_catalog_chest_ids[]={\n'+',\n'.join(json.dumps(s) for s in chest_ids)+'\n};\n')
    source = Nso(install / 'exefs' / 'main')
    targets = json.loads(args.targets.read_text(encoding='utf-8'))
    if source.build_id != targets['build_id']:
        ap.error('Target manifest does not match installed NSO')
    layout = json.loads((cache / 'gen' / 'layout.json').read_text())
    base = int(next(m['base'] for m in layout if m['name'] == 'main'), 16)
    addresses = [base + int(v, 16) for v in targets['offsets']]
    frame_address=None
    if args.frame_queue:
        frame_address=base+int(targets['frame_offset'],16)
        addresses.append(frame_address)
    if len(addresses) > 32 or len(set(addresses)) != len(addresses):
        ap.error('Invalid target count or duplicate targets')
    compiler = setup / 'llvm/bin/clang.exe'
    runtime = setup / 'runtime'
    header = out / 'trace_config.h'
    lines = [f'// {GENERATED_MARKER}: private diagnostic targets. Do not commit.',
             '#include "cpu.h"', 'void spawn_diag_enter(const Cpu *, uint64_t, unsigned);',
             '#undef FN_ENTER', '#define FN_ENTER(a) do { \\',
             'if (__builtin_expect(g_fnprof, 0)) fnprof_hit(a, c->x[30], c->x[0]); \\']
    lines += [f'if ((a) == 0x{address:x}ull) spawn_diag_enter(c, (a), {i}); \\'
              for i, address in enumerate(addresses)]
    lines += ['} while (0)', '']
    if args.apple_experiment:
        if not addresses or addresses[0] != base + 0x599670:
            ap.error('Apple experiment requires the observed 1.4.3 request entry as target zero')
        lines += ['void apple_experiment_enter(Cpu *, uint64_t);', '#undef FN_ENTER',
                  '#define FN_ENTER(a) do { \\',
                  'if (__builtin_expect(g_fnprof, 0)) fnprof_hit(a, c->x[30], c->x[0]); \\']
        lines += [f'if ((a) == 0x{address:x}ull) spawn_diag_enter(c, (a), {i}); \\'
                  for i, address in enumerate(addresses)]
        lines += [f'if ((a) == 0x{addresses[0]:x}ull) apple_experiment_enter(c, (a)); \\', '} while (0)', '']
    if args.beta:lines=[line for line in lines if 'spawn_diag_enter(c,' not in line]
    if args.frame_queue:
        lines.insert(lines.index('#include "cpu.h"')+1,'void spawn_menu_frame(Cpu *, uint64_t);')
        lines.insert(len(lines)-2,f'if ((a) == 0x{frame_address:x}ull) spawn_menu_frame(c, 0x{addresses[0]:x}ull); \\')
    if args.release_mode:
        from modmenu.integration.hooks import release_header
        header.write_text(release_header(addresses[0], frame_address, GENERATED_MARKER))
    else:
        header.write_text('\n'.join(lines))
    selected, found = [], set()
    for path in sorted((cache / 'gen/main').glob('main_*.c')):
        text = path.read_text(encoding='utf-8')
        entries = {int(v, 16) for v in re.findall(r'FN_ENTER\((0x[0-9a-f]+)', text)}
        relevant = entries.intersection(addresses)
        if relevant:
            selected.append(path)
            found.update(relevant)
    if found != set(addresses):
        ap.error('Some requested targets are not generated function entries')
    flags = ['-O1', '-fno-strict-aliasing', '-Wno-return-type', '-Wno-unused-label',
             '-fvisibility=hidden', '-march=x86-64-v3', '-I', str(runtime), '-iquote', str(ROOT), '-I', str(cache / 'gen')]

    def compile_one(path):
        obj = out / (path.stem + '.o')
        command = [str(compiler), *flags, '-include', str(header), '-c', str(path), '-o', str(obj)]
        result = subprocess.run(command, capture_output=True, text=True)
        (out / (path.stem + '.compile.log')).write_text(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(f'Compile failed: {path.name}; see compile log')
        print('Compiled diagnostic chunk:', path.name, flush=True)
        return obj

    print('Compiling', len(selected), 'chunks for', len(addresses), 'entry observations', flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        compiled = list(pool.map(compile_one, selected))
    tracer = out / 'spawn_diag_win.o'
    if not args.release_mode:
        subprocess.run([str(compiler), *flags, '-O2', '-Wall', '-Wextra', '-c',
                        str(ROOT / 'runtime/diagnostics/spawn_diag_win.c'), '-o', str(tracer)], check=True)
    ninja = (cache / 'build/build.ninja').read_text()
    link = next(line for line in ninja.splitlines() if ': link_lib ' in line)
    inputs = link.split(': link_lib ', 1)[1].split(' | ', 1)[0].replace('$ ', '\0').split()
    objects = [(setup / v.replace('\0', ' ')).resolve() for v in inputs]
    replacements = {p.name: p for p in compiled}
    linked = [replacements.get(p.name, p) if p.parent.name == 'main' else p for p in objects]
    missing = [str(p) for p in linked if not p.is_file()]
    if missing:
        raise FileNotFoundError(missing)
    if not args.release_mode:
        linked.append(tracer)
    if args.apple_experiment:
        experiment = out / 'apple_experiment_win.o'
        subprocess.run([str(compiler), *flags, '-O2', '-Wall', '-Wextra', '-c',
                        *(['-DSPAWN_MENU_MODE'] if args.menu_mode else []),
                        *(['-DSPAWN_BETA_CATALOG','-I',str(out)] if args.beta else []),
                        *(['-DSPAWN_FRAME_QUEUE'] if args.frame_queue else []),
                        str(ROOT / 'modmenu/runtime/spawn/apple_experiment_win.c'), '-o', str(experiment)], check=True)
        linked.append(experiment)
    runtime_archive=runtime/'libtotkrt.a'
    if args.menu_mode:
        runtime_archive=out/'libtotkrt-menu.a'
        shutil.copy2(runtime/'libtotkrt.a',runtime_archive)
        ui_objects=[]
        for name in ('menu','menu_win','items_window',*(['item_icons'] if args.icons else [])):
            obj=out/(name+'.o')
            subprocess.run([str(compiler),'-std=c++17','-O2','-Wall','-DSPAWN_MENU_MODE',
                            '-iquote',str(ROOT),'-I',str(ROOT/'runtime'),'-I',str(ROOT/'runtime/third_party/imgui'),
                            *(['-DSPAWN_BETA_CATALOG','-I',str(out)] if args.beta else []),
                            *(['-DSPAWN_FRAME_QUEUE'] if args.frame_queue else []),
                            '-DMODMENU_BETA_LABEL="'+('Mod Menu '+release['version'] if args.release_mode else 'Beta '+args.beta_version)+'"',
                            *(['-DITEM_ICONS_ENABLED'] if args.icons else []),
                            '-I',str(runtime/'deps/include'),'-c',str(ROOT/('runtime/ui' if name in ('menu','menu_win') else 'modmenu/runtime/ui')/(name+'.cpp')),
                            '-o',str(obj)],check=True)
            ui_objects.append(obj)
        subprocess.run([str(setup/'llvm/bin/llvm-ar.exe'),'rcs',str(runtime_archive),*[str(p) for p in ui_objects]],check=True)
    response = out / 'link.rsp'
    response.write_text('\n'.join('"' + str(p).replace('\\', '/') + '"' for p in linked))
    libs = ['-lpsapi', '-lbcrypt', '-luser32', '-lgdi32', '-ldwmapi', '-limm32', '-lwinmm',
            '-lvulkan-1', '-lSDL3', '-lopus', '-l:libvpx.a', '-l:libzstd.a', '-l:libc++.a',
            '-l:libc++abi.a', '-l:libunwind.a', '-l:libwinpthread.a']
    exe = out / 'totk.exe'
    subprocess.run([str(compiler), '-fuse-ld=lld', '-Wl,--stack,16777216', '@' + str(response),
                    '-Wl,--whole-archive', str(runtime_archive), '-Wl,--no-whole-archive',
                    '-L', str(runtime / 'deps/lib'), *libs, '-o', str(exe)], check=True)
    # An independent profile is mandatory even when the executable is launched directly.
    if not (out / 'profile').exists():
        shutil.copytree(args.profile_source or install / 'profile', out / 'profile')
    for pattern in ('*.dll', '*-cache.bin', '*-keys.bin', 'seed-*.bin', 'shader-*.bin',
                    'totk_xlate.*', 'romfs-index.bin'):
        for path in install.glob(pattern):
            shutil.copy2(path, out / path.name)
    for name in ('romfs-patches', 'romfs-patches-xbox', 'romfs-patches-xbox-label'):
        if (install / name).is_dir():
            shutil.copytree(install / name, out / name, dirs_exist_ok=True)
    ini = (install / 'totk.ini').read_text(encoding='utf-8-sig')
    # Disable mod rebuild only in this private copy, so setup cannot replace diagnostics.
    ini += '\n[mods]\nmods_rebuild = off\n'
    (out / 'totk.ini').write_text(ini, encoding='utf-8')
    if args.menu_mode:
        shutil.copy2(ROOT/'build/item-catalog/items.tsv',out/'items.tsv')
        if args.release_mode:
            if (install/'mods').exists():
                # Translation/audio mods can contain names beyond MAX_PATH once
                # placed in an isolated installer workspace. Use extended paths.
                source_mods, destination_mods = str((install/'mods').resolve()), str((out/'mods').resolve())
                if os.name == 'nt':
                    extend = lambda p: p if p.startswith('\\\\?\\') else ('\\\\?\\UNC\\'+p[2:] if p.startswith('\\\\') else '\\\\?\\'+p)
                    source_mods, destination_mods = extend(source_mods), extend(destination_mods)
                shutil.copytree(source_mods,destination_mods,dirs_exist_ok=True)
            for name in ('cheats.status','exefs.status'):
                status=out/'build-cache'/name
                status.parent.mkdir(exist_ok=True)
                if (install/'build-cache'/name).exists():
                    shutil.copy2(install/'build-cache'/name,status)
        else:
            mod=ROOT.parent/'Mod Menu PT-BR'
            shutil.copytree(mod,out/'mods'/mod.name,dirs_exist_ok=True)
    script = out / 'Iniciar diagnostico.ps1'
    quote = lambda s: "'" + str(s).replace("'", "''") + "'"
    script.write_text("$ErrorActionPreference = 'Stop'\nSet-Location -LiteralPath $PSScriptRoot\n" +
                      "& (Join-Path $PSScriptRoot 'totk.exe') --exefs " + quote(install / 'exefs') +
                      ' --romfs ' + quote(install / 'romfs') +
                      " --profile (Join-Path $PSScriptRoot 'profile')\n", encoding='utf-8-sig')
    (out / 'Abrir diagnostico.cmd').write_text(
        '@echo off\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Iniciar diagnostico.ps1"\n',
        encoding='ascii')
    result = {'mode': 'read-only entry logging', 'game_build_id': source.build_id,
              'targets': [hex(a) for a in addresses], 'chunks': [p.name for p in selected],
              'exe_sha256': hashlib.sha256(exe.read_bytes()).hexdigest(),
              'profile': str(out / 'profile'), 'original_executable_modified': False}
    if args.apple_experiment:
        result['mode'] = 'explicitly armed single-apple experiment; game acceptance unverified'
        result['arming_file'] = 'spawn-apple.request'
        result['automatic_injection_on_launch'] = False
    if args.menu_mode:
        result['mode']='menu-requested apple creation on next observed game-thread creation entry'
        result['arming_file']=None
        result['currently_enabled_items']=['Item_Fruit_A','Weapon_Sword_001','Weapon_Bow_001','Weapon_Shield_001','Armor_001_Lower']
        result['equipment_validation']='apple and sword user-confirmed; bow, shield and trousers pending'
    if args.beta:
        result['mode']='private mod menu beta 0.1; full catalog enabled, not individually validated'
        result['currently_enabled_items']=catalog_ids
        result['catalog_count']=len(catalog_ids)
        result['clothing_delivery']='chest'
        result['creation_history']='spawn-history.jsonl'
        if args.release_mode:
            (out/'player-config.json').write_text(json.dumps(adapter['player'],indent=2))
        else:
            shutil.copy2(ROOT/'build/player-position/config.json',out/'player-config.json')
        beta_script=ROOT/'tools/start_beta.ps1'
        minor=int(args.beta_version.split('.')[1])
        previous='spawn-diagnostic-beta'+str(minor-1) if minor>=3 else 'spawn-diagnostic-beta'
        parameters=' -BuildName '+out.name+' -SourceBuild '+previous if args.frame_queue else ''
        (out/'Abrir Mod Menu Beta.cmd').write_text('@echo off\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "'+str(beta_script)+'"'+parameters+'\nif errorlevel 1 pause\n',encoding='ascii')
    if args.frame_queue:
        result['beta_version']=args.beta_version
        result['queue_consumer']='recurring guest frame, matching an observed creation guest-thread context'
    if args.icons:
        for name in ('item-icons.rgba','item-icons.tsv'):
            shutil.copy2(ROOT/'build/icon-atlas'/name,out/name)
        result['real_thumbnail_count']=len((ROOT/'build/icon-atlas/item-icons.tsv').read_text().splitlines())
    if args.release_mode:
        result.update(mode='local release candidate', release=release,
                      equipment_validation='apple, sword, bow, shield and clothing user-confirmed in beta; release regression pending')
        for name in ('Iniciar diagnostico.ps1','Abrir diagnostico.cmd','Abrir Mod Menu Beta.cmd'):
            (out/name).unlink(missing_ok=True)
    (out / 'diagnostic-build.json').write_text(json.dumps(result, indent=2))
    print('RELEASE_BUILD_OK:' if args.release_mode else 'DIAGNOSTIC_BUILD_OK:', exe)


if __name__ == '__main__':
    main()
