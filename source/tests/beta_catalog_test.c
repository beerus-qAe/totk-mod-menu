// Check every private catalog entry can be serialized without touching the game.
#define SPAWN_BETA_CATALOG
#include <assert.h>
#include <stdio.h>
#include "modmenu/runtime/spawn/spawn_menu.h"
#include "modmenu/runtime/spawn/apple_request.h"
int main(void){
    unsigned count=sizeof spawn_catalog_ids/sizeof spawn_catalog_ids[0],chests=0;
    float position[3]={400,1640,1334};
    for(unsigned i=0;i<count;++i){
        const char *id=spawn_catalog_ids[i];AppleRequest packet;
        assert(spawn_menu_item_support(id));
        assert(item_delivery_build(&packet,0x10000,position,id));
        if(spawn_menu_item_chest(id)){
            ++chests;
            assert(!strcmp((char *)packet.bytes+0x400,"TBox_Field_Wood"));
            assert(!strcmp((char *)packet.bytes+0x500,id));
        }else assert(!strcmp((char *)packet.bytes+0x400,id));
        assert(!packet.bytes[0x140]);
    }
    assert(count>=1048 && chests>0);
    assert(spawn_menu_item_support("Obj_ArrowNormal_A_01"));
    assert(spawn_menu_item_support("Obj_ArrowBundle_A_01"));
    assert(spawn_menu_item_support("Obj_ArrowBundle_A_02"));
    assert(!spawn_menu_item_support("NormalArrow"));
    assert(spawn_menu_item_support("BombFruit"));
    assert(spawn_menu_item_support("SpObj_ElectricBoxGenerator_Capsule_A_01"));
    assert(spawn_menu_item_support("SpObj_Cannon_Capsule_A_01"));
    assert(!spawn_menu_item_support("Item_NotInCatalog"));
    assert(!spawn_menu_item_support("Armor_NotInCatalog"));
    printf("BETA_CATALOG_CHECK_OK: %u items serialized, %u chest-delivered entries\n",count,chests);
}
