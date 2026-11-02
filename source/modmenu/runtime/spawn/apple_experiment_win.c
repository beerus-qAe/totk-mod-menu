// Explicitly armed, single-apple experiment. Called only on a fresh observed
// holding request, on its existing game thread. Not linked by ordinary builds.
#ifdef _WIN32
#include <windows.h>
#include <stdio.h>
#include <errno.h>
#include <fenv.h>
#include <wchar.h>
#include "host.h"
#include "apple_request.h"
#include "spawn_menu.h"

static __thread int entering;
#ifndef SPAWN_MENU_MODE
static volatile LONG attempted;
#endif
#ifdef SPAWN_MENU_MODE
static volatile LONG pending, menu_state;
static ULONGLONG queued_at;
static char selected_actor[128];
int spawn_menu_submit(const char *actor) {
    if (!spawn_menu_item_support(actor) || InterlockedCompareExchange(&pending,2,0)) return 0;
    strcpy(selected_actor,actor);
    queued_at=GetTickCount64();
    InterlockedExchange(&menu_state,1);
    InterlockedExchange(&pending,1);
    return 1;
}
int spawn_menu_busy(void) { return InterlockedCompareExchange(&pending,0,0)!=0; }
const char *spawn_menu_status(void) {
    if (spawn_menu_busy() && GetTickCount64()-queued_at>30000 && InterlockedCompareExchange(&pending,0,1)==1)
        InterlockedExchange(&menu_state,5);
    switch(InterlockedCompareExchange(&menu_state,0,0)) {
    case 1:return "Pedido na fila. Aguardando o jogo...";
    case 2:return "Criando item perto do Link...";
    case 3:return "Pedido aceito pelo jogo. Procure o item perto do Link.";
    case 4:return "O jogo recusou o pedido de criacao.";
    case 5:return "Pedido expirou. Tente novamente com a partida carregada.";
    case 6:return "Player indisponivel. Aguarde a captura de posicao.";
    default:return "Pronto. Crie um item por vez e recolha-o no jogo.";
    }
}
#endif

static int read_exact(uint64_t address, void *out, size_t count) {
    SIZE_T got = 0;
    return address && ReadProcessMemory(GetCurrentProcess(), (void *)(uintptr_t)address, out, count, &got) && got == count;
}

static int local_path(wchar_t *path, const wchar_t *name) {
    DWORD size = GetModuleFileNameW(NULL, path, 32768);
    if (!size || size > 32700) return 0;
    wchar_t *end = wcsrchr(path, L'\\');
    if (!end) return 0;
    wcscpy(end + 1, name);
    return 1;
}

#ifdef SPAWN_FRAME_QUEUE
static SRWLOCK context_lock=SRWLOCK_INIT;
static struct { void *thread; uint64_t manager,vtable; } contexts[32];
static void remember_context(const Cpu *cpu) {
    uint64_t vtable;
    if(entering || !cpu->thread || !read_exact(cpu->x[0],&vtable,8) || !vtable)return;
    AcquireSRWLockExclusive(&context_lock);
    for(unsigned i=0;i<32;++i) {
        if(!contexts[i].thread || contexts[i].thread==cpu->thread) {
            contexts[i].thread=cpu->thread;contexts[i].manager=cpu->x[0];contexts[i].vtable=vtable;break;
        }
    }
    ReleaseSRWLockExclusive(&context_lock);
}
#endif

static int player_world(float position[3], float rotation[9]) {
    wchar_t path[32768];
    if (!local_path(path, L"player-position.bin")) return 0;
    FILE *file = _wfopen(path, L"rb");
    if (!file) return 0;
    uint64_t token[6];
    int ok = fread(token, sizeof token, 1, file) == 1;
    fclose(file);
    uint64_t now = GetTickCount64();
    if (!ok || token[0] != 0x504c415945523031ull || token[1] != GetCurrentProcessId() ||
        token[2] > now || now - token[2] > 2000) return 0;
    uint64_t vtable, name_pointer;
    char name[7];
    if (!read_exact(token[3], &vtable, 8) || vtable != token[5] ||
        !read_exact(token[3] + 0x218, &name_pointer, 8) || name_pointer != token[4] ||
        !read_exact(name_pointer, name, sizeof name) || memcmp(name, "Player", 7) ||
        !read_exact(token[3] + 0x2b4, position, 12) ||
        !read_exact(token[3] + 0x2c0, rotation, 36)) return 0;
    for (int i = 0; i < 3; ++i)
        if (!isfinite(position[i]) || fabsf(position[i]) > 100000.f) return 0;
    for (int i = 0; i < 9; ++i) if (!isfinite(rotation[i])) return 0;
    return 1;
}

