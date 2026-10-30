#!/usr/bin/env bash
# Bootstrap a network-install path to the iPhone (US) from the mac mini (India).
#
# The phone is reachable over Tailscale (100.89.49.53) but iOS only talks to
# hosts it has paired with. Pair records are portable files, so the fix is:
#
#   1. On ANY Mac that has touched the phone (USB once, or Xcode's
#      "Connect via network"), export the pair record.
#   2. Copy that file to the mac mini (Tailscale, AirDrop, email, whatever).
#   3. Run this script here.
#
# Then installs work over the network with no cable and no Mac in the US:
#   python3 tools/install_over_network.py --host 100.89.49.53 \
#       --pair-record ~/pair.plist --ipa ./App.ipa
#
# This script verifies the pair record and the phone's reachability, and tells
# you exactly what is missing.
set -uo pipefail

HOST="${IPHONE_IP:-100.89.49.53}"
PAIR="${1:-$HOME/pair.plist}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
PM3="$HOME/Library/Python/3.9/bin/pymobiledevice3"
export PATH="$HOME/Library/Python/3.9/bin:$PATH"

ok=0
fail=0
say() { printf "%s\n" "$*"; }
check() { if [ "$1" = "0" ]; then echo "  OK   $2"; ok=$((ok+1)); else echo "  FAIL $2"; fail=$((fail+1)); fi; }

say "=== 1. Tailscale ==="
if command -v tailscale >/dev/null 2>&1; then
  tailscale status 2>/dev/null | grep -i iphone | head -2
  tailscale ping -c 1 --timeout 8s iphone-11 >/dev/null 2>&1
  check $? "phone reachable over the tailnet"
else
  echo "  FAIL tailscale not installed"; fail=$((fail+1))
fi

say ""
say "=== 2. Phone's lockdownd reachable at $HOST:62078 ==="
nc -G 5 -z "$HOST" 62078 >/dev/null 2>&1
check $? "lockdownd port open (phone awake and unlocked)"

say ""
say "=== 3. Pair record ==="
if [ -f "$PAIR" ]; then
  python3 "$HERE/tools/pair_record_roundtrip.py" "$PAIR" 2>&1 | sed 's/^/  /'
  check $? "pair record is valid and portable"
else
  echo "  FAIL no pair record at $PAIR"
  echo ""
  echo "  Produce one on a Mac that has paired with the phone:"
  echo "    pymobiledevice3 lockdown save-pair-record ~/pair.plist"
  echo "  (or, if it was paired over USB: ls /var/db/lockdown/*.plist)"
  fail=$((fail+1))
fi

say ""
say "=== 4. Install path ==="
if [ -f "$PAIR" ]; then
  say "  ready: python3 tools/install_over_network.py --host $HOST --pair-record $PAIR --ipa <app.ipa>"
else
  say "  blocked on the pair record above"
fi

say ""
say "passed=$ok failed=$fail"
[ "$fail" -eq 0 ]
