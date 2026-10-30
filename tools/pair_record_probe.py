"""Compare lockdownd-over-TCP behaviour with and without a pair record.

This tells us whether an EXPORTED pair record from another Mac is enough to
drive the device over Tailscale -- i.e. whether "pair once on any Mac, then
install from India forever" is technically sound.
"""
import asyncio
import os
import subprocess
import sys
import tempfile

from pymobiledevice3.lockdown import create_using_tcp

HOST = sys.argv[1] if len(sys.argv) > 1 else "100.89.49.53"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 62078


def fake_pair_record():
    d = tempfile.mkdtemp()
    key, cert = os.path.join(d, "k.pem"), os.path.join(d, "c.pem")
    subprocess.run(
        ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
         "-keyout", key, "-out", cert, "-days", "2", "-subj", "/CN=fake-host"],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    c, k = open(cert).read(), open(key).read()
    return {
        "HostID": "0" * 40, "SystemBUID": "0" * 36,
        "HostCertificate": c, "HostPrivateKey": k,
        "DeviceCertificate": c, "RootCertificate": c, "RootPrivateKey": k,
        "WiFiMACAddress": "00:00:00:00:00:00", "EscrowBag": b"",
    }


async def attempt(label, **kwargs):
    try:
        c = await create_using_tcp(HOST, port=PORT, pair_timeout=15, **kwargs)
        vals = await c.get_values()
        print(f"{label}: CONNECTED -> {vals.get('DeviceName')} / {vals.get('ProductVersion')}")
        await c.close()
    except Exception as e:
        print(f"{label}: {type(e).__name__}: {str(e)[:110]}")


async def main():
    await attempt("no pair record      ", autopair=False)
    await attempt("fake pair record    ", autopair=False, pair_record=fake_pair_record())

asyncio.run(main())