static void apple_experiment_run(Cpu *original, uint64_t entry) {
#ifdef SPAWN_MENU_MODE
    if (entering || InterlockedCompareExchange(&pending,0,0)!=1) return;
    if(GetTickCount64()-queued_at>30000) { InterlockedExchange(&pending,0);InterlockedExchange(&menu_state,5);return; }
    wchar_t path[32768];
#else
    if (entering || attempted) return;
    wchar_t path[32768];
    if (!local_path(path, L"spawn-apple.request") || GetFileAttributesW(path) == INVALID_FILE_ATTRIBUTES) return;
    uint64_t name_pointer = 0, parent = 0, actor_name = 0;
    char name[13] = {0}, actor[9] = {0};
    unsigned char arg[0x98];
    if (!read_exact(original->x[1], &name_pointer, 8) || !read_exact(name_pointer, name, 13) ||
        strcmp(name, "Item_Fruit_A") || !read_exact(original->x[2], arg, sizeof arg)) return;
    memcpy(&parent, arg + 0x68, 8);
    // CarryBox identifies the fresh holding action; it never supplies position.
    if (!parent || original->x[5] || !read_exact(parent + 0x218, &actor_name, 8) ||
        !read_exact(actor_name, actor, 9) || strcmp(actor, "CarryBox")) return;
#endif
    float position[3], rotation[9];
    if (!player_world(position, rotation)) {
#ifdef SPAWN_MENU_MODE
        InterlockedExchange(&menu_state,6);InterlockedExchange(&pending,0);
#endif
        return;
    }
    float length = rotation[2]*rotation[2] + rotation[5]*rotation[5] + rotation[8]*rotation[8];
    if (!isfinite(length) || length < .8f || length > 1.2f) return;
    position[0] += rotation[2] * 1.5f;
    position[1] += 1.f;
    position[2] += rotation[8] * 1.5f;
    // Nested guest calls use a separate lower portion of the current guest stack.
    // Refuse unless that whole region is already committed and writable.
    if (original->sp < 0x10000) return;
    uint64_t stack = (original->sp - 0x8000) & ~15ull;
    MEMORY_BASIC_INFORMATION info;
    if (!VirtualQuery((void *)(uintptr_t)(stack - 0x4000), &info, sizeof info) || info.State != MEM_COMMIT ||
        (info.Protect != PAGE_READWRITE && info.Protect != PAGE_EXECUTE_READWRITE) ||
        (uint64_t)(uintptr_t)info.BaseAddress + info.RegionSize < stack + 32) return;
#ifdef SPAWN_MENU_MODE
    if(InterlockedCompareExchange(&pending,2,1)!=1)return;
    InterlockedExchange(&menu_state,2);
#else
    if (InterlockedCompareExchange(&attempted, 1, 0)) return;
    if (!DeleteFileW(path)) { InterlockedExchange(&attempted, 0); return; }
#endif
    entering = 1;
    // Persistent guest-visible storage prevents asynchronous code from retaining
    // a pointer into a temporary C buffer or a returned guest stack frame.
    void *memory = mem_kernel_alloc(sizeof ((AppleRequest *)0)->bytes, 16);
    AppleRequest request;
    const char *requested_actor = "Item_Fruit_A";
#ifdef SPAWN_MENU_MODE
    requested_actor=selected_actor;
#endif
    if (!memory || !item_delivery_build(&request, (uint64_t)(uintptr_t)memory, position, requested_actor)) goto finish;
    memcpy(memory, request.bytes, sizeof request.bytes);
    uint64_t stack_arguments[3] = {0, request.result, request.preactor};
    memcpy((void *)(uintptr_t)stack, stack_arguments, sizeof stack_arguments);
    Cpu call = *original;
    call.sp = stack;
    uint64_t accepted = rt_call(&call, entry, 8, original->x[0], request.name_object, request.creation_arg,
                                (uint64_t)0, (uint64_t)1, (uint64_t)0, (uint64_t)0, (uint64_t)0);
    uint32_t result;
    uint64_t preactor;
    memcpy(&result, (unsigned char *)memory + 0x180, 4);
    memcpy(&preactor, (unsigned char *)memory + 0x188, 8);
#ifdef SPAWN_MENU_MODE
    InterlockedExchange(&menu_state,accepted ? 3 : 4);
#endif
    if (local_path(path, L"apple-experiment.json")) {
        FILE *file = _wfopen(path, L"w");
        if (file) {
            fprintf(file, "{\"actor\":\"%s\",\"request_return\":%llu,\"result_code\":%u,\"preactor\":\"%llx\","
                          "\"position\":[%.6f,%.6f,%.6f],\"visual_confirmation_required\":true}\n",
                    requested_actor, (unsigned long long)accepted, result, (unsigned long long)preactor,
                    position[0], position[1], position[2]);
            fclose(file);
        }
    }
    if(local_path(path,L"spawn-history.jsonl")) {
        FILE *file=_wfopen(path,L"a");
        if(file) {
            SYSTEMTIME t;GetSystemTime(&t);
            unsigned long long waited=0;
#ifdef SPAWN_MENU_MODE
            waited=GetTickCount64()-queued_at;
#endif
#ifdef SPAWN_FRAME_QUEUE
            const char *consumer="guest_frame";
#else
            const char *consumer="natural_creation";
#endif
            fprintf(file,"{\"utc\":\"%04u-%02u-%02uT%02u:%02u:%02uZ\",\"item\":\"%s\",\"delivery\":\"%s\",\"return\":%llu,\"result\":%u,\"preactor\":\"%llx\",\"position\":[%.6f,%.6f,%.6f],\"consumer\":\"%s\",\"wait_ms\":%llu}\n",
                    t.wYear,t.wMonth,t.wDay,t.wHour,t.wMinute,t.wSecond,requested_actor,
                    spawn_menu_item_chest(requested_actor)?"chest":"world",(unsigned long long)accepted,result,
                    (unsigned long long)preactor,position[0],position[1],position[2],consumer,waited);
            fclose(file);
        }
    }
finish:
    entering = 0;
#ifdef SPAWN_MENU_MODE
    if(InterlockedCompareExchange(&menu_state,0,0)==2)InterlockedExchange(&menu_state,4);
    InterlockedExchange(&pending,0);
#endif
}

