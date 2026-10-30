#!/bin/bash
#
# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0
#
# Records the exact source of a ROM tree for the build that follows: every project's
# commit (repo manifest -r, which `repo init -m` can sync back), plus every project
# that has uncommitted changes or a commit on no remote branch, since nobody else can
# get those sources.
#
# Run it from the top of the tree after syncing and applying any patches, right before
# building. The build then puts the result in the ROM as
# /system_ext/etc/source/manifest.xml and its hash in ro.malachite.source.id.
#
#   bash device/xiaomi/malachite/tools/source-snapshot.sh [-o <file>]

set -e

device=$(cd "$(dirname "$0")/.." && pwd)
out=$device/source/source-manifest.xml
[ "$1" = -o ] && out=${2:?file}

[ -d .repo ] || { echo "Run this from the top of the ROM tree (where .repo is)." >&2; exit 1; }
command -v repo >/dev/null || { echo "repo is not in PATH." >&2; exit 1; }

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

echo "Recording the commit of every project..."
repo manifest -r -o "$tmp/manifest.xml" 2>/dev/null

echo "Checking every project for uncommitted or unpushed changes..."
# repo warns on stdout above 24 jobs, and only lines naming a project and its state
# count, so a warning can't mark the tree untraceable.
jobs=$(nproc)
[ "$jobs" -le 24 ] || jobs=24
# shellcheck disable=SC2016
repo forall -j"$jobs" -c '
  git update-index -q --refresh >/dev/null 2>&1
  state=
  git diff-index --quiet HEAD -- 2>/dev/null || state=uncommitted
  [ -n "$(git for-each-ref --contains HEAD --count=1 refs/remotes 2>/dev/null)" ] ||
    state="${state:+$state,}unpushed"
  [ -z "$state" ] || echo "$REPO_PATH $state"
' | grep -E '^[^ ]+ (uncommitted|unpushed|uncommitted,unpushed)$' | sort > "$tmp/state" || true

{
  sed '/<\/manifest>/d' "$tmp/manifest.xml"
  if [ -s "$tmp/state" ]; then
    echo "  <!-- malachite-source: untraceable"
    sed 's/^/       /' "$tmp/state"
    echo "  -->"
  else
    echo "  <!-- malachite-source: every project is at a published commit -->"
  fi
  echo "</manifest>"
} > "$tmp/source-manifest.xml"

mkdir -p "$(dirname "$out")"
mv "$tmp/source-manifest.xml" "$out"

echo
echo "Source ID: src-$(sha256sum "$out" | cut -c1-12)"
echo "Saved to $out; the build puts it in the ROM."
if [ -s "$tmp/state" ]; then
  echo
  echo "Not traceable: these projects have uncommitted or unpushed changes."
  echo "Commit and push them, then run this again:"
  sed 's/^/  /' "$tmp/state"
  exit 2
fi
