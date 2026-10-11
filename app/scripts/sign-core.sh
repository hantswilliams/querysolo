#!/usr/bin/env bash
# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
#
# Sign the frozen core (core/dist/querysolo/) with the Developer ID before Tauri bundles it
# (ship-dmg-steps.md step 3). Tauri signs the app and its own binaries, not the executables
# and libraries under Resources/, and notarisation rejects an app with an unsigned Mach-O
# file anywhere in it. Every Mach-O file is signed with the hardened runtime, a secure
# timestamp and the app's entitlements; the libraries first, the executable that loads them
# last. Run from app/ (Tauri's beforeBundleCommand does).
#
# Without APPLE_SIGNING_IDENTITY (a local unsigned build, Linux, CI without the secrets) it
# does nothing, so an unsigned build keeps working.
set -euo pipefail

if [[ "$(uname)" != "Darwin" || -z "${APPLE_SIGNING_IDENTITY:-}" ]]; then
  echo "sign-core: no signing identity (or not macOS); the frozen core is left unsigned"
  exit 0
fi

core="../core/dist/querysolo"
exe="$core/querysolo"
entitlements="src-tauri/entitlements.plist"
[[ -x "$exe" ]] || { echo "sign-core: no frozen core at $core; run core/freeze/build.py first" >&2; exit 1; }

sign() {
  codesign --force --options runtime --timestamp --entitlements "$entitlements" \
    --sign "$APPLE_SIGNING_IDENTITY" "$1"
}

count=0
while IFS= read -r -d '' f; do
  [[ "$f" == "$exe" ]] && continue
  if file -b "$f" | grep -q "Mach-O"; then
    sign "$f" || { echo "sign-core: could not sign $f" >&2; exit 1; }
    count=$((count + 1))
  fi
done < <(find "$core" -type f -print0)
sign "$exe"
echo "sign-core: signed $count libraries and the querysolo executable with $APPLE_SIGNING_IDENTITY"
