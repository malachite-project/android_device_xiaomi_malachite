#!/usr/bin/env bash
#
# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0
#
# Create the release keys RisingOS signs APKs, APEXes and the OTA with.
# The private keys stay in vendor/lineage-priv/keys (gitignored by RisingOS)
# and are never committed. Run from the root of an Android tree.

set -euo pipefail

top=${ANDROID_BUILD_TOP:-$(pwd)}
keys="$top/vendor/lineage-priv/keys"

if [ ! -f "$top/build/envsetup.sh" ]; then
    echo "Run this from the root of the Android tree." >&2
    exit 1
fi

if ! command -v openssl >/dev/null; then
    echo "openssl is required to create the AVB key." >&2
    exit 1
fi

mkdir -p "$keys"

if [ ! -f "$keys/keys.mk" ] || [ ! -f "$keys/releasekey.pk8" ]; then
    echo "Generating APK and APEX signing keys with gk -f..."
    (
        cd "$top"
        # gk is a shell function from build/envsetup.sh.
        . build/envsetup.sh >/dev/null
        gk -f
    )
fi

# gk wipes the key directory, so the AVB key is created afterwards.
if [ ! -f "$keys/avb.pem" ]; then
    echo "Generating the 4096-bit AVB key..."
    openssl genrsa -out "$keys/avb.pem" 4096
fi

chmod 600 "$keys"/*.pk8 "$keys"/*.pem

echo
echo "Release keys are in $keys"
echo "AVB public key:"
openssl rsa -in "$keys/avb.pem" -pubout 2>/dev/null | openssl pkey -pubin -outform DER 2>/dev/null | sha256sum
echo
echo "Build a signed user build with:"
echo "  . build/envsetup.sh"
echo "  riseup malachite user"
echo "  rise sb"
