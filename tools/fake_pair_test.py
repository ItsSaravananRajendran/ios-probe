import asyncio, plistlib, subprocess, os, tempfile, ssl
from pymobiledevice3.lockdown import create_using_tcp

# Build a self-signed host identity to stand in for a real pair record's
# HostCertificate/HostPrivateKey, to see whether the device's behavior changes
# from "TCP reset" to "TLS-level" once a peer identity is presented.
d = tempfile.mkdtemp()
key = os.path.join(d, "k.pem"); cert = os.path.join(d, "c.pem")
subprocess.run(["openssl","req","-x509","-newkey","rsa:2048","-nodes","-keyout",key,
                "-out",cert,"-days","2","-subj","/CN=fake-host"], check=True,
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
host_cert = open(cert).read(); host_key = open(key).read()

pair_record = {
    "HostID": "0"*40,
    "SystemBUID": "0"*36,
    "HostCertificate": host_cert,
    "HostPrivateKey": host_key,
    "DeviceCertificate": host_cert,
    "RootCertificate": host_cert,
    "RootPrivateKey": host_key,
    "WiFiMACAddress": "00:00:00:00:00:00",
    "EscrowBag": b"",
}

async def main():
    for label, kwargs in (("with fake pair record", {"pair_record": pair_record}),):
        try:
            c = await create_using_tcp("100.89.49.53", port=62078, autopair=False,
                                       pair_timeout=10, **kwargs)
            vals = await c.get_values()
            print(label, "-> CONNECTED", {k: vals.get(k) for k in ("DeviceName","ProductVersion","UniqueDeviceID")})
            await c.close()
        except Exception as e:
            print(label, "->", type(e).__name__, str(e)[:120])
asyncio.run(main())
