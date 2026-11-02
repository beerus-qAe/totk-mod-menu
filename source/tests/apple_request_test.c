// Tests the candidate packet in isolation, not acceptance by the game.
#include <assert.h>
#include <stdio.h>
#include "../modmenu/runtime/spawn/apple_request.h"

int main(void) {
    AppleRequest packet;
    float position[3] = {400.f, 1642.f, 1334.f};
    uint64_t base = 0x10000;
    assert(apple_request_build(&packet, base, position));
    assert(!memcmp(packet.bytes, position, sizeof position));
    assert(!strcmp((char *)packet.bytes + 0x400, "Item_Fruit_A"));
    uint64_t pointer;
    memcpy(&pointer, packet.bytes + 0x100, 8);
    assert(pointer == base + 0x400);
    memcpy(&pointer, packet.bytes + 0x40, 8);
    assert(pointer == base + 0x140 && packet.bytes[0x140] == 0);
    for (int offset = 0x48; offset < 0x90; ++offset) assert(packet.bytes[offset] == 0);
    assert(packet.bytes[0x90] == 7);
    assert(item_request_build(&packet,base,position,"Weapon_Sword_001"));
    assert(!strcmp((char *)packet.bytes+0x400,"Weapon_Sword_001"));
    assert(packet.bytes[0x140]==0);
    assert(!item_request_build(&packet,base,position,"Weapon\nInvalid"));
    assert(item_request_build(&packet,base,position,"SpObj_ElectricBoxGenerator_Capsule_A_01"));
    char oversized[129];memset(oversized,'A',128);oversized[128]=0;
    assert(!item_request_build(&packet,base,position,oversized));
    AppleRequest before = packet;
    position[0] = NAN;
    assert(!apple_request_build(&packet, base, position));
    assert(!memcmp(&packet, &before, sizeof packet));
    position[0] = INFINITY;
    assert(!apple_request_build(&packet, base, position));
    position[0] = 1;
    assert(!apple_request_build(&packet, base + 1, position));
    assert(!apple_request_build(&packet, UINT64_MAX - 15, position));
    assert(!apple_request_build(&packet, 0, position));
    puts("APPLE_PACKET_CHECK_OK: owned strings, detached references, transform, invalid-input rejection");
}
