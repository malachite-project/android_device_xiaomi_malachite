#!/bin/bash
# Apply the malachite-specific commits on top of crDroid's own framework repos.
# Run from the Android source root, AFTER `repo sync`, BEFORE `breakfast`.
# Tested against crDroid 16.0 on 2026-10-22 (all commits below applied cleanly or were already present).
# Safe to run twice: commits already in the tree are skipped.
set -u
ROOT=$(pwd)
BASE=https://github.com/malachite-project
git config --global user.name  >/dev/null 2>&1 || git config --global user.name  "builder"
git config --global user.email >/dev/null 2>&1 || git config --global user.email "builder@localhost"

apply() {  # apply <path> <repo-name> <sha>...
  local path=$1 repo=$2; shift 2
  [ -d "$ROOT/$path" ] || { echo "!! missing $path"; FAIL=1; return; }
  cd "$ROOT/$path" || return
  git remote remove malachite 2>/dev/null
  git remote add malachite "$BASE/$repo"
  git fetch -q --no-tags malachite lineage-23.2 || { echo "!! fetch failed: $repo"; FAIL=1; cd "$ROOT"; return; }
  for sha in "$@"; do
    local subj; subj=$(git log -1 --format=%s "$sha" 2>/dev/null)
    if [ -z "$subj" ]; then echo "!! $path: commit $sha not found (fork was rebased?)"; FAIL=1; continue; fi
    if git cherry-pick -x "$sha" >/dev/null 2>&1; then
      echo "ok       $path: $subj"
    elif [ -z "$(git status --porcelain | grep -v '^??')" ]; then
      git cherry-pick --skip >/dev/null 2>&1 || git cherry-pick --abort >/dev/null 2>&1
      echo "present  $path: $subj (already in crDroid)"
    else
      git cherry-pick --abort >/dev/null 2>&1
      echo "!! CONFLICT $path: $subj"; FAIL=1
    fi
  done
  cd "$ROOT"
}
FAIL=0

# Face unlock fix, backlight, voice-call volume, market name
apply frameworks/base android_frameworks_base \
  92a5e79525b15c1fc596f56c44c3e4d4ec00f230 \
  f61033b480ec1eb9dbfb7c56c798f546d9c7c2f9 \
  30a81f64116efad3d00ba421579bbdc07c84971a \
  af3e3bc601f69e2f36ba30c9ac0939dbb34d2984
# libgui ABI fix (needed for the MediaTek blobs)
apply frameworks/native android_frameworks_native \
  4fbba134a20d5c565709607fe095bae368043659
# Native eSIM
apply packages/apps/Settings android_packages_apps_Settings \
  0d78ceaf31e94250f1f8d1c66a1b98b81bb8a96c
apply packages/services/Telephony android_packages_services_Telephony \
  f20390c0cc976c18618fdda2bb155313b23ba923 \
  fc67e9d80276175a24332fe8afe2f106c548274f
# Bluetooth A2DP offload coex fix
apply packages/modules/Bluetooth android_packages_modules_Bluetooth \
  11dfd43472a428c0af0fae4ff3903070fb8d00aa
# WPA3 opt-out for the MediaTek WiFi driver
apply external/wpa_supplicant_8 android_external_wpa_supplicant_8 \
  0cd9f1c12855f7233ea487af9fe33928534c1d29

[ "$FAIL" = 0 ] && echo "DONE: all patches applied." || echo "DONE WITH PROBLEMS: see lines starting with '!!' above."
exit $FAIL
