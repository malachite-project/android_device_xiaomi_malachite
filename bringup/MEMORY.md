# lmkd and zram

**Status: untested.** Nothing here has been built or measured on a device.

## The swap-low threshold

`vendor.prop` used to set `ro.lmk.swap_free_low_percentage=100`. The other
lmkd values next to it (`filecache_min_kb`, `kill_timeout_ms`,
`stall_limit_critical`) are Pixel's (`hardware/google/pixel/mm/device_gki.mk`),
as are the zram fstab and writeback properties. Pixel does not set this one;
lmkd's default is 10.

lmkd decides swap is low in `__mp_event_psi()` (`system/memory/lmkd/lmkd.cpp`):

```
swap_low_threshold = total_swap * swap_free_low_percentage / 100;
swap_is_low = get_free_swap(&mi) < swap_low_threshold;
```

`get_free_swap()` is `min(SwapFree, MemFree + Inactive(file))`. At 100 the
threshold is all of `SwapTotal`, so swap counts as low as soon as one page is
in zram, and even with zram empty whenever free memory plus inactive page
cache is below `SwapTotal` (half of RAM here). In practice it is always low.

With swap low, lmkd kills on the first memory-pressure event in which free
memory is under the high watermark (`LOW_MEM_AND_SWAP`), which is the normal
state while kswapd reclaims. It also polls every 10 ms instead of 100 ms
during pressure. Cached and previous apps, and anything else above
`PERCEPTIBLE_APP_ADJ`, are killed instead of being compressed into zram. zram
is set up but barely used, and switching back to those apps is a cold start.

At the default of 10, kills under watermark pressure come from page-cache
thrashing, swap really running out, PSI critical stalls or a breached min
watermark after a kill, as on Pixel.

## Checking it on a device

Before and after, with the same set of apps opened in turn and then revisited:

- `adb logcat -b events -s killinfo` and `adb logcat -s lowmemorykiller`:
  kill count and reason. Before, expect "swap is low" kills with most of
  `SwapTotal` free.
- `grep -E 'Swap(Total|Free)' /proc/meminfo` after a session: zram use.
- `adb shell dumpsys activity exit-info <package>`: `LOW_MEMORY` exits.
- `adb shell am start -W` on a revisited app: `LaunchState` (COLD vs WARM/HOT)
  and `TotalTime`.

If the device thrashes instead (long `swapin` stalls, `/proc/pressure/memory`
`full` climbing, janky UI), lmkd's thrashing and critical-stall kills should
cover it; set the property back to confirm the cause.
