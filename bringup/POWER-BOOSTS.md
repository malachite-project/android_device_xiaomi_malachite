# CPU boosts, governor and ADPF

**Status: untested.** Nothing here has been built or measured on a device.

## What a uclamp boost is

`cpu.uclamp.min` asks the scheduler to treat a group's tasks as needing at
least that share of a CPU's capacity, which pulls the CPU frequency up for
them. `init.mt6878.power.rc` sets it per task group, and the power HAL raises
it for a moment on touch, launch and heavy rendering (`configs/powerhint.json`).

`/proc/sys/kernel/sched_util_clamp_min` is a ceiling on all of those requests,
per-thread ones included. The kernel caps each task's effective `uclamp.min`
at it (GKI 6.1 `kernel/sched/core.c`, `uclamp_eff_get()`: a request above the
system default returns the default), and none of the prebuilt vendor modules
override that.

## The old 12.5% ceiling

Until September 2026 the ceiling was `128` of `1024`, that is 12.5%. It dates
from darkhz's "Fix frequency lockups" (`d34bf5c`, 2021), which lowered it
because CPUs stayed stuck at their maximum or minimum frequency. The same-SoC
trees (tetris, scout, Galaga) and the MT6789 trees (emerald, tanzanite) keep
it.

claxten10 later configured larger boosts (`663311a`, `8956ae7`, `3413861`,
`b36c031`, `c901169`, 2025). Under the ceiling each one ran as 12.5%, so the
tree writes 12.5 in their place:

| Where | Setting | Configured | Written |
| --- | --- | --- | --- |
| `init.mt6878.power.rc` | camera-daemon `cpu.uclamp.min` | 70 | 12.5 |
| `init.mt6878.power.rc` | nnapi-hal `cpu.uclamp.min` | 90 | 12.5 |
| `powerhint.json` INTERACTION | top-app (`UclampTAMin`) | 40 | 12.5 |
| `powerhint.json` FIXED_PERFORMANCE | top-app (`UclampTAMin`) | 100 | 12.5 |
| `powerhint.json` EXPENSIVE_RENDERING | foreground (`UclampFGMin`) | 30 | 12.5 |

## The ceiling is now lifted for ADPF

ADPF hint sessions (HWUI render threads, Chrome, games) size CPU demand per
frame by setting `uclamp.min` on the session's threads with `sched_setattr`.
`power-libperfmgr` only accepts sessions when `powerhint.json` has an
`AdpfConfig`; without one every client got `EX_UNSUPPORTED_OPERATION`.
A 12.5% ceiling would also have capped each session below its useful range.

The ceiling is now `1024`. Every group and power-hint value above stays at
12.5, so their behaviour is unchanged; `tests/test_powerhint.py` enforces
both. Only ADPF threads can go higher, up to `UclampMin_High` (390, 38%).

The `ADPF_DEFAULT` profile follows claxten10's MediaTek profile for gale
(MT6768, `f5ea899`), minus the heuristic boost entries, which the current
parser names differently and would reject, dropping every profile. The power
HAL needs `setsched` on app, SurfaceFlinger, composer and system_server
threads, `sys_nice` and `mlstrustedsubject` (Pixel's
`power-libperfmgr/hal_power_default.te`); see
`sepolicy/vendor/hal_power_default.te`.

Watch for the lockups `d34bf5c` described: CPUs pinned at a fixed frequency
while idle, visible in
`/sys/devices/system/cpu/cpufreq/policy*/scaling_cur_freq`. Sessions release
their clamp when paused or closed, and a stale session times out after
`StaleTimeFactor` frame periods. If they appear, write `128` back to the
ceiling to confirm the cause.

## Governor: sugov_ext

After boot the tree selects `sugov_ext` (`cpufreq_sugov_ext.ko`), MediaTek's
schedutil, as stock OS3 does. Its frequency choice uses the non-linear OPP
capacity table that `scheduler.ko` already applies to task placement and
frequency invariance, adds a per-cluster adaptive margin, and votes the DSU
frequency. Plain `schedutil` maps utilisation to frequency linearly with a
fixed 25% margin. `schedutil` is written first so a failed `sugov_ext` write
leaves the previous behaviour rather than the boot-time `performance`
governor.

## Cache QoS

`cpuqos_v3.ko` keeps L3 partitioning disabled until `1` is written to
`/sys/devices/system/cpu/cpuqos/cpuqos_boot_complete`, which stock and the
Galaga tree do at boot completion. The tree now does the same.

## Returning to the larger boost profile

1. Put back the configured values from the table: the two rc lines, the
   `UclampTAMin` node values `0, 40, 100` with its actions, and the
   `UclampFGMin` node values `0, 10, 30` with its action.
2. Raise `GROUP_BOOST_LIMIT` in `tests/test_powerhint.py` to match.

Expect more speed in the camera, on-device AI and touch response, and more
battery use.
