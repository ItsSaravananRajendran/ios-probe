"""Probe whether lockdownd's TCP port accepts TLS at all.

If a TLS handshake succeeds (even with an untrusted client cert), the network
transport is fully usable and the ONLY missing piece is a trusted pairing
record. If it resets, the device refuses the transport outright.
"""
import asyncio
import os
import ssl
import subprocess
import sys
import tempfile

from pymobiledevice3.service_connection import ServiceConnection, create_ssl_context

HOST = sys.argv[1] if len(sys.argv) > 1 else "100.89.49.53"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 62078


def make_cert():
    d = tempfile.mkdtemp()
    key, cert = os.path.join(d, "k.pem"), os.path.join(d, "c.pem")
    subprocess.run(
        ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
         "-keyout", key, "-out", cert, "-days", "2", "-subj", "/CN=probe-host"],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    combined = os.path.join(d, "combined.pem")
    with open(combined, "w") as f:
        f.write(open(cert).read())
        f.write(open(key).read())
    return combined


async def main():
    pem = make_cert()
    ctx = create_ssl_context(pem)
    try:
        svc = await ServiceConnection.create_using_tcp(HOST, PORT, ssl_context=ctx)
        print("TLS HANDSHAKE OK -> transport works; only pairing/auth is missing")
        await svc.close()
    except Exception as e:
        print("TLS FAILED:", type(e).__name__, str(e)[:140])


asyncio.run(main())
