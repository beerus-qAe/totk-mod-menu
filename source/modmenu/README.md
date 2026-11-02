# TotK Mod Menu 0.1.0-rc.1

A source release for Windows x86-64, upstream recomp v0.3.1 at
`ab1dee5bdb9089399b2000880eaa8f702a846f89`, and TotK 1.4.3 build
`277178b7dba1b6d4949a84778d4abc58b31b34f5`. Other versions are rejected.
This is a release candidate, not a plugin ABI or a universally compatible binary.

## Layout

- `runtime/ui`: searchable catalog, native item window and real thumbnail cache.
- `runtime/spawn`: request serialization, chest delivery and guest-thread queue.
- `integration/ui.h`: the upstream menu bridge, with stubs for ordinary builds.
- `integration/hooks.py`: creation observation and recurring frame hook generation.
- `adapters`: supported build IDs, entry offsets, Player layout and setup fingerprints.
- `cheats`: delegates to upstream services and locally supplied cheat files.
- `compatibility.py`, `launch.py`: installation and launch validation.

The integration patch changes three upstream UI files for text entry, modal behavior,
the item button and font-atlas registration. The runtime library is copied privately;
only the two upstream UI objects and module UI objects are replaced in that copy.
Lifted C is not edited. A forced header instruments generated function entries.

## Install from a source ZIP

1. Extract the ZIP into a separate folder. Obtain an upstream checkout at the exact
   commit above. Git, the upstream Windows 0.3.1 setup, its LLVM/Python/dependencies,
   an extracted 1.4.3 game and a completed setup compilation cache are required.
2. Check then apply the patch: `python apply.py --checkout "PATH_TO_UPSTREAM" --check-only`,
   followed by the same command without `--check-only`. Different upstream revisions,
   conflicting local files and patch/checksum failures stop before modification.
3. Use the setup's Python 3.14. Install `modmenu/requirements-build.txt` into that
   environment, or provide those packages through a dedicated environment/PYTHONPATH.
   Supply an official Arm astcenc 5.7.0 Windows executable separately. Tools are not
   downloaded automatically and their licenses remain with their distributions.
4. From the patched checkout, run (replace every placeholder with a local path):

```powershell
& "SETUP/python/python.exe" tools/build_modmenu_release.py `
  --setup "SETUP" --cache "COMPLETED_SETUP_CACHE" `
  --install "INSTALLED_GAME" --decoder "ASTCENC.exe" --check-only
```

5. Repeat without `--check-only` to generate the local catalog and thumbnails and
   compile/link `build/modmenu-release/totk.exe`. Optionally pass
   `--profile-source "YOUR_CHOSEN_PROFILE"` for the initial save copy. Close the game
   before copying a profile. An existing release profile is never overwritten.
6. Open `build/modmenu-release/Abrir Mod Menu.cmd`. Keep the source checkout and the
   original extracted game in place: the launcher uses their local paths.

The cache is a prerequisite from the original setup, not supplied by this package.
Its base runtime headers/archive and layout must match the supported setup. Cached
link metadata must contain the supplied main module's SHA256. Locally installed
cheats must match compiled patch sets; unsupported or stale cheats require rebuilding
with upstream setup first. Do not run upstream auto-rebuild over this executable.
There is no automatic installer for a clean machine or extraction/key management.

## Updating the recomp

Start with a new upstream checkout and rebase the small UI patch. Add a new release
support record and setup fingerprints after reviewing CPU/runtime ABI changes. For a
new game build, discover and validate the creation/frame entries, Player layout and
delivery structures; add a separate adapter rather than reusing old offsets blindly.
Rebuild, run serialization/queue/UI/compatibility checks, then test real item pickup,
equipment, chest delivery, repeated requests and save/reload. Only then declare the
version supported. A changed tag alone is not evidence of compatibility.

## Distribution

Run `python tools/package_modmenu_release.py`. Distribute only the source ZIP and its
SHA256 under `build/releases`. Packaging uses an allowlist and the upstream game-content
scanner; it excludes all private build files, icons, item names, saves, ROMs, keys,
cached objects and the generated executable. The install output remains private.
The MIT license and notices are included. No game assets are granted a new license.

Runtime module files keep the existing experimental item routes: not every catalog
entry is individually verified. The prior beta's successful play tests are evidence
for those tested items only; this release still requires its own gameplay regression.

## Checks

After generating the local build, run:

```powershell
python tools/check_modmenu_release.py --setup "SETUP"
python tools/package_modmenu_release.py
python tests/modmenu_release_test.py
& "SETUP/python/python.exe" modmenu/launch.py build/modmenu-release/release-install.json --check-only
```

The module checks cover packet ownership, all catalog delivery routes, wrong-thread
rejection and queue completion, real icon font rebuilds, search/modal UI and compiling
the upstream menu without the optional module. Package tests apply the actual ZIP's
patch to original upstream files and reject changed game/cache/executable inputs.
