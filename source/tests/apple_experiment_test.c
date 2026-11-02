// Run the arming and invocation path with a stub game function, never the game.
#include <assert.h>
#include <stdarg.h>
#include <stdlib.h>
#include "../modmenu/runtime/spawn/apple_experiment_win.c"

static unsigned calls;
static const char *expected_actor="Item_Fruit_A";
void *mem_kernel_alloc(uint64_t size, uint64_t align) {
    (void)align;
    return VirtualAlloc(NULL, size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
}
uint64_t rt_call(Cpu *c, uint64_t fn, int n, ...) {
    assert(fn == 0x1234 && n == 8);
    uint64_t args[8];
    va_list ap; va_start(ap, n);
    for (int i = 0; i < n; ++i) args[i] = va_arg(ap, uint64_t);
    va_end(ap);
    assert(!strcmp(*(const char **)(uintptr_t)args[1], expected_actor));
    unsigned char *packet = (unsigned char *)(uintptr_t)args[2];
    float world[3]; memcpy(world, packet, sizeof world);
    assert(world[0] == 400.f && world[1] == 1642.f && world[2] == 1335.5f);
    for (int i = 0x48; i < 0x90; ++i) {
        if(!strcmp(expected_actor,"TBox_Field_Wood") && i>=0x58 && i<0x60)continue;
        assert(!packet[i]);
    }
    if(!strcmp(expected_actor,"TBox_Field_Wood")) {
        assert(!strcmp((char *)packet+0x22c,"Drop__DropActor"));
        assert(!strcmp((char *)packet+0x500,"Armor_001_Lower"));
    }
    assert(args[3] == 0 && args[4] == 1 && args[5] == 0 && args[6] == 0 && args[7] == 0);
    uint64_t *stack = (uint64_t *)(uintptr_t)c->sp;
    assert(stack[0] == 0);
    *(uint32_t *)(uintptr_t)stack[1] = 1;
    *(uint64_t *)(uintptr_t)stack[2] = 0x5678;
    ++calls;
    memset(c->x, 0x55, sizeof c->x); // must not affect the original Cpu
    return 1;
}
int main(void) {
    unsigned char parent[0x400] = {0}, create[0x98] = {0};
    const char *actor = "CarryBox", *apple = "Item_Fruit_A";
    memcpy(parent + 0x218, &actor, 8);
    float pos[3] = {400,1641,1334}, rot[9] = {1,0,0,0,1,0,0,0,1};
    memcpy(parent + 0x2b4, pos, sizeof pos);
    memcpy(parent + 0x2c0, rot, sizeof rot);
    uint64_t p = (uintptr_t)parent; memcpy(create + 0x68, &p, 8);
    void *stack = VirtualAlloc(NULL, 0x20000, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    assert(stack);
    Cpu original = {0};
    original.sp = (uintptr_t)stack + 0x18000;
    original.x[0] = 99;
    original.x[1] = (uintptr_t)&apple;
    original.x[2] = (uintptr_t)create;
    Cpu before = original;
    wchar_t path[32768]; assert(local_path(path, L"spawn-apple.request"));
    DeleteFileW(path);
    apple_experiment_enter(&original, 0x1234); assert(calls == 0);
    FILE *file = _wfopen(path, L"w"); assert(file); fclose(file);
    wchar_t hint_path[32768]; assert(local_path(hint_path,L"player-position.bin"));
    DeleteFileW(hint_path);
    apple_experiment_enter(&original, 0x1234);
    assert(calls == 0); // CarryBox cannot supply position without a fresh Player identity.
    unsigned char player[0x400] = {0};
    const char *player_name = "Player";
    uint64_t vtable = 0x12345678;
    memcpy(player, &vtable, 8);
    memcpy(player + 0x218, &player_name, 8);
    memcpy(player + 0x2b4, pos, sizeof pos);
    memcpy(player + 0x2c0, rot, sizeof rot);
    memset(parent + 0x2b4, 0, 12); // incorrect local coordinates must be ignored
    uint64_t token[6] = {0x504c415945523031ull,GetCurrentProcessId()+1,GetTickCount64(),
                         (uintptr_t)player,(uintptr_t)player_name,vtable};
    file = _wfopen(hint_path,L"wb");assert(file);fwrite(token,sizeof token,1,file);fclose(file);
    apple_experiment_enter(&original,0x1234);assert(calls==0);
    token[1]=GetCurrentProcessId(); token[2]=GetTickCount64()-3000;
    file = _wfopen(hint_path,L"wb");assert(file);fwrite(token,sizeof token,1,file);fclose(file);
    apple_experiment_enter(&original,0x1234);assert(calls==0);
    token[2]=GetTickCount64();
    file = _wfopen(hint_path,L"wb");assert(file);fwrite(token,sizeof token,1,file);fclose(file);
    errno = EDOM; SetLastError(456);
    apple_experiment_enter(&original, 0x1234);
    assert(calls == 1 && !memcmp(&before, &original, sizeof original));
    assert(errno == EDOM && GetLastError() == 456);
    assert(GetFileAttributesW(path) == INVALID_FILE_ATTRIBUTES);
    apple_experiment_enter(&original, 0x1234); assert(calls == 1);
    DeleteFileW(hint_path);
    puts("APPLE_EXPERIMENT_CHECK_OK: explicit arming, one call, detached packet, isolated Cpu, state preserved");
    return 0;
}
