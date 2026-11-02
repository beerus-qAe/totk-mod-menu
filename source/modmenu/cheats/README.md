# Cheats integration

The module uses the upstream cheat menu and compiled patch-set service. Cheat text
and third-party mods are read from the player's installation, not shipped in the
source release. Code cheats must have been compiled by the matching upstream setup.
The release builder checks their content hashes and patch-set declarations, then
copies their local status manifests and mods into the private output.

Enable individual cheats through F1 > Cheats. This release does not add an infinite
money cheat. Adding a new instruction cheat requires another upstream lift/build;
editing a text file or claiming free shopping is infinite money is insufficient.
