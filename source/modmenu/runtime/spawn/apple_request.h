// Owned candidate packet for the observed 1.4.3 request layout. Building a packet
// does not establish that the game accepts it; no captured pointers are retained.
#pragma once
#include <math.h>
#include <stdint.h>
#include <string.h>
#include "spawn_menu.h"

typedef struct {
    unsigned char bytes[0x600];
    uint64_t name_object, creation_arg, result, preactor;
} AppleRequest;

static inline void apple_store64(unsigned char *p, uint64_t v) { memcpy(p, &v, sizeof v); }

// guest_base must refer to reserved, writable guest scratch memory. The caller
// owns allocation, execution on a suitable game thread, completion and lifetime.
static inline int item_request_build(AppleRequest *out, uint64_t guest_base,
                                      const float world_position[3], const char *actor) {
    if (!actor) return 0;
    size_t length = 0;
    while(actor[length] && length < 128) {
        unsigned char c=actor[length];
        if(!((c>='A'&&c<='Z')||(c>='a'&&c<='z')||(c>='0'&&c<='9')||c=='_'))return 0;
        ++length;
    }
    if(!length || length>=128)return 0;
    if (!out || !world_position || !guest_base || (guest_base & 15) ||
        guest_base > UINT64_MAX - sizeof out->bytes) return 0;
    for (int i = 0; i < 3; ++i)
        if (!isfinite(world_position[i]) || fabsf(world_position[i]) > 100000.f) return 0;
    AppleRequest packet = {0};
    memcpy(packet.bytes, world_position, 12);
    const float identity[9] = {1,0,0, 0,1,0, 0,0,1};
    const float scale[3] = {1,1,1};
    memcpy(packet.bytes + 0x0c, identity, sizeof identity);
    memcpy(packet.bytes + 0x30, scale, sizeof scale);
    // The optional string and actor name refer only to this packet's own storage.
    apple_store64(packet.bytes + 0x40, guest_base + 0x140);
    packet.bytes[0x90] = 7; // explicit position, rotation and scale
    apple_store64(packet.bytes + 0x100, guest_base + 0x400);
    memcpy(packet.bytes + 0x400, actor, length+1);
    packet.name_object = guest_base + 0x100;
    packet.creation_arg = guest_base;
    packet.result = guest_base + 0x180;
    packet.preactor = guest_base + 0x188;
    *out = packet;
    return 1;
}

static inline int apple_request_build(AppleRequest *out,uint64_t base,const float position[3]) {
    return item_request_build(out,base,position,"Item_Fruit_A");
}

// Serialize one string instance parameter in owned guest-visible storage.
// The chest's own 1.4.3 parameter table declares Drop__DropActor as String128.
static inline int item_delivery_build(AppleRequest *out,uint64_t base,const float position[3],const char *actor) {
    if(!spawn_menu_item_chest(actor))return item_request_build(out,base,position,actor);
    size_t length=0;
    while(actor[length] && length<128) {
        unsigned char c=actor[length];
        if(!((c>='A'&&c<='Z')||(c>='a'&&c<='z')||(c>='0'&&c<='9')||c=='_'))return 0;
        ++length;
    }
    if(length<7 || length>=128)return 0;
    AppleRequest packet;
    if(!item_request_build(&packet,base,position,"TBox_Field_Wood"))return 0;
    apple_store64(packet.bytes+0x58,base+0x200);
    uint32_t one=1;
    memcpy(packet.bytes+0x200,&one,4); // parameter buffer capacity
    apple_store64(packet.bytes+0x208,base+0x218);
    memcpy(packet.bytes+0x210,&one,4); // active parameter count
    memcpy(packet.bytes+0x218,&one,4); // string parameter tag
    apple_store64(packet.bytes+0x220,base+0x22c);
    uint32_t key_size=sizeof "Drop__DropActor";
    memcpy(packet.bytes+0x228,&key_size,4);
    memcpy(packet.bytes+0x22c,"Drop__DropActor",key_size);
    apple_store64(packet.bytes+0x2b0,base+0x500);
    memcpy(packet.bytes+0x500,actor,strlen(actor)+1);
    *out=packet;
    return 1;
}
