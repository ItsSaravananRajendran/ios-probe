# ios-probe — building iOS apps on the mac mini (India) for an iPhone (US)

The mac mini in India has **no Xcode** and Apple's Xcode download is
Apple-ID-gated, so **building happens on GitHub Actions macOS runners**
(which ship Xcode preinstalled) and the artifact comes back as an `.ipa`.

The iPhone in the US is already enrolled in the same **Tailscale** tailnet
as the mac mini (`sarav201997@`), so it is reachable from India without
putting anything on the public internet.

## Verified working

| Step | Status |
|---|---|
| SwiftUI app → Xcode project (`xcodegen`) | working |
| Unsigned Release build for `generic/platform=iOS` | working |
| Package `.ipa` (`Payload/` + zip) | working |
| codesign with entitlements, `codesign --verify` | working |
| Binary check: Mach-O arm64, `platform 2` (iOS), `minos 17.0` | working |
| GitHub Actions macOS runner | working (queue is slow, ~10–25 min) |

## Layout

```
project.yml                 # XcodeGen source of truth (bundle id, deployment target)
ProbeApp/Sources/           # SwiftUI sources
.github/workflows/
  build-ios.yml             # unsigned IPA (matrix over macOS runner labels)
  sign-test.yml             # proves codesign+entitlements+packaging in CI
  testflight.yml            # signed IPA uploaded to App Store Connect
```

## Why CI and not the mac mini

- `download.developer.apple.com` returns `302 → /unauthorized/` for every
  Xcode version without an Apple ID session, so a local Xcode install needs
  the user's Apple ID (and `mas install` additionally needs sudo, which this
  box does not have passwordless).
- GitHub Actions `macos-15` / `macos-26` runners have Xcode already
  installed, so a build costs nothing locally and needs no credentials.

## Install paths to the iPhone

### The blocker that is NOT signing: device pairing

The iPhone's `lockdownd` listens on TCP 62078 and **accepts the connection over
Tailscale**, but it resets the connection the moment a client speaks to it
without a valid pairing record. Measured directly:

- `nc -z` to `100.89.49.53:62078` -> `succeeded`
- send a length-prefixed lockdown plist -> `Connection reset by peer`
- connect and read without sending -> the socket is closed immediately

So the phone is **reachable but not yet paired**. Pairing options, all tested
from the mac mini:

| Route | Result |
|---|---|
| `pymobiledevice3 lockdown pair` (USB) | no USB device attached |
| `pymobiledevice3 bonjour mobdev2` / `rsd` | `[]` — mDNS does not cross Tailscale |
| `pymobiledevice3 remote pair` | "No devices were found during bonjour browse" |
| `pymobiledevice3 remote start-tunnel --native` | "remotepairingd reported no device" (no Apple ID signed into this Mac) |
| port 58783 (RSD / wireless debug) | connection refused — Developer Mode is off on the phone |
| port 27015 (usbmux over network) | connection refused |

**To pair the phone from the mac mini, enable Developer Mode on the iPhone**
(Settings > Privacy & Security > Developer Mode) and turn on
**Settings > Developer > Connect via Network**. That opens the RSD service and
lets `pymobiledevice3` establish a tunnel over Tailscale without a USB cable.
Without it, the only pairing route is a physical USB connection to some Mac.

### A. TestFlight (recommended — needs the paid Apple Developer Program, $99/yr)

No physical connection to the phone, no Mac in the US, and it does **not**
require Developer Mode.

1. In the Apple Developer portal, create an **App Store Connect API key**
   (Admin → Keys → App Store Connect) and download the `.p8`.
2. Create an **Apple Distribution** certificate (`.p12`) and a
   **distribution provisioning profile** that includes the iPhone's UDID
   (or use `TestFlight` internal testing, which does not need the UDID).
3. Store them as repo secrets:
   `ASC_KEY_ID`, `ASC_ISSUER_ID`, `ASC_PRIVATE_KEY`, `IOS_CERT_P12`,
   `IOS_CERT_PASSWORD`, `IOS_PROFILE`, `IOS_TEAM_ID`.
   ```bash
   gh secret set ASC_KEY_ID --repo ItsSaravananRajendran/ios-probe
   base64 -i cert.p12 | gh secret set IOS_CERT_P12 --repo ItsSaravananRajendran/ios-probe
   base64 -i profile.mobileprovision | gh secret set IOS_PROFILE --repo ItsSaravananRajendran/ios-probe
   ```
4. Run the `Build + TestFlight` workflow. It preflights the secrets (failing
   fast with the exact missing names), archives, signs, exports, and uploads
   with `xcrun altool`.
5. On the iPhone: install the **TestFlight** app from the App Store, accept
   the invitation, install the build. Builds last 90 days.

