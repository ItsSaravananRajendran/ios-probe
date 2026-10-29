"""Try a TLS-first lockdownd handshake on the network port.

iOS lockdownd on TCP may expect TLS immediately (rather than the USB
flow's plaintext-then-upgrade). This probes both orders and reports which
one the device accepts.
"""

import asyncio
import plistlib
import socket
import ssl
import struct
import sys

HOST = sys.argv[1] if len(sys.argv) > 1 else "100.89.49.53"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 62078

QUERY = {
    "Label": "HermesProbe",
    "Request": "QueryType",
    "BundlePath": "/System/Library/PrivateFrameworks/MobileDevice.framework",
}


def build_plist(d):
    """lockdownd frames plists as a 4-byte big-endian length + payload."""
    payload = plistlib.dumps(d, fmt=plistlib.FMT_XML)
    return struct.pack(">L", len(payload)) + payload


def parse_plist(data):
    if len(data) < 8:
        raise ValueError("short frame")
    (n,) = struct.unpack(">L", data[:4])
    return plistlib.loads(data[4 : 4 + n])


def probe_plaintext(host, port):
    try:
        s = socket.create_connection((host, port), timeout=10)
        s.sendall(build_plist(QUERY))
        s.settimeout(10)
        buf = b""
        while len(buf) < 4096:
            try:
                d = s.recv(4096)
            except socket.timeout:
                break
            if not d:
                break
            buf += d
        s.close()
        return buf
    except Exception as e:
        return b"ERR:" + str(e).encode()


def probe_tls(host, port):
    try:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ctx.set_ciphers("ALL:!aNULL:!eNULL")
        ctx.options |= 0x4  # OP_LEGACY_SERVER_CONNECT
        raw = socket.create_connection((host, port), timeout=10)
        s = ctx.wrap_socket(raw, server_hostname=host)
        s.sendall(build_plist(QUERY))
        s.settimeout(10)
        buf = b""
        while len(buf) < 4096:
            try:
                d = s.recv(4096)
            except (socket.timeout, ssl.SSLError):
                break
            if not d:
                break
            buf += d
        s.close()
        return buf
    except Exception as e:
        return b"ERR:" + str(e).encode()


def show(label, data):
    print(f"--- {label} ---")
    if data.startswith(b"ERR:"):
        print(" ", data.decode(errors="replace"))
        return
    print("  bytes:", len(data))
    try:
        p = parse_plist(data)
        for k in ("DeviceName", "ProductVersion", "BuildVersion", "ProductType"):
            if k in p:
                print(f"  {k} = {p[k]}")
        print("  keys:", sorted(p.keys())[:18])
    except Exception as e:
        print("  raw:", data[:220])


show("plaintext", probe_plaintext(HOST, PORT))
show("tls-first", probe_tls(HOST, PORT))