void apple_experiment_enter(Cpu *original, uint64_t entry) {
    DWORD error = GetLastError();
    int saved_errno = errno;
    fenv_t environment;
    fegetenv(&environment);
#ifdef SPAWN_FRAME_QUEUE
    (void)entry;
    remember_context(original);
#else
    apple_experiment_run(original, entry);
#endif
    fesetenv(&environment);
    errno = saved_errno;
    SetLastError(error);
}

#ifdef SPAWN_FRAME_QUEUE
// The recurring guest frame controller is the consumer. Reuse only a manager
// observed on this exact guest thread, never the render thread or a new host thread.
void spawn_menu_frame(Cpu *original,uint64_t entry) {
    if(entering || InterlockedCompareExchange(&pending,0,0)!=1)return;
    DWORD error=GetLastError();int saved_errno=errno;fenv_t env;fegetenv(&env);
    uint64_t manager=0,identity=0,current=0;
    AcquireSRWLockShared(&context_lock);
    for(unsigned i=0;i<32;++i)if(contexts[i].thread==original->thread) {
        manager=contexts[i].manager;identity=contexts[i].vtable;break;
    }
    ReleaseSRWLockShared(&context_lock);
    if(manager && read_exact(manager,&current,8) && current==identity) {
        Cpu call=*original;call.x[0]=manager;
        apple_experiment_run(&call,entry);
    }
    fesetenv(&env);errno=saved_errno;SetLastError(error);
}
#endif
#endif
