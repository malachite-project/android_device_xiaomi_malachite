# September 2026 init-lifecycle audit follow-up

Baseline: device `b6918928e81a3bf8f191d8346153b417eb47bd1e`.
This is a bounded source fix, not closure of the full Lunaris pre-build audit
and not a battery-life, charging-safety or release certification.
The local Android workspace, resolved manifest, staged `vendor/extra` and
physical device were not available. No ROM build or device operation was run.

## Charger-only boot: release the normal-boot governor request

The original [power init](../init/init.mt6878.power.rc) selects `performance`
for CPU policies 0 and 4 during `init`, then restores `schedutil` only at
`sys.boot_completed=1`. Android init queues `init` before choosing **either**
`charger` or `late-init`; charger-only mode does not start normal Android boot.
See the [reference event selection](https://github.com/LineageOS/android_system_core/blob/0e96ff13d90df568ddd788bb02b3ddb6e3641528/init/init.cpp#L1234-L1246).
The inspected Lunaris `16.2` file has the identical Git blob
`7de53f99940c9006eafbe29bd3e4a31ce078ca2a`.

Given existing policy nodes and successful writes, this file leaves both
policies requesting `performance` after `init -> charger`. The source model
reproduces that state before the patch. The charger action now requests the
same `schedutil` governors already used at normal boot completion. Normal
boot tuning, policy limits, UFS policy, battery authentication, Power HAL
activation and thermal protection are otherwise unchanged.

This fixes the missing release in this rc file. It does **not** establish
that the original writes succeeded on the phone, that another installed
component did not override them, or that measurable drain/heat occurred.
Runtime acceptance still requires charger-only and normal-boot governor,
frequency-residency and power measurements on the exact installed build.

## Module loader: preserve failure without creating a boot wait

The product packages [init.insmod.sh](../modules/init.insmod.sh) through
[modules/Android.bp](../modules/Android.bp). The installed configuration tries
the system and vendor lists before setting `vendor.all.modules.ready=1`.
`init/init.mt6878.rc` waits for that property in `post-fs-data`.

Previously a failing `modprobe`, `insmod`, enable write or exhausted property
retry could be followed by a successful command and a zero process exit.
The [platform modprobe](https://github.com/LineageOS/android_system_core/blob/0e96ff13d90df568ddd788bb02b3ddb6e3641528/toolbox/modprobe.cpp#L302-L354)
already returns failure; the wrapper discarded it. The inspected Lunaris
`16.2` modprobe file has the identical Git blob
`c5025e7b491427677d620db2868f66bb4688da48`.

The wrapper now aggregates failures and exits nonzero while continuing
subsequent actions and partitions. Failed load-list reads are reported rather
than converted into an empty argument list. Property writes remain bounded
at 128 attempts. Config paths and enable targets are quoted, final lines
without a newline are processed, and module argument splitting cannot expand
unrelated filenames in the process working directory. Unknown actions fail
visibly instead of being silently ignored.

**Compatibility contract:** `vendor.all.modules.ready` remains the existing
load-attempt completion barrier, not proof of successful module insertion.
It is deliberately still published after a module-load failure. Withholding
it would introduce a boot hang at the existing unbounded init wait. The
process exit status now exposes aggregate failure; stderr describes the
failing action where captured. No new property, SELinux permission, retry
service or reboot action is introduced. This is failure-reporting and parser
repair, not repair of any missing or ABI-incompatible kernel module.

System-before-vendor ordering, order within each list (including the first
vendor KernelSU entry), blocklist options and explicit module arguments are
preserved. Kernel artifacts and load lists are not modified.

## Host regression and CI coverage

The original contents of the changed existing files were reconstructed from
pinned GitHub reads and checked against their Git blob hashes before testing.
The test harness executes the actual loader under host shells with fake
`cat`, `modprobe`, `insmod` and `setprop` commands. Module-list reads are mapped
to temporary fixtures; enable writes target only temporary files. It never
inserts a module or writes real sysfs/properties.

```sh
MALACHITE_TEST_SHELL=/bin/bash python3 -m unittest discover -s tests -p 'test_module_loader.py' -v
MALACHITE_TEST_SHELL=/bin/dash python3 -m unittest discover -s tests -p 'test_module_loader.py' -v
python3 -m unittest discover -s tests -p 'test_power_init.py' -v
```

The power tests model only the governor writes in this device rc, including
the successful-write prerequisite. They are not a replacement for Android's
init parser, Soong evaluation or device measurements.

The device-contract workflow now includes PRs targeting `main` as well as
`lineage-23.2`, retains its existing cleanup-branch trigger, checks the loader
with `mksh`, and runs the full offline unittest discovery rather than only
`test_device_contracts.py`. The PR's checks are the authority for the final
full-tree CI result. A passing host suite is not ROM-build or device proof.

## Disposition of the ten original audit candidates

| Candidate | Result of this follow-up | Remaining evidence |
| --- | --- | --- |
| C01: charger governor | Missing release corrected in the device rc | Actual successful writes, competing owners, offline-charge and normal-boot measurements |
| C02: UFS clock gating | No speculative change | Shipped driver quirks, stock rationale, I/O integrity and residency |
| C03: persistent power hints | No speculative change | Exact Power HAL/driver ABI and begin/end transitions under concurrent modes |
| C04: thermal reporting | No thresholds or mitigation changes | Sensor names/units, actual daemon operation and kernel cooling response |
| C05: charging and regional resources | No tuning or calibration changes | Actual SKU/overlay selection, health units and supported charger measurements |
| C06: module loader | Error propagation and parser repaired; completion barrier preserved | Actual per-module insertion and ABI, required/optional classification; not certified by the barrier |
| C07: AVB | Existing signing/rollback policy untouched | Evaluated release configuration and generated public AVB metadata |
| C08: update/recovery/storage | Existing safety boundaries retained | Built images, payloads, module CRCs and storage guarantees |
| C09: VINTF/SELinux/vendor ABI | No unsupported policy/HAL edits | Exact integrated source/binaries and merged build/runtime checks |
| C10: product additions | Not available here; no invented fixes | Staged `vendor/extra` sources/APKs and lifecycle evidence |

The already committed WPA3 compatibility change is preserved. No firmware,
DTBO deployment, signing keys, rollback indices, persistent storage, charger
limits, temperature trips or thermal services are changed by this follow-up.
