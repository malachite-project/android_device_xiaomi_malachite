#!/bin/bash
# Evolution X (bka, Android 16) for malachite - release-key build helper.
# Own folder (~/evox), so it never touches ~/crdroid.   Usage:  ~/evox/evox-release.sh <step>
#   init    repo init + local manifest + patch script (run once, from ~/evox)
#   sync    repo sync (resets projects to clean state) + malachite patches + maintainer name
#   keys    create release keys ONCE into vendor/evolution-priv/keys (refuses to overwrite)
#   build   build the release-signed ROM (mka evolution)
#   backup  pack keys into ~/evox-keys-backup.tar.gz
#   clean   delete build output (keeps source + ccache)
set -eu
SRC=${SRC:-$HOME/evox}
BRANCH=${BRANCH:-evox-malachite}     # device-tree branch in your fork
RAW=https://raw.githubusercontent.com/ridhzlabs/android_device_xiaomi_malachite/$BRANCH
KEYS=$SRC/vendor/evolution-priv/keys
mkdir -p "$SRC"; cd "$SRC"

do_init() {
  df -h "$SRC" | tail -1
  [ -d .repo ] || repo init -u https://github.com/Evolution-X/manifest -b bka --git-lfs --repo-url=https://gerrit.googlesource.com/git-repo --repo-rev=b85886fa9f5b4e2189cc5b2f40bd0a80459d4c77
  mkdir -p .repo/local_manifests
  curl -fL "$RAW/manifests/evox.xml" -o .repo/local_manifests/malachite.xml
  curl -fL "$RAW/tools/apply-malachite-patches-evox.sh" -o apply-malachite-patches-evox.sh
  chmod +x apply-malachite-patches-evox.sh
  echo ">> manifest: $(grep -c '<project' .repo/local_manifests/malachite.xml) projects, device branch: $(grep -o 'revision="[^"]*"' .repo/local_manifests/malachite.xml | sed -n 1p)"
  echo ">> patch script lines: $(wc -l < apply-malachite-patches-evox.sh)  (check against the number in the chat)"
}

do_sync() {
  repo sync -c -d -j3 --retry-fetches=5 --force-sync --no-clone-bundle --no-tags
  ./apply-malachite-patches-evox.sh
}

do_keys() {
  if [ -f "$KEYS/.keys_done" ]; then
    echo ">> keys already exist in $KEYS - NOT regenerating (new keys would break updates)."; return
  fi
  rm -rf "$KEYS"; mkdir -p "$(dirname "$KEYS")"
  git clone --depth 1 https://github.com/Evolution-X/vendor_evolution-priv_keys-template "$KEYS"
  rm -rf "$KEYS/.git"                      # keys must never be pushed anywhere
  cd "$KEYS"
  # own certificate subject instead of the default "Android"
  sed -i "s#'/C=US[^']*'#'/C=ID/ST=Jakarta/L=Jakarta/O=ridhzxlabs/OU=ridhzxlabs/CN=ridhzxlabs/emailAddress=noreply@ridhzxlabs.invalid'#" make_key.sh
  grep -q ridhzxlabs make_key.sh || { echo "!! subject edit failed"; exit 1; }
  echo ">> generating keys (about 90 RSA-4096 keys, takes several minutes)..."
  ./keys.sh
  cd "$SRC"
  # sanity: our key must NOT be the public AOSP test key
  A=$(openssl x509 -in build/make/target/product/security/testkey.x509.pem -noout -fingerprint -sha256)
  B=$(openssl x509 -in "$KEYS/testkey.x509.pem" -noout -fingerprint -sha256)
  [ "$A" != "$B" ] || { echo "!! generated key equals the public AOSP test key - do NOT build"; exit 1; }
  openssl x509 -in "$KEYS/releasekey.x509.pem" -noout -subject
  touch "$KEYS/.keys_done"
  echo ">> keys OK ($(ls "$KEYS" | wc -l) files)"
}

do_build() {
  [ -f "$KEYS/.keys_done" ] || { echo "no keys yet: run 'keys' first"; exit 1; }
  export MALACHITE_RELEASE=true USE_CCACHE=1 CCACHE_EXEC=/usr/bin/ccache
  export BUILD_USERNAME=ridhzxlabs BUILD_HOSTNAME=ridhzxlabs
  # Evolution X includes Google apps by default. For a vanilla build: WITH_GMS=false ./evox-release.sh build
  set +eu; source build/envsetup.sh
  breakfast malachite userdebug
  mka evolution 2>&1 | tee "$HOME/build-evox-$(date +%m%d-%H%M).log"
  ls -lh out/target/product/malachite/*.zip out/target/product/malachite/*.img 2>/dev/null
}

do_backup() {
  tar czf "$HOME/evox-keys-backup.tar.gz" -C "$SRC/vendor/evolution-priv" keys
  echo ">> $HOME/evox-keys-backup.tar.gz - download to your PC NOW. NEVER upload keys to GitHub."
}

do_clean() { rm -rf out/target/product/malachite; df -h . | tail -1; }

case "${1:-}" in
  init) do_init;; sync) do_sync;; keys) do_keys;; build) do_build;; backup) do_backup;; clean) do_clean;;
  *) sed -n '2,9p' "$0";;
esac
