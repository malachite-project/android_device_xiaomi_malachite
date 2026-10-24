#!/bin/bash
# Apply the malachite-specific commits on top of Evolution X's own repos.
# Run from the Android source root, AFTER `repo sync`, BEFORE `breakfast`.
# Tested 2026-10-23 against Evolution X bka. Safe to run twice (applied commits are skipped).
# Modes: (none) plain cherry-pick | theirs = take the patch on conflict | both = keep both sides on conflict
set -u
ROOT=$(pwd)
BASE=https://github.com/malachite-project
git config --global user.name  >/dev/null 2>&1 || git config --global user.name  "builder"
git config --global user.email >/dev/null 2>&1 || git config --global user.email "builder@localhost"
FAIL=0

keep_both() {   # resolve every conflict hunk by keeping our side, then the patch's side
  python3 -I - <<'PY'
import re, subprocess
files = subprocess.run(['git','diff','--name-only','--diff-filter=U'], capture_output=True, text=True).stdout.split()
for f in files:
    s = open(f).read()
    s = re.sub(r'<<<<<<< [^\n]*\n(.*?)=======\n(.*?)>>>>>>> [^\n]*\n', lambda m: m.group(1)+m.group(2), s, flags=re.S)
    open(f, 'w').write(s)
    subprocess.run(['git','add',f])
PY
  git -c core.editor=true cherry-pick --continue >/dev/null 2>&1
}