### B. Free Apple ID (no $99, but 7-day expiry and more friction)

- Register the iPhone's UDID in the Apple Developer portal.
- Build with a **development** profile; the app stops launching after 7 days
  and must be re-signed and reinstalled.
- Reinstalling still needs a transport to the phone. Over Tailscale this
  means either SideStore/AltStore, or `pymobiledevice3 apps install` once a
  pairing record exists.

### C. Direct install over Tailscale (after pairing)

`pymobiledevice3` is installed on the mac mini (`~/Library/Python/3.9/bin`).

The phone's `lockdownd` (port 62078) IS reachable over Tailscale at
`100.89.49.53` when the phone is awake/unlocked — but it resets every protocol
exchange until this host is a trusted peer. Pairing routes, all tested:

| Route | Result |
|---|---|
| `pymobiledevice3 lockdown pair` (USB) | no USB device attached |
| `pymobiledevice3 bonjour mobdev2` / `rsd` | `[]` — mDNS does not cross Tailscale |
| `pymobiledevice3 remote pair` | "No devices were found during bonjour browse" |
| `pymobiledevice3 remote start-tunnel --native` | "remotepairingd reported no device" (no Apple ID signed into this Mac) |
| `idevice_id -n` / `ideviceinfo -n` (libimobiledevice) | "No device found!" — network mode needs usbmuxd on 27015, refused |
| port 58783 (RSD / wireless debug) | connection refused — Developer Mode is off on the phone |
| port 27015 (usbmux over network) | connection refused |
| ports 49152 / 49918 / 62742 | other iOS services, not RSD ("did not answer the RemoteXPC handshake") |

`pymobiledevice3 doctor` states the rule: *"a device advertises one tag per
paired host, so an unpaired host cannot recognise it however the setting is
set."* Apple's wireless debugging is Bonjour/mDNS by design and does not route
across networks.

**The practical unlock: export a pair record from a Mac that has already
paired with the phone** (Xcode's *Connect via network*, or any Mac that touched
it over USB), then copy it to the mac mini. Pair records are portable — they
carry the host cert/key, the device cert, and the root — so the receiving
machine becomes a trusted peer of the device.

On the paired Mac:
```bash
pymobiledevice3 lockdown save-pair-record ~/pair.plist
# or, if it was paired over USB:
ls /var/db/lockdown/*.plist
```

Then on the mac mini:
```bash
export PATH="$HOME/Library/Python/3.9/bin:$PATH"

# 1. check every prerequisite
./tools/bootstrap_network_install.sh ~/pair.plist

# 2. install
python3 tools/install_over_network.py \
  --host 100.89.49.53 \
  --pair-record ~/pair.plist \
  --ipa ./App.ipa
```

That script loads the pair record, opens lockdown over Tailscale, and drives
`installation_proxy.install_from_local`. On failure it prints the fix instead
of a traceback.

`tools/bootstrap_network_install.sh` checks all three prerequisites (tailnet
reachability, lockdownd port open, pair record validity) and reports exactly
what is missing. `tools/pair_record_roundtrip.py` validates that a pair record
is a portable file.

**Port map of the iPhone over Tailscale** (measured by sweeping 1–65535 while
the phone was awake): only four ports are open — 49152, 49918, 62078
(lockdownd), 62742. Ports 1024–49151 are entirely closed; 27015 (usbmuxd
network) and 58783 (RSD) are refused. The other three are iOS internals, not
RSD ("did not answer the RemoteXPC handshake"). The phone **sleeps** — ports
appear and vanish as it wakes, so re-check before concluding anything.

**xtool hits the same wall**: it uses SwiftyMobileDevice's
`DEVICE_LOOKUP_NETWORK` (usbmuxd Bonjour discovery), so `xtool devices
--network` and `xtool install --network` cannot see an unpaired phone across
Tailscale either. `xtool install` also requires `xtool auth` first.

`tools/probe_transport.py` re-runs the pairing diagnostics; pass the phone's
tailnet IP to check the current state.

## Troubleshooting

- **CI queued for 20+ min** — macOS runner capacity. The build matrix tries
  `macos-15`, `macos-15-arm64`, `macos-26`, `macos-latest`; the first label
  to get a runner wins. `ubuntu-latest` starts in ~10s, so use it to check
  that Actions itself works.
- **`security: SecKeychainItemImport: The specified keychain could not be
  found`** — `security create-keychain` must run before `security import`.
- **`The specified item could not be found in the keychain`** on `codesign` —
  the signing cert needs `extendedKeyUsage=codeSigning`, otherwise codesign
  will not list the identity.
- **Repo is private** — GitHub Free only provides macOS runners to public
  repos. `gh repo edit <owner>/<repo> --visibility public`.
