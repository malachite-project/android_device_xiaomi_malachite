#!/bin/bash
# Apply the malachite-specific commits on top of crDroid's own framework repos.
# Run from the Android source root, AFTER `repo sync`, BEFORE `breakfast`.
# Tested against crDroid 16.0 on 2026-10-23. Safe to run twice: commits already in the tree are skipped.
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
    if git log -n 300 --format=%B HEAD | grep -qF "cherry picked from commit $sha"; then
      echo "present  $path: $subj (applied by an earlier run)"; continue
    fi
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