apply() {  # apply <path> <repo-name> <sha[:mode]>...
  local path=$1 repo=$2; shift 2
  [ -d "$ROOT/$path" ] || { echo "!! missing $path"; FAIL=1; return; }
  cd "$ROOT/$path" || return
  git remote remove malachite 2>/dev/null
  git remote add malachite "$BASE/$repo"
  git fetch -q --no-tags malachite lineage-23.2 || { echo "!! fetch failed: $repo"; FAIL=1; cd "$ROOT"; return; }
  local item sha mode subj
  for item in "$@"; do
    sha=${item%%:*}; mode=""; [ "$item" != "$sha" ] && mode=${item#*:}
    subj=$(git log -1 --format=%s "$sha" 2>/dev/null)
    if [ -z "$subj" ]; then echo "!! $path: commit $sha not found (fork was rebased?)"; FAIL=1; continue; fi
    if git log -n 300 --format=%B HEAD | grep -qF "cherry picked from commit $sha"; then
      echo "present  $path: $subj (already applied by an earlier run)"; continue
    fi
    local opts=(-x); [ "$mode" = theirs ] && opts+=(-X theirs)
    if git cherry-pick "${opts[@]}" "$sha" >/dev/null 2>&1; then
      echo "ok       $path: $subj${mode:+ [$mode]}"
    elif [ -z "$(git status --porcelain | grep -v '^??')" ]; then
      git cherry-pick --skip >/dev/null 2>&1 || git cherry-pick --abort >/dev/null 2>&1
      echo "present  $path: $subj (already in tree)"
    elif [ "$mode" = both ] && keep_both; then
      echo "ok       $path: $subj [both sides kept]"
    else
      git cherry-pick --abort >/dev/null 2>&1
      echo "!! CONFLICT $path: $subj"; FAIL=1
    fi
  done
  cd "$ROOT"
}

# Port malachite's final GED KPI code (GPU frequency scaling) into this tree's older libgui.
# The tree already has the first GED KPI patch under the flag ENABLE_MTK_GED_KPI; malachite's three
# later fixes (fail closed, keep Surface layout, probe without a fence) cannot be cherry-picked, so
# we 3-way merge the files: base = their first GED commit, theirs = their final commit, ours = this tree.
ged_port() {
  local path=frameworks/native B=4655ab6a019257d244ddaf50a2270109291c803c T=5fc726ef7558d12da2600cb062047797eb3e00d5
  [ -d "$ROOT/$path" ] || return
  cd "$ROOT/$path" || return
  if git log -n 300 --format=%B HEAD | grep -qF "Port malachite GED KPI fixes"; then
    echo "present  $path: GED KPI fixes (already ported)"; cd "$ROOT"; return
  fi
  if ! git cat-file -e "$B" 2>/dev/null || ! git cat-file -e "$T" 2>/dev/null; then
    echo "!! $path: GED KPI commits not fetched"; FAIL=1; cd "$ROOT"; return
  fi
  local tmp f rc=0; tmp=$(mktemp -d)
  for f in libs/gui/Surface.cpp libs/gui/include/gui/Surface.h libs/gui/Android.bp; do
    git show "$B:$f" > "$tmp/base" && git show "$T:$f" > "$tmp/theirs" && git show "HEAD:$f" > "$tmp/ours" || { rc=1; break; }
    sed -i -E 's/([^_A-Z])MTK_GED_KPI/\1ENABLE_MTK_GED_KPI/g' "$tmp/base" "$tmp/theirs"
    git merge-file --theirs "$tmp/ours" "$tmp/base" "$tmp/theirs"; [ $? -le 127 ] || rc=1
    cp "$tmp/ours" "$f"
  done
  python3 -I - <<'PY' || rc=1
p = "libs/gui/include/gui/Surface.h"; s = open(p).read()
blk = "    #ifdef ENABLE_MTK_GED_KPI\n    pid_t mPid;\n    bool mIsSurfaceFlinger;\n    #endif\n"
if blk in s: open(p, "w").write(s.replace(blk, "", 1).replace("\n\n\n", "\n\n"))
PY
  if [ $rc -eq 0 ] && ! grep -q '^<<<<<<<' libs/gui/Surface.cpp && \
     [ "$(grep -cE '^\s*#\s*(if|ifdef|ifndef)\b' libs/gui/Surface.cpp)" = "$(grep -cE '^\s*#\s*endif\b' libs/gui/Surface.cpp)" ]; then
    git add libs/gui && git commit -q -m "libgui: Port malachite GED KPI fixes ($B..$T)" && echo "ok       $path: GED KPI fixes ported (3-way merge)"
  else
    git checkout -q -- libs/gui; echo "!! $path: GED KPI port failed (left unchanged)"; FAIL=1
  fi
  rm -rf "$tmp"; cd "$ROOT"
}

# Face unlock fix, backlight, voice-call volume
apply frameworks/base android_frameworks_base 92a5e79525b15c1fc596f56c44c3e4d4ec00f230 f61033b480ec1eb9dbfb7c56c798f546d9c7c2f9 30a81f64116efad3d00ba421579bbdc07c84971a
# libgui ABI for the MediaTek blobs (Evolution X's libgui lacks the out-of-line symbols)
apply frameworks/native android_frameworks_native 4fbba134a20d5c565709607fe095bae368043659:theirs
ged_port
# Native eSIM (Evolution X has its own EsimSettings row; keep both)
apply packages/apps/Settings android_packages_apps_Settings 0d78ceaf31e94250f1f8d1c66a1b98b81bb8a96c:both
apply packages/services/Telephony android_packages_services_Telephony f20390c0cc976c18618fdda2bb155313b23ba923 fc67e9d80276175a24332fe8afe2f106c548274f
# Bluetooth A2DP offload coex fix
apply packages/modules/Bluetooth android_packages_modules_Bluetooth 11dfd43472a428c0af0fae4ff3903070fb8d00aa
# WPA3 opt-out for the MediaTek WiFi driver
apply external/wpa_supplicant_8 android_external_wpa_supplicant_8 0cd9f1c12855f7233ea487af9fe33928534c1d29

# device.mk: Evolution X already ships FaceUnlock (same package as ParanoidSense), so the
# ParanoidSense module does not exist here. Remove the line locally (fix your fork too).
DM="$ROOT/device/xiaomi/malachite/device.mk"
if [ -f "$DM" ] && grep -q '^    ParanoidSense$' "$DM"; then
  python3 -I - "$DM" <<'PY'
import sys
p = sys.argv[1]; s = open(p).read()
old = "PRODUCT_PACKAGES += \\\n    ParanoidSense\n"
assert old in s, "ParanoidSense block not in the expected form - edit device.mk by hand"
open(p, "w").write(s.replace(old, ""))
PY
  [ $? -eq 0 ] && echo "ok       device.mk: removed ParanoidSense (Evolution X ships FaceUnlock)" || { echo "!! device.mk edit failed"; FAIL=1; }
fi

# Maintainer card in Settings > About phone (Evolution X shows it from this string on unofficial builds;
# "Unknown" hides the card). Name + link are set in Evolution X's own Settings resources.
MAINTAINER=${MAINTAINER:-RidhzXLabs}
DONATE_URL=${DONATE_URL:-https://github.com/ridhzlabs}
ES="$ROOT/packages/apps/Settings/res/values/evolution_strings.xml"
if [ -f "$ES" ] && grep -q 'name="build_maintainer_summary"' "$ES"; then
  sed -i -E "s|(<string name=\"build_maintainer_summary\"[^>]*>)[^<]*(</string>)|\1${MAINTAINER}\2|; s|(<string name=\"build_maintainer_donate_url\"[^>]*>)[^<]*(</string>)|\1${DONATE_URL}\2|" "$ES"
  grep -q "build_maintainer_summary\"[^>]*>${MAINTAINER}<" "$ES" && echo "ok       maintainer set to '${MAINTAINER}' (link: ${DONATE_URL})" || { echo "!! maintainer edit failed"; FAIL=1; }
else
  echo "!! $ES: build_maintainer_summary not found"; FAIL=1
fi

[ "$FAIL" = 0 ] && echo "DONE: all patches applied." || echo "DONE WITH PROBLEMS: see lines starting with '!!' above."
exit $FAIL
