# Standalone installer

`tools/build_modmenu_installer.py --setup PATH` builds a Windows GUI executable in
`build/releases`. It embeds an allowlisted upstream source snapshot with the module
overlay, source checksums, Pillow/FontTools distributions and licenses, and the
official Arm astcenc SSE2 decoder and Apache license. It contains no game-derived
assets or executable. Developer inputs are prepared under ignored `build/icon-*`
folders; the official astcenc archive's SHA256 is checked before embedding.

At runtime the native bootstrap finds the original setup beside the installer or
on the Desktop, or asks for its folder. The setup supplies Python/Tk and LLVM; Git,
system Python, administrator privileges and network downloads are unnecessary.
The GUI asks for the installed game and lets the user correct the setup path.
The game must be closed. The cache is discovered and compatibility checked before
creating an installation workspace. The current release supports only the pinned
0.3.1 setup/runtime and game build 1.4.3, using the x86-64-v3 build configuration.

Each attempt creates a new isolated source/build workspace under
`%LOCALAPPDATA%/TotKModMenu/installations`. Catalog and real thumbnails are generated
from the player's existing RomFS. Mods and profiles are copied locally. Reinstalling
imports the prior successful Mod Menu profile when available; the original game
files, executable and saves remain read-only inputs. The successful installation
pointer is updated only after build and launch-compatibility checks pass.

The GUI creates a Desktop shortcut and offers to launch the mod. Logs are saved in
`%LOCALAPPDATA%/TotKModMenu/logs`. Failed attempts are kept for diagnosis and never
replace the previous successful pointer. Closing the GUI during a build is blocked
to avoid abandoning compiler subprocesses. There is no in-progress cancellation.

Validation: native `--selftest`, native payload extraction using `--extract-only PATH`,
Tk `gui.py --setup PATH --selftest`, and `tests/modmenu_installer_test.py`. The worker
also supports a headless `--check-only` and a complete isolated install test. These
do not start gameplay or claim real in-game validation of the newly installed build.
