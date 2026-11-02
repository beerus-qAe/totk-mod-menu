#pragma once
#include "imgui.h"
// Add real cached icons to the existing font texture before its Vulkan upload.
void item_icons_build(ImFontAtlas *atlas);
bool item_icons_draw(const char *actor,ImVec2 position,float size);
