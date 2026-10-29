#!/usr/bin/env bash
# Build an iOS .ipa from the mac mini (India) via GitHub Actions macOS runners,
# then optionally install it to the iPhone (US) over Tailscale.
#
# Usage:
#   ./ship.sh build                 # build unsigned ipa, download artifact
#   ./ship.sh sign                  # build + sign + package (self-signed proof)
#   ./ship.sh install <path.ipa>    # install a signed ipa to the iPhone
#   ./ship.sh info                  # show iPhone reachability + pairing state
set -euo pipefail

REPO="${REPO:-ItsSaravananRajendran/ios-probe}"
IPHONE_IP="${IPHONE_IP:-100.89.49.53}"
PM3="$HOME/Library/Python/3.9/bin/pymobiledevice3"
export PATH="$HOME/Library/Python/3.9/bin:$PATH"

here() { cd "$(dirname "$0")"; }

wait_for_run() {
  local wf="$1" rid
  rid=$(gh workflow run "$wf" --repo "$REPO" 2>&1 | grep -oE '[0-9]{10,}$' | tail -1)
  [ -n "$rid" ] || { echo "could not start $wf"; exit 1; }
  echo ">> $wf run $rid  (macOS runners are often queued 10-25 min)"
  gh run watch "$rid" --repo "$REPO" --exit-status
  echo "$rid"
}

case "${1:-}" in
  build)
    here
    rid=$(wait_for_run build-ios.yml)
    rm -rf out && mkdir -p out
    gh run download "$rid" --repo "$REPO" --name ProbeApp-ipa-macos-26 --dir out
    ls -la out/
    echo "IPA at: $(pwd)/out/ProbeApp.ipa  (unsigned — needs signing to install)"
    ;;

  sign)
    here
    rid=$(wait_for_run sign-test.yml)
    rm -rf out2 && mkdir -p out2
    gh run download "$rid" --repo "$REPO" --name SignedProbe-ipa --dir out2
    echo "signed ipa: $(pwd)/out2/SignedProbe.ipa  (self-signed — device will reject it)"
    ;;

  install)
    ipa="${2:?usage: ship.sh install <path.ipa>}"
    [ -f "$ipa" ] || { echo "no such file: $ipa"; exit 1; }
    echo ">> iPhone reachability"
    nc -G 5 -z -v "$IPHONE_IP" 62078 2>&1 | tail -1 || \
      echo "   lockdownd unreachable — wake/unlock the iPhone and retry"
    echo ">> installing"
    "$PM3" apps install "$ipa"
    ;;

  info)
    echo "== tailscale =="
    tailscale status 2>&1 | head -5
    echo "== lockdown port =="
    nc -G 5 -z -v "$IPHONE_IP" 62078 2>&1 | tail -1
    echo "== pairing record =="
    "$PM3" lockdown info 2>&1 | grep -v -i warning | head -10 || true
    ;;

  *)
    sed -n '2,12p' "$0"
    exit 1
    ;;
esac
