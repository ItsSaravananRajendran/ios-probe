"""Install an .ipa onto a remote iPhone over Tailscale.

Why this exists
---------------
The iPhone and the mac mini are on the same Tailscale tailnet, so the phone
is IP-reachable from India. But iOS lockdownd refuses to talk to an unpaired
host: it accepts the TCP connection on 62078 and then resets it. Measured:

    nc -z 100.89.49.53 62078          -> succeeded
    framed QueryType plist            -> Connection reset by peer
    TLS handshake                      -> Connection reset by peer
    with a pair record loaded         -> Connection reset by peer

So the transport is reachable; only TRUST is missing. This script therefore
takes a pair record exported from a Mac that has already paired with the phone
(Xcode's "Connect via network" pairing, or any Mac that touched it over USB)
and uses it to drive lockdownd + installation_proxy over Tailscale.

Pair records are per-host but portable: they contain the host cert/key, the
device cert, and the root. Copying one to another machine makes that machine
a trusted peer of the device.

Usage
-----
    # export the pair record on the Mac that is paired with the phone:
    #   pymobiledevice3 lockdown save-pair-record /path/to/pair.plist
    #   (or: ls /var/db/lockdown/*.plist  on that Mac)

    python3 install_over_network.py \
        --host 100.89.49.53 \
        --pair-record ~/pair.plist \
        --ipa ./MyApp.ipa
"""

import argparse
import asyncio
import plistlib
import ssl
import struct
import sys
from pathlib import Path

from pymobiledevice3.lockdown import create_using_tcp
from pymobiledevice3.services.installation_proxy import InstallationProxyService


def load_pair_record(path: Path) -> dict:
    data = path.read_bytes()
    try:
        record = plistlib.loads(data)
    except Exception:
        record = plistlib.loads(data[8:])  # strip a length prefix if present
    if "HostCertificate" not in record:
        raise SystemExit(f"{path} does not look like a pair record (no HostCertificate)")
    return record


async def main() -> int:
    ap = argparse.ArgumentParser(description="Install an .ipa on a remote iPhone over Tailscale")
    ap.add_argument("--host", required=True, help="phone's Tailscale IP")
    ap.add_argument("--port", type=int, default=62078, help="lockdownd port (default 62078)")
    ap.add_argument("--ipa", required=True, type=Path, help="path to .ipa")
    ap.add_argument("--pair-record", type=Path, help="exported pair record (.plist)")
    ap.add_argument("--developer", action="store_true", help="install as developer package")
    ap.add_argument("--timeout", type=float, default=30.0)
    args = ap.parse_args()

    if not args.ipa.exists():
        raise SystemExit(f"no such ipa: {args.ipa}")

    pair_record = load_pair_record(args.pair_record) if args.pair_record else None
    if pair_record is None:
        print("WARNING: no pair record supplied. lockdownd will reset the connection\n"
              "         because this host is not a trusted peer of the device.", file=sys.stderr)

    try:
        lockdown = await asyncio.wait_for(
            create_using_tcp(
                args.host,
                port=args.port,
                autopair=False,
                pair_record=pair_record,
                pair_timeout=args.timeout,
            ),
            timeout=args.timeout,
        )
    except Exception as e:
        print(f"FAILED to open lockdown session: {type(e).__name__}: {e}", file=sys.stderr)
        print("\nThe usual cause is a missing/incorrect pair record. The phone accepts the TCP\n"
              "connection but resets it because this host is not trusted.\n\n"
              "Fix: on a Mac that has paired with the phone, run:\n"
              "  pymobiledevice3 lockdown save-pair-record ./pair.plist\n"
              "and pass that file here with --pair-record.", file=sys.stderr)
        return 1

    try:
        values = await lockdown.get_values()
        print(f"connected: {values.get('DeviceName')} / iOS {values.get('ProductVersion')} / "
              f"{values.get('ProductType')}")
        print(f"udid: {values.get('UniqueDeviceID')}")
        await InstallationProxyService(lockdown=lockdown).install_from_local(
            args.ipa, developer=args.developer
        )
        print(f"INSTALL OK: {args.ipa.name}")
        return 0
    except Exception as e:
        print(f"INSTALL FAILED: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    finally:
        try:
            await lockdown.close()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
