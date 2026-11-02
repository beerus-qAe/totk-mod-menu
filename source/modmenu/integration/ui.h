// The only UI bridge included by the upstream menu. Ordinary upstream builds
// remain usable without linking the optional module.
#pragma once
#ifdef SPAWN_MENU_MODE
#include "../runtime/ui/items_window.h"
#ifdef ITEM_ICONS_ENABLED
#include "../runtime/ui/item_icons.h"
#endif
#else
static inline bool items_modal() { return false; }
static inline void items_button() {}
static inline void items_window(float) {}
#endif
