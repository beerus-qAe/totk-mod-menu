"""Compile and run module checks against a locally generated release catalog."""
import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--setup', type=Path, required=True)
    args = ap.parse_args()
    clang = args.setup / 'llvm/bin/clang.exe'
    out = ROOT / 'build/checks'
    out.mkdir(parents=True, exist_ok=True)
    release = ROOT / 'build/modmenu-release'
    imgui = ROOT / 'runtime/third_party/imgui'
    flags = ['-O2', '-fuse-ld=lld', '-static', '-iquote', str(ROOT),
             '-I', str(args.setup / 'runtime'), '-I', str(ROOT / 'runtime'),
             '-I', str(imgui), '-I', str(release), '-I', str(args.setup / 'runtime/deps/include')]
    ui = [str(imgui / name) for name in ('imgui.cpp', 'imgui_draw.cpp', 'imgui_tables.cpp', 'imgui_widgets.cpp')]
    jobs = [
        ('release_packet', ['tests/apple_request_test.c']),
        ('release_catalog', ['tests/beta_catalog_test.c']),
        ('release_queue', ['tests/spawn_menu_test.c', '-DSPAWN_BETA_CATALOG', '-DSPAWN_FRAME_QUEUE']),
        ('release_icons', ['-std=c++17', 'tests/item_icons_test.cpp', 'modmenu/runtime/ui/item_icons.cpp', *ui]),
        ('release_window', ['-std=c++17', '-DSPAWN_MENU_MODE', '-DITEM_ICONS_ENABLED', '-DSPAWN_BETA_CATALOG',
                            'tests/items_window_test.cpp', 'modmenu/runtime/ui/item_icons.cpp', *ui]),
    ]
    for name, sources in jobs:
        exe = out / (name + '.exe')
        driver = clang.with_name('clang++.exe') if '-std=c++17' in sources else clang
        command = [str(driver), *flags, *sources, '-o', str(exe)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        (out / (name + '.compile.log')).write_text(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(name + ': see compile log')
        subprocess.run([str(exe)], cwd=release, check=True)
    # The integration must not introduce unresolved module symbols in ordinary builds.
    command = [str(clang), '-std=c++17', '-O1', '-I', str(ROOT / 'runtime'),
               '-I', str(imgui), '-I', str(args.setup / 'runtime/deps/include'),
               '-c', str(ROOT / 'runtime/ui/menu.cpp'), '-o', str(out / 'upstream_menu_without_module.o')]
    subprocess.run(command, cwd=ROOT, check=True)
    print('MODULE_CHECKS_OK: packet, catalog, guest-thread queue, thumbnails, UI, optional integration')


if __name__ == '__main__':
    main()
