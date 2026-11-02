"""Generate the two game-thread hook sites without editing lifted game code."""


def release_header(creation, frame, marker):
    return '\n'.join([
        '// ' + marker + ': private release hook addresses; do not distribute.',
        '#include "cpu.h"',
        'void apple_experiment_enter(Cpu *, uint64_t);',
        'void spawn_menu_frame(Cpu *, uint64_t);',
        '#undef FN_ENTER',
        '#define FN_ENTER(a) do { \\',
        'if (__builtin_expect(g_fnprof, 0)) fnprof_hit(a, c->x[30], c->x[0]); \\',
        f'if ((a) == 0x{creation:x}ull) apple_experiment_enter(c, (a)); \\',
        f'if ((a) == 0x{frame:x}ull) spawn_menu_frame(c, 0x{creation:x}ull); \\',
        '} while (0)', '',
    ])
