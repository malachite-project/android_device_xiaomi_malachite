#!/usr/bin/env bash
#
# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0
#
# Apply the device fixes that RisingOS's framework forks do not carry yet.
# Run from the root of the Android tree after repo sync and before building.

set -euo pipefail

top=${ANDROID_BUILD_TOP:-$(pwd)}
patches="$(cd "$(dirname "$0")/../../patches/rising" && pwd)"

if [ ! -d "$top/frameworks/native/.git" ]; then
    echo "Run this from the root of the Android tree." >&2
    exit 1
fi

for patch in "$patches"/*.patch; do
    [ -e "$patch" ] || continue
    name=$(basename "$patch")
    if git -C "$top/frameworks/native" apply --check "$patch" 2>/dev/null; then
        git -C "$top/frameworks/native" apply "$patch"
        echo "Applied $name"
    elif git -C "$top/frameworks/native" apply --reverse --check "$patch" 2>/dev/null; then
        echo "Already applied $name"
    else
        echo "Failed to apply $name; resolve it against frameworks/native." >&2
        exit 1
    fi
done
