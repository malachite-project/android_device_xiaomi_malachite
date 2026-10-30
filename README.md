# Evolution X for the Redmi Note 14 Pro 5G / POCO X7 5G (malachite)

Device tree for an unofficial Evolution X (Android 17) build for malachite,
ported from LineageOS 24.0. Not built or tested on a phone yet.

**Downloads, updates and support:** [Telegram group](https://t.me/malachite_project)

## Branch

`feature/evolutionx-24.0` is the Evolution X branch in this device tree and
the [malachite-project](https://github.com/malachite-project) frameworks/native
fork. Other dependencies use `lineage-24.0`. See [EVOLUTION.md](EVOLUTION.md)
for the port state and remaining prerequisites. `lineage-23.2` (Android 16) stays as it was;
[bringup/LINEAGE-24.md](bringup/LINEAGE-24.md) lists what moving each fork to
24.0 changed.

## Building

See [EVOLUTION.md](EVOLUTION.md) for the Evolution X build and signing steps,
[BUILDING.md](BUILDING.md) for general fork maintenance, and [AGENTS.md](AGENTS.md)
for the working rules.

`manifests/evolution.xml` is the local manifest for this branch: set up an
Evolution X cnb checkout and copy it to `.repo/local_manifests/`. Follow
EVOLUTION.md before syncing and building. Do not also install malachite.xml,
which selects the LineageOS framework forks. The manifest comment lists what
each fork changes.
Kernel sources are built separately; see
[kernel_manifest-6.1](https://github.com/malachite-project/kernel_manifest-6.1).

## Source ID

Every build made from these trees, whatever the ROM, can be traced to its exact
sources. Rules for builders:

1. Keep every project a git checkout (repo sync or git clone, not copies), and
   commit and push your changes, patches included, before building.
2. Right before building, from the top of the ROM tree:
   ```
   bash device/xiaomi/malachite/tools/source-snapshot.sh
   ```
   It records the commit of every project in the tree and prints the source ID. If it
   lists projects with uncommitted or unpushed changes, commit and push them and run
   it again.
3. Build as usual. Put the source ID in your release notes, and include it in bug
   reports.

The build puts the record in the ROM, so nothing extra has to be published:

```
adb shell getprop ro.malachite.source.id            # src-<12 hex digits>
adb shell cat /system_ext/etc/source/manifest.xml  # every project and commit
```

Both can be read from adb shell and appear in bug reports; apps can't read them.
Anyone can sync that exact tree from the file: pull it, copy it to `.repo/manifests/`,
then `repo init -m manifest.xml` and `repo sync`. The ID ends in `-untraceable` if
something was uncommitted or unpushed, `-stale` if the device, vendor or kernel tree
changed after the snapshot, and is `none` if no snapshot was taken.

Even without a snapshot, every build records its device, vendor and kernel trees as
`<repository>@<commit>`, from wherever they were synced (forks included):

```
adb shell getprop | grep malachite.source
```

## Credits

Built on the work of [mt6878-devs](https://github.com/mt6878-devs),
[puhboo](https://github.com/puhboo) and [cmdr-chara](https://github.com/cmdr-chara),
and of the LineageOS project.

```
#
# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0
#
```
