import asyncio
import sys

from pymobiledevice3.lockdown import create_using_tcp

HOST = sys.argv[1] if len(sys.argv) > 1 else "100.89.49.53"


async def main():
    try:
        c = await create_using_tcp(HOST, port=62078, autopair=True, pair_timeout=20)
        vals = await c.get_values()
        for k in (
            "DeviceName",
            "ProductVersion",
            "BuildVersion",
            "UniqueDeviceID",
            "ProductType",
            "DeviceClass",
            "WiFiAddress",
        ):
            if k in vals:
                print(f"{k} = {vals[k]}")
        print("--- lockdown info ---")
        info = await c.lockdown_info()
        for k in ("DeviceName", "ProductVersion", "UniqueDeviceID", "ProductType"):
            if k in info:
                print(f"  {k} = {info[k]}")
        await c.close()
    except Exception as e:
        print("ERR:", type(e).__name__, e)


asyncio.run(main())
