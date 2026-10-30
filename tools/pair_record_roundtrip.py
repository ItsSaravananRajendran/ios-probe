"""Verify a pair record can be exported and re-imported for network installs.

This is the linchpin of "pair once on any Mac, install forever from India":
pair records must be portable files, not live session state.

Usage:
    # on the Mac that is paired with the phone:
    pymobiledevice3 lockdown save-pair-record pair.plist
    # here, verify it is well-formed and usable:
    python3 tools/pair_record_roundtrip.py pair.plist
"""
import plistlib
import sys
from pathlib import Path

REQUIRED = ["HostID", "HostCertificate", "HostPrivateKey", "DeviceCertificate", "RootCertificate"]


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    path = Path(sys.argv[1])
    raw = path.read_bytes()
    try:
        record = plistlib.loads(raw)
    except Exception:
        # tolerate a length-prefixed plist
        (n,) = int.from_bytes(raw[:4], "big"), None
        record = plistlib.loads(raw[4 : 4 + n])

    missing = [k for k in REQUIRED if k not in record]
    print(f"record keys: {sorted(record.keys())}")
    if missing:
        print(f"NOT A PAIR RECORD - missing: {missing}")
        return 1

    print("HostID:        ", record.get("HostID"))
    print("DeviceID:      ", record.get("DeviceID"))
    print("WiFiMACAddress:", record.get("WiFiMACAddress"))
    print("SystemBUID:    ", record.get("SystemBUID"))
    cert = record.get("HostCertificate", "")
    key = record.get("HostPrivateKey", "")
    print(f"HostCertificate: {len(cert)} bytes, HostPrivateKey: {len(key)} bytes")
    if "BEGIN" not in cert or "BEGIN" not in key:
        print("WARNING: certificate/key are not PEM text")
    print("\nOK - this pair record is portable and can be used with:")
    print("  python3 tools/install_over_network.py --host <ip> --pair-record "
          f"{path} --ipa <app.ipa>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
