# LineageOS 23.2 for the Redmi Note 14 Pro 5G / POCO X7 5G (malachite)

Device tree for an unofficial LineageOS 23.2 (Android 16) build for malachite.

**Downloads, updates and support:** [Telegram group](https://t.me/malachite_project)

## Branch

`lineage-23.2` is the only branch, in this repository and in every other
[malachite-project](https://github.com/malachite-project) fork. To base work on
these trees, use `lineage-23.2`.

## Building

`manifests/malachite.xml` is the local manifest for the whole tree: set up a
LineageOS 23.2 checkout, copy it to `.repo/local_manifests/`, sync, then
`breakfast malachite`. The comment at its top lists what each fork changes.
Kernel sources are built separately; see
[kernel_manifest-6.1](https://github.com/malachite-project/kernel_manifest-6.1).

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
