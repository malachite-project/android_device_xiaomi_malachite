#!/bin/bash
# RisingOS Revived (sixteen-qpr2) for malachite, fresh checkout in ~/rising.
# Needs ~/keep/{malachite.xml,apply-malachite-patches-evox.sh,keys} saved from the Evolution X checkout.
# Steps: init | sync | keys | build | backup      (run from anywhere)
set -eu
SRC=${SRC:-$HOME/rising}
KEYS=$SRC/vendor/lineage-priv/keys
KEEP=$HOME/keep
mkdir -p "$SRC"; cd "$SRC"

do_init() {
  for f in malachite.xml apply-malachite-patches-evox.sh keys/testkey.pk8; do [ -e "$KEEP/$f" ] || { echo "!! missing $KEEP/$f"; exit 1; }; done
  [ -d .repo ] || repo init -u https://github.com/RisingOS-Revived/android -b sixteen-qpr2 --git-lfs --repo-url=https://gerrit.googlesource.com/git-repo --repo-rev=b85886fa9f5b4e2189cc5b2f40bd0a80459d4c77
  mkdir -p .repo/local_manifests
  cp "$KEEP/malachite.xml" .repo/local_manifests/malachite.xml
  cp "$KEEP/apply-malachite-patches-evox.sh" .
  echo ">> local manifest projects: $(grep -c '<project' .repo/local_manifests/malachite.xml)"
}

do_patch() {
  # Rising patch script = the Evolution X one without its Evolution-only maintainer block
  python3 -I - <<'PY'
s = open("apply-malachite-patches-evox.sh").read()
a = s.index("# Maintainer card")
b = s.index('[ "$FAIL" = 0 ] && echo "DONE')
open("apply-malachite-patches-rising.sh", "w").write(s[:a] + s[b:])
PY
  chmod +x apply-malachite-patches-rising.sh
  ./apply-malachite-patches-rising.sh
  # inline release signing: include our keys from the product makefile
  MK=device/xiaomi/malachite/lineage_malachite.mk
  grep -q 'lineage-priv/keys/keys.mk' "$MK" || printf '\n# release keys\n-include vendor/lineage-priv/keys/keys.mk\n' >> "$MK"
  grep -n 'lineage-priv/keys/keys.mk' "$MK"
}

do_sync() {
  repo sync -c -d -j3 --retry-fetches=5 --force-sync --no-clone-bundle --no-tags
  do_patch
}

do_keys() {
  OLD=$KEEP/keys
  if [ ! -f "$KEYS/testkey.pk8" ]; then
    [ -f "$OLD/testkey.pk8" ] && [ -f "$OLD/avb_custom_key.bin" ] || { echo "!! no Evolution keys to reuse in $OLD"; exit 1; }
    rm -rf "$KEYS"; mkdir -p "$(dirname "$KEYS")"; cp -a "$OLD" "$KEYS"
    sed -i 's#vendor/evolution-priv#vendor/lineage-priv#g' "$KEYS/keys.mk"
  fi
  grep -n 'PRODUCT_DEFAULT_DEV_CERTIFICATE' "$KEYS/keys.mk"
  A=$(openssl x509 -in build/make/target/product/security/testkey.x509.pem -noout -fingerprint -sha256 || true)
  B=$(openssl x509 -in "$KEYS/testkey.x509.pem" -noout -fingerprint -sha256 || true)
  [ -n "$B" ] && [ "$A" != "$B" ] || { echo "!! key check failed (equals AOSP test key or missing)"; exit 1; }
  openssl x509 -in "$KEYS/testkey.x509.pem" -noout -subject
  echo ">> keys OK ($(ls "$KEYS"/*.pk8 | wc -l) .pk8 files)"
}

do_build() {
  [ -f "$KEYS/keys.mk" ] || { echo "no keys: run keys first"; exit 1; }
  grep -q 'lineage-priv/keys/keys.mk' device/xiaomi/malachite/lineage_malachite.mk || { echo "!! keys include missing: run sync first"; exit 1; }
  export WITH_GMS=true
  export MALACHITE_RELEASE=true USE_CCACHE=1 CCACHE_EXEC=/usr/bin/ccache
  export BUILD_USERNAME=ridhzxlabs BUILD_HOSTNAME=ridhzxlabs
  set +eu; source build/envsetup.sh
  breakfast malachite userdebug
  echo ">> package type: $(get_build_var RISING_PACKAGE_TYPE)  build type: $(get_build_var RISING_BUILDTYPE)  keys: $(get_build_var BUILD_KEYS 2>/dev/null)"
  mka bacon 2>&1 | tee "$HOME/build-rising-$(date +%m%d-%H%M).log"
  ls -lh out/target/product/malachite/*.zip out/target/product/malachite/*.img 2>/dev/null
}

do_backup() { tar czf "$HOME/rising-keys-backup.tar.gz" -C "$SRC/vendor/lineage-priv" keys && echo ">> $HOME/rising-keys-backup.tar.gz"; }

case "${1:-}" in
  init) do_init;; sync) do_sync;; patch) do_patch;; keys) do_keys;; build) do_build;; backup) do_backup;;
  *) sed -n '5,5p' "$0";;
esac
