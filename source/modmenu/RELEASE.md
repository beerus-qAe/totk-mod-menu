# TotK Mod Menu 0.1.0-rc.1

First release candidate with a separate module, version checks and a local build.

Supported: recomp **0.3.1**, TotK **1.4.3**, Windows x64. Future versions require a
validated adapter. This package does not promise compatibility with unknown builds.

The ZIP contains source, an integration patch, instructions and licenses. It contains
no extracted game, recompiled executable, thumbnails, catalog, saves or keys.
The local build generates thumbnails and the catalog from the player's installation.

This is a technical source installation. Obtain an upstream checkout at the exact
supported commit and an original Windows setup with a completed compilation cache.
Read `source/modmenu/README.md` for dependencies and build commands. Check patch
application with `python apply.py --checkout "UPSTREAM_CHECKOUT" --check-only`, then
repeat without `--check-only` to apply. No dependencies are downloaded automatically.

After building, use `build/modmenu-release/Abrir Mod Menu.cmd`, then open
**F1 > Cheats > Adicionar itens**. The existing local compiled cheats are retained;
this candidate does not introduce an infinite-money cheat.

Distribute this source ZIP and its SHA256, not the local compiled folder. Test item
pickup, weapons, bows, shields, clothing chests, thumbnails, repeated requests, cheats
and save/reload before declaring a stable release. This candidate has its own profile.
