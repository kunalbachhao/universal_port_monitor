# Centralized USB Device Monitoring and Alert System

CNL mini project. Lab PCs (clients) watch for USB storage devices being plugged in
or removed, and report each event over **TCP/IP** to a central server on the
invigilator's PC. The server shows an alert and writes the event to `logs/events.csv`.

It **only reports** that a device was plugged in or removed. It does not block USB,
read files, or decide that anyone cheated. The invigilator makes that call.

```
              CENTRAL SERVER (invigilator PC, TCP port 5000)
                              |
                         TCP / LAN
              +---------------+---------------+
          LAB-PC-01       LAB-PC-02       LAB-PC-03
          client.py       client.py       client.py
             USB             USB             USB
```

## Requirements

- Windows 10/11 and Python 3.8 or newer (developed on Python 3.14)
- No third-party packages (only `socket`, `threading`, `json`, `csv`, `ctypes`)
- All PCs on the same LAN / Wi-Fi

## Files

| File | Purpose |
|------|---------|
| `server/server.py` | Multi-client TCP server: alerts, connected-client count |
| `server/event_logger.py` | Appends USB events to `logs/events.csv` |
| `server/config.py` | Server port, timeout, log path |
| `client/client.py` | Connects to server, sends events, reconnects automatically |
| `client/usb_monitor.py` | Detects USB storage drives (Windows API via `ctypes`) |
| `client/config.py` | Server IP/port, PC name, intervals |
| `shared/protocol.py` | JSON message format shared by both sides |
| `tests/` | Unit and integration tests |
| `*.bat` | Double-click launchers (`setup`, `start_server`, `start_client`, `test_connection`, `test_usb`, `allow_firewall`, `autostart_client`) |
| `scripts/find_python.bat` | Helper used by the launchers to locate Python |
| `How To Run.md` | Step-by-step guide using the launchers |
| `WORKFLOW.md` | Phase checklist and test report |

## Quick start (double-click)

1. On every laptop: `setup.bat`. On the server, press **Y** to add the firewall rules.
2. Server laptop: `start_server.bat`
3. Client laptops: `start_client.bat`. The server is found automatically by UDP broadcast.

See **How To Run.md** for the full walkthrough. The command-line equivalents follow.

## Automatic server discovery

When `SERVER_IP = "auto"` (the default in `client/config.py`), the client broadcasts the
UDP packet `USB_MONITOR_DISCOVER` to port 5001. The server replies with
`{"service": "USB_MONITOR_SERVER", "port": 5000}`. The reply's source IP is the server's IP,
and the client then opens the normal TCP connection. If the network blocks broadcasts,
set `SERVER_IP` to the real address or pass `--server <IP>`.

## Command line

All commands are run from the `USB_Monitoring_System` folder.

### 1. Server (invigilator laptop)

```bash
python server\server.py
```

```
====================================================
  CENTRAL USB MONITORING SERVER
====================================================

Server IP : 192.168.1.100
Port      : 5000

Waiting for clients...
```

The first time it runs, **Windows Firewall** asks whether Python may accept
connections. Choose **Allow** on *Private networks*. If you skip this, clients on
other laptops cannot connect. Make sure the Wi-Fi network is set to *Private*, not *Public*.

### 2. Connectivity test (client laptop)

```bash
ping 192.168.1.100
```

```bash
python client\client.py --server 192.168.1.100 --test
```

Client output: `Connected to server.` / `Message sent successfully.`
Server output: `Received from DESKTOP-XYZ (192.168.1.105): Hello from examination PC`

### 3. Start monitoring (client laptop)

```bash
python client\client.py --server 192.168.1.100
```

To skip typing `--server` every time, set `SERVER_IP` in `client/config.py`.
To show a lab name instead of the hostname, add `--name LAB-PC-01`.

Now plug in a pen drive. The server shows:

