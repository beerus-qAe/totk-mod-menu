#pragma once
#include <string.h>
#ifdef SPAWN_BETA_CATALOG
#include "spawn_catalog_ids.h"
#endif
// 1: user-validated item; 2: enabled for the next equipment test.
static inline int spawn_menu_item_support(const char *actor) {
    if(!actor)return 0;
    if(!strcmp(actor,"Item_Fruit_A") || !strcmp(actor,"Weapon_Sword_001") || !strcmp(actor,"Weapon_Bow_001") || !strcmp(actor,"Weapon_Shield_001"))return 1;
#ifdef SPAWN_BETA_CATALOG
    for(unsigned i=0;i<sizeof spawn_catalog_ids/sizeof spawn_catalog_ids[0];++i)
        if(!strcmp(actor,spawn_catalog_ids[i]))return 2;
#else
    if(!strcmp(actor,"Armor_001_Lower"))return 2;
#endif
    return 0;
}
static inline int spawn_menu_item_chest(const char *actor) {
    if(!actor)return 0;
#ifdef SPAWN_BETA_CATALOG
    for(unsigned i=0;i<sizeof spawn_catalog_chest_ids/sizeof spawn_catalog_chest_ids[0];++i)
        if(!strcmp(actor,spawn_catalog_chest_ids[i]))return 1;
    return 0;
#else
    return !strncmp(actor,"Armor_",6);
#endif
}
#ifdef __cplusplus
extern "C" {
#endif
int spawn_menu_submit(const char *actor);
int spawn_menu_busy(void);
const char *spawn_menu_status(void);
#ifdef __cplusplus
}
#endif
