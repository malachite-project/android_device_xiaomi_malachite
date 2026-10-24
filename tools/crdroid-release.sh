#!/bin/bash
# crDroid 16.0 for malachite - release-key build helper.
# Usage:  ~/crdroid/crdroid-release.sh <step>
#   clean   delete the previous build output (keeps source + ccache)
#   sync    repo sync (resets every project to clean state) + re-apply malachite patches
#   keys    create release keys ONCE into vendor/lineage-priv/keys (refuses to overwrite)
#   build   build the release-signed ROM
#   backup  pack the keys into ~/crdroid-keys-backup.tar.gz
#   all     clean + sync + keys + build + backup
set -eu
SRC=${SRC:-$HOME/crdroid}
KEYS=$SRC/vendor/lineage-priv/keys
cd "$SRC"

do_clean() {
  echo ">> removing old malachite build output (source + ccache kept)"
  rm -rf out/target/product/malachite
  df -h . | tail -1
}

do_sync() {
  echo ">> repo sync -d (reset projects to manifest revision, drops old cherry-picks)"
  repo sync -c -d -j"$(nproc)" --force-sync --no-clone-bundle --no-tags
  [ -x ./apply-malachite-patches.sh ] || { echo "apply-malachite-patches.sh missing in $SRC"; exit 1; }
  ./apply-malachite-patches.sh
}

do_keys() {
  if [ -f "$KEYS/releasekey.pk8" ]; then
    echo ">> keys already exist in $KEYS - NOT regenerating (new keys would break updates)."
    return
  fi
  rm -rf "$HOME/crDroid-build-signed-script"
  git clone --depth 1 https://github.com/crdroidandroid/crDroid-build-signed-script "$HOME/crDroid-build-signed-script"
  cp "$HOME/crDroid-build-signed-script/create-signed-env.sh" "$HOME/crDroid-build-signed-script/keys.mk" .
  # answers: C, ST, L, O, OU, CN, email, confirm. Edit if you want other subject fields.
  printf '%s\n' ID Jakarta Jakarta ridhzxlabs ridhzxlabs ridhzxlabs noreply@ridhzxlabs.invalid Y | bash ./create-signed-env.sh
  rm -f create-signed-env.sh keys.mk
  test -f "$KEYS/releasekey.pk8" && test -f "$KEYS/keys.mk" && echo ">> keys OK ($(ls "$KEYS" | wc -l) files)"
}

do_build() {
  [ -f "$KEYS/keys.mk" ] || { echo "no keys yet: run 'keys' first"; exit 1; }
  export MALACHITE_RELEASE=true USE_CCACHE=1 CCACHE_EXEC=/usr/bin/ccache
  export BUILD_USERNAME=ridhzxlabs BUILD_HOSTNAME=ridhzxlabs
  set +eu; source build/envsetup.sh
  breakfast malachite userdebug
  mka bacon 2>&1 | tee "$HOME/build-release-$(date +%m%d-%H%M).log"
  ls -lh out/target/product/malachite/*.zip out/target/product/malachite/*.img 2>/dev/null
}

do_backup() {
  tar czf "$HOME/crdroid-keys-backup.tar.gz" -C "$SRC/vendor/lineage-priv" keys
  echo ">> $HOME/crdroid-keys-backup.tar.gz - download to your PC NOW. NEVER upload keys to GitHub."
}

case "${1:-}" in
  clean) do_clean;; sync) do_sync;; keys) do_keys;; build) do_build;; backup) do_backup;;
  all) do_clean; do_sync; do_keys; do_build; do_backup;;
  *) sed -n '2,9p' "$0";;
esac
