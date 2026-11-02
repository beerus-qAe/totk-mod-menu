// Reuse the stub guest call, but exercise the menu queue without holding an item.
#define SPAWN_MENU_MODE
#define main unused_holding_fixture
#include "apple_experiment_test.c"
#undef main
#ifdef SPAWN_FRAME_QUEUE
#define consume(cpu) spawn_menu_frame(cpu,0x1234)
#else
#define consume(cpu) apple_experiment_enter(cpu,0x1234)
#endif

int main(void) {
    wchar_t path[32768]; assert(local_path(path,L"player-position.bin"));
    DeleteFileW(path);
    void *stack=VirtualAlloc(NULL,0x20000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);assert(stack);
    Cpu cpu={0};cpu.sp=(uintptr_t)stack+0x18000;cpu.x[0]=99;
#ifdef SPAWN_FRAME_QUEUE
    uint64_t manager=0x12345678;
    cpu.x[0]=(uintptr_t)&manager;cpu.thread=(void *)1;
    apple_experiment_enter(&cpu,0x1234); // observe manager on the real creation path
#endif
    Cpu before=cpu;
    assert(!spawn_menu_submit("Weapon_Sword_999"));
    assert(spawn_menu_submit("Item_Fruit_A"));
    assert(!spawn_menu_submit("Item_Fruit_A"));
    consume(&cpu);
    assert(calls==0 && !spawn_menu_busy());
    assert(strstr(spawn_menu_status(),"Player indisponivel"));
    unsigned char player[0x400]={0};const char *name="Player";
    uint64_t vt=0x12345678;float pos[3]={400,1641,1334},rot[9]={1,0,0,0,1,0,0,0,1};
    memcpy(player,&vt,8);memcpy(player+0x218,&name,8);
    memcpy(player+0x2b4,pos,sizeof pos);memcpy(player+0x2c0,rot,sizeof rot);
    uint64_t token[6]={0x504c415945523031ull,GetCurrentProcessId(),GetTickCount64(),(uintptr_t)player,(uintptr_t)name,vt};
    FILE *f=_wfopen(path,L"wb");assert(f);fwrite(token,sizeof token,1,f);fclose(f);
    assert(spawn_menu_submit("Item_Fruit_A"));
#ifdef SPAWN_FRAME_QUEUE
    Cpu unrelated=cpu;unrelated.thread=(void *)2;
    spawn_menu_frame(&unrelated,0x1234);assert(calls==0 && spawn_menu_busy());
#endif
    consume(&cpu);
    assert(calls==1 && !spawn_menu_busy() && !memcmp(&cpu,&before,sizeof cpu));
    assert(strstr(spawn_menu_status(),"aceito"));
    expected_actor="Weapon_Sword_001";
    assert(spawn_menu_submit(expected_actor));
    consume(&cpu);assert(calls==2 && !spawn_menu_busy());
    const char *equipment[]={"Weapon_Bow_001","Weapon_Shield_001","Armor_001_Lower"};
    for(unsigned i=0;i<3;++i){
        expected_actor=i==2 ? "TBox_Field_Wood" : equipment[i];
        assert(spawn_menu_submit(equipment[i]));
        consume(&cpu);assert(calls==3+i && !spawn_menu_busy());
    }
    assert(spawn_menu_submit("Item_Fruit_A"));queued_at=GetTickCount64()-31000;
    assert(strstr(spawn_menu_status(),"expirou") && !spawn_menu_busy());
    assert(calls==5);DeleteFileW(path);
    puts("SPAWN_MENU_CHECK_OK: queue, duplicate rejection, missing Player, no holding trigger, completion, timeout");
}