```
====================================================
                     USB ALERT
====================================================
PC Name    : LAB-PC-02
IP Address : 192.168.1.102   (socket peer: 192.168.1.102)
Event      : USB INSERTED
Drive      : E:
Time       : 16:42:15
Connected clients: 2
====================================================
```

### Testing USB detection alone

```bash
python client\usb_monitor.py
```

This prints `USB_INSERTED  Drive: E:` and `USB_REMOVED  Drive: E:` as you plug in and remove a drive.

### Running the tests

```bash
python -m unittest discover tests -v
```

## Protocol

Each message is one JSON object followed by `\n`. TCP is a byte stream, so the
newline marks where one message ends. The server replies `ACK\n` to every message.

```json
{"event": "USB_INSERTED", "pc_name": "LAB-PC-07", "ip": "192.168.1.107", "drive": "E:", "timestamp": "2026-10-19 16:24:31"}
```

| Event | Sent when |
|-------|-----------|
| `CLIENT_CONNECTED` | First message after connecting; tells the server who this PC is |
| `USB_INSERTED` / `USB_REMOVED` | A USB storage drive appears or disappears |
| `HEARTBEAT` | Every 10 s, so a dead connection is noticed |
| `TEST_MESSAGE` | `--test` mode only |

Required fields: `event`, `pc_name`, `ip`, `timestamp`. USB events also include `drive`.
The server rejects invalid JSON or a missing field and prints `[INVALID]`, but the connection stays open.

## How USB detection works

Once a second, `usb_monitor.py` asks Windows which drive letters exist
(`GetLogicalDrives`) and keeps the ones that are USB storage:

- `GetDriveTypeW` = *removable*: a pen drive or card. Empty card-reader slots are ignored.
- `GetDriveTypeW` = *fixed*, but the storage bus is USB (`IOCTL_STORAGE_QUERY_PROPERTY`): an external USB HDD or SSD.

It compares each scan with the previous one. A new letter means `USB_INSERTED`; a missing letter means `USB_REMOVED`.
Drives already plugged in when the client starts are reported as well,
with the note *"already connected when monitoring started"*.

**Privacy:** only drive letters and drive type are checked. No file on the USB drive is
opened, listed, read, copied or changed.

## Reconnection

If the server cannot be reached, the client prints
`Server unavailable (...). Retrying in 5s...` and keeps monitoring.
Events detected while it is offline are queued and sent once it reconnects.
A missing heartbeat ACK means the connection is lost, so the client reconnects.

## Wireshark demonstration

1. On the server laptop, start Wireshark on the Wi-Fi/Ethernet interface.
2. Filter: `tcp.port == 5000`
3. Start a client. You will see the 3-way handshake (`SYN`, `SYN-ACK`, `ACK`) and the `CLIENT_CONNECTED` JSON.
4. Plug in a USB drive. A `PSH, ACK` packet carries the JSON event, followed by the server's `ACK\n` reply.
5. Right-click a packet, then **Follow > TCP Stream** to show the readable JSON.
6. Point out the source and destination IP, the source port (random ephemeral port) and destination port (5000).
7. Every 10 s a small `HEARTBEAT` packet appears.

Note: Wireshark cannot capture traffic when the client and server are on the *same* laptop
(127.0.0.1) unless Npcap's loopback adapter is chosen, so use two laptops.

## Auto-start on Windows (do this last, only once everything works)

1. Press `Win + R`, type `shell:startup`, press Enter.
2. In that folder create `usb_client.bat` containing:
   ```
   cd /d C:\path\to\USB_Monitoring_System
   python client\client.py --server 192.168.1.100
   ```

## Lab deployment

Only with permission from the lab faculty or administrator. Run the server on the invigilator PC
and the client on each lab PC, with `SERVER_IP` set in `client/config.py`.
If the lab network blocks TCP port 5000, ask the administrator to allow it, or pick another
allowed port in **both** config files. Do not try to get around network restrictions.
