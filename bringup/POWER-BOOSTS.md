# CPU boost profile (uclamp)

**Status: the profile below is saved, not active.** The tree ships the values
the phone actually runs with. Nothing here has been measured on a device.

## What a uclamp boost is

`cpu.uclamp.min` asks the scheduler to treat a group's tasks as needing at
least that share of a CPU's capacity, which pulls the CPU frequency up for
them. `init.mt6878.power.rc` sets it per task group, and the power HAL raises
it for a moment on touch, launch and heavy rendering (`configs/powerhint.json`).

`/proc/sys/kernel/sched_util_clamp_min` is a ceiling on all of those requests.
The kernel caps each task's effective `uclamp.min` at it (GKI 6.1
`kernel/sched/core.c`, `uclamp_eff_get()`: a request above the system default
returns the default), and none of the prebuilt vendor modules override that.

## Why the profile was inactive

The ceiling is `128` of `1024`, that is 12.5%. It dates from darkhz's
"Fix frequency lockups" (`d34bf5c`, 2021), which lowered it because CPUs
stayed stuck at their maximum or minimum frequency. Every same-SoC tree
(tetris, scout) and the MT6789 trees (emerald, tanzanite) keep the same value.

claxten10 later configured larger boosts (`663311a`, `8956ae7`, `3413861`,
`b36c031`, `c901169`, 2025). Under the ceiling each one ran as 12.5%. The tree
now writes 12.5 in their place, so the files state the behaviour the phone
already had.

| Where | Setting | Configured | Effective, and now written |
| --- | --- | --- | --- |
| `init.mt6878.power.rc` | camera-daemon `cpu.uclamp.min` | 70 | 12.5 |
| `init.mt6878.power.rc` | nnapi-hal `cpu.uclamp.min` | 90 | 12.5 |
| `powerhint.json` INTERACTION | top-app (`UclampTAMin`) | 40 | 12.5 |
| `powerhint.json` FIXED_PERFORMANCE | top-app (`UclampTAMin`) | 100 | 12.5 |
| `powerhint.json` EXPENSIVE_RENDERING | foreground (`UclampFGMin`) | 30 | 12.5 |

Values at or below the ceiling were already effective and are unchanged:
foreground 10 on INTERACTION, and every 0.

`configs/nnapi_powerhal.json` is a stock MediaTek file. Its
`PERF_RES_SCHED_UCLAMP_MIN_*` values of 100 are capped the same way; the file
is left as shipped.

## Turning the profile on

1. In `init/init.mt6878.power.rc`, raise `sched_util_clamp_min` to `1024`
   (the kernel default, no ceiling).
2. Put back the configured values from the table: the two rc lines, the
   `UclampTAMin` node values `0, 40, 100` with its actions, and the
   `UclampFGMin` node values `0, 10, 30` with its action.

Expect more speed in the camera, on-device AI and touch response, and more
battery use. Test it on the phone before relying on it, and watch for the
frequency lockups `d34bf5c` described: CPUs pinned at a fixed frequency while
idle, visible in `/sys/devices/system/cpu/cpufreq/policy*/scaling_cur_freq`.
