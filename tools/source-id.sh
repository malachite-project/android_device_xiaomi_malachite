#!/bin/bash
#
# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0
#
# Prints where the commit checked out in a tree comes from, for the
# ro.malachite.source.* properties set in device.mk:
#
#   <repository>@<commit>[-dirty][-unpublished]
#
# <repository> is the remote the commit was fetched from or pushed to (owner/name for
# GitHub, host/path otherwise, "local" for a remote on this machine). -dirty: the tree
# has uncommitted changes. -unpublished: no remote branch known to the tree contains
# the commit. "unknown" if the tree is missing or not its own git checkout.
#
#   source-id.sh --snapshot-id <source-manifest.xml> <tree>...
#
# prints ro.malachite.source.id: src-<hash of the snapshot from source-snapshot.sh>,
# with -untraceable if it lists uncommitted or unpushed projects and -stale if one of
# the given trees is no longer at the commit it records; "none" without a snapshot.

if [ "$1" = --snapshot-id ]; then
  snapshot=$2
  shift 2
  [ -f "$snapshot" ] || { echo none; exit 0; }
  id=src-$(sha256sum "$snapshot" | cut -c1-12)
  grep -q 'malachite-source: untraceable' "$snapshot" && id=$id-untraceable
  for tree in "$@"; do
    recorded=$(grep "path=\"$tree\"" "$snapshot" | head -n 1 |
      sed -n 's/.* revision="\([0-9a-f]*\)".*/\1/p')
    [ -n "$recorded" ] || continue
    [ "$(git -C "$tree" rev-parse HEAD 2>/dev/null)" = "$recorded" ] || { id=$id-stale; break; }
  done
  echo "$id"
  exit 0
fi

tree=${1:?tree}

commit=$(git -C "$tree" rev-parse --short=7 HEAD 2>/dev/null) &&
  top=$(git -C "$tree" rev-parse --show-toplevel 2>/dev/null) &&
  [ "$top" -ef "$tree" ] || { echo unknown; exit 0; }

dirty=
git -C "$tree" update-index -q --refresh >/dev/null 2>&1
git -C "$tree" diff-index --quiet HEAD -- 2>/dev/null || dirty=-dirty

remote=
published=-unpublished
for ref in $(git -C "$tree" for-each-ref --contains HEAD --format='%(refname:strip=2)' \
    refs/remotes 2>/dev/null); do
  case "$ref" in m/* | */HEAD) continue ;; esac
  candidate=${ref%%/*}
  candidate_url=$(git -C "$tree" remote get-url "$candidate" 2>/dev/null)
  case "$candidate_url" in
    "" | /* | .* | file://*) continue ;;
    *://* | *:*) ;;
    *) continue ;;
  esac
  remote=$candidate
  published=
  break
done
[ -n "$remote" ] || remote=$(git -C "$tree" remote 2>/dev/null | head -n 1)

url=$(git -C "$tree" remote get-url "$remote" 2>/dev/null)
case "$url" in
  "") repository=none ;;
  /* | .* | file://*) repository=local ;;
  *)
    # Drop the scheme, any user or token, the GitHub host and the .git suffix.
    repository=$(printf '%s\n' "$url" | sed -e 's#^[a-z+]*://##' -e 's#^[^@/]*@##' \
      -e 's#^\([^/:]*\):#\1/#' -e 's#^github\.com/##' -e 's#\.git$##' -e 's#/*$##' |
      tr -d ' ')
    ;;
esac

echo "${repository}@${commit}${dirty}${published}"
