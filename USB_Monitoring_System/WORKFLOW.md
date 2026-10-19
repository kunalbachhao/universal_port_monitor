# Workflow and Test Report

Status key: **Done** = implemented and verified on the development laptop ·
**Pending** = needs physical laptops / a real USB drive / the lab, so the team must run it.

## Phase checklist

| # | Phase | Status | How it was verified |
|---|-------|--------|---------------------|
| 1 | Project setup | Done | Python 3.14.7, folder structure created, no dependencies |
| 2 | Basic TCP server | Done | `server.py` binds `0.0.0.0:5000`, prints its IP and port |
| 3 | Basic TCP client | Done | `client.py --test` prints "Connected to server. / Message sent successfully." |
| 4 | Two-laptop test | **Pending** | Run server on laptop 1 and `client.py --server <IP> --test` on laptop 2 |
| 5 | Multi-client server | Done | One thread per client; 3 clients tested; disconnecting one leaves the others connected |
| 6 | JSON protocol | Done | Newline-delimited JSON; required fields validated; invalid messages rejected |
| 7 | Automatic PC info | Done | Hostname, LAN IP and timestamp filled in automatically |
| 8 | USB detection | Done (logic) / **Pending** (real drive) | Insert/remove logic unit-tested; the Windows API query runs without error. Plug in a real pen drive to confirm |
| 9 | USB + TCP integration | Done | Event delivered to the server and ACKed (integration test) |
| 10 | Server alerts | Done | "USB ALERT" / "USB REMOVED" blocks show PC, IP, event, drive, time |
| 11 | Event logging | Done | `logs/events.csv` appended, header written once |
| 12 | Client reconnection | Done | Client prints "Server unavailable... Retrying", queues events, delivers them after reconnecting |
| 13 | Wireshark | **Pending** | See README, "Wireshark demonstration" |
| 14 | Multi-laptop testing | **Pending** | Test cases T1–T7 below on real laptops |
| 15 | Documentation | Done | README.md, this file |
| 16 | Lab deployment prep | Done (scripts) / **Pending** (lab) | `.bat` launchers, firewall and auto-start scripts; still needs lab permission |
| + | Automatic server discovery | Done | UDP broadcast on port 5001; client found the server via its LAN IP in a live run |

## Automated tests

`python -m unittest discover tests -v` gives **19 tests, all passing** (2026-10-19, Windows 11, Python 3.14.7).
`setup.bat` runs the same tests.

| File | What is tested |
|------|----------------|
| `test_server.py` | 3 clients connect; USB alert + CSV row; log appends; one client disconnecting does not stop the server; events from 2 clients; invalid JSON / missing fields rejected |
| `test_client.py` | JSON round trip; required fields; unknown event rejected; automatic PC info; test message; server down; reconnection with queued event; auto-discovery finds server / no server |
| `test_usb_detection.py` | Insert/remove detection; several drives at once; real Windows drive query |

### Live run on one laptop (localhost, separate processes)

```
[CONNECTED] LAB-PC-01 (127.0.0.1)   Connected clients: 1
Received from LAB-PC-01 (127.0.0.1): Hello from examination PC
[DISCONNECTED] LAB-PC-01   Connected clients: 0
[CONNECTED] LAB-PC-02 (127.0.0.1)   Connected clients: 1
[CONNECTED] LAB-PC-03 (127.0.0.1)   Connected clients: 2
[DISCONNECTED] LAB-PC-03   Connected clients: 1
```

After the server was stopped, client LAB-PC-02 printed:

```
Connection to server lost.
Server unavailable (ConnectionRefusedError). Retrying in 5s...
```

## Manual test cases (fill in on real laptops)

| ID | Test | Expected | Result |
|----|------|----------|--------|
| T1 | Client connects | Server: `[CONNECTED] <PC>` | |
| T2 | USB inserted on client 1 | Server: USB ALERT, `USB INSERTED`, client 1's name/IP, drive letter | |
| T3 | USB removed from client 1 | Server: USB REMOVED, client 1 | |
| T4 | USB inserted on client 2 | Server: USB ALERT, client 2 | |
| T5 | Both clients generate events | Both alerts shown and logged correctly | |
| T6 | Close one client (Ctrl+C) | `[DISCONNECTED]`; the other client still sends events | |
| T7 | Stop server, plug in USB, restart server | Client retries; queued event appears after restart | |
| T8 | Wireshark `tcp.port == 5000` | Handshake, JSON payload, correct IPs and ports visible | |
| T9 | External USB HDD/SSD | Detected like a pen drive | |

## Known limitations

- Windows only. On other systems the client runs but never detects any USB drive.
- Detection checks once a second, so a drive plugged in and pulled out within a second can be missed.
- Phones in MTP mode and USB devices without a drive letter (keyboards, mice) are not reported. Only storage that gets a drive letter is detected.
- If the connection breaks right after the server receives an event but before the client gets the ACK, the event can be sent twice.
- No authentication or encryption, as the scope says. Use it only on a trusted lab LAN.
