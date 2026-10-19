# How To Run

Everything runs by **double-clicking `.bat` files**. You do not need to type commands
or IP addresses: clients find the server automatically on the network.

- **Laptop 1** = Server (invigilator)
- **Laptop 2, 3, ...** = Clients (exam PCs)

| File | Double-click it on | What it does |
|------|--------------------|--------------|
| `setup.bat` | every laptop, once | Checks Python, prepares logs, runs self-test, adds firewall rules |
| `start_server.bat` | server laptop | Starts the central monitoring server |
| `start_client.bat` | each client laptop | Starts USB monitoring and connects to the server |
| `test_connection.bat` | a client laptop | Sends one test message to the server |
| `test_usb.bat` | any laptop | Shows USB insert/remove detection, no network needed |
| `allow_firewall.bat` | server laptop | Adds or removes the firewall rules (`--remove`) |
| `autostart_client.bat` | lab PCs, optional | Starts the client automatically at login (`--remove` to undo) |

---

## Step 0: One-time setup (every laptop)

1. **Python 3.8 or newer** must be installed. If it is missing, `setup.bat` opens the
   download page for you. During installation tick **"Add python.exe to PATH"**.
   No `pip install` is needed: the project uses only Python's standard library.
2. Copy the whole `USB_Monitoring_System` folder to every laptop.
3. Double-click **`setup.bat`**. It:
   - checks Python
   - creates `logs\events.csv`
   - runs the self-test, which should say `Self-test passed.`
   - asks *"Add the firewall rules now?"*. Press **Y on the server laptop** and click
     **Yes** on the Windows permission popup. On client laptops you can press N.

---

## Step 1: Same network

- Connect all laptops to the **same** Wi-Fi network, LAN switch, or phone hotspot.
- On every laptop set the network to **Private**:
  *Settings > Network & Internet > Wi-Fi > (your network) > Network profile type > Private*

---

## Step 2: Start the server (Laptop 1)

Double-click **`start_server.bat`**:

```
====================================================
  CENTRAL USB MONITORING SERVER
====================================================

Server IP : 192.168.1.100
Port      : 5000
Discovery : ON (UDP 5001) - clients find this server automatically

Waiting for clients...  (Ctrl+C to stop)
```

If a **Windows Firewall popup** appears, tick **Private networks** and click **Allow access**.

Leave this window open.

---

## Step 3: Check the connection (Laptop 2)

Double-click **`test_connection.bat`**:

```
Found server at 192.168.1.100:5000
Connected to server.
Message sent successfully.
```

The server window shows `Received from ... : Hello from examination PC`.

**Do not continue until this works.** If it fails, see *Troubleshooting*.

---

## Step 4: Start USB monitoring (Laptop 2, 3, ...)

Double-click **`start_client.bat`**:

```
PC name : DESKTOP-ABC123
Server  : automatic discovery
Monitoring USB storage devices... (Ctrl+C to stop)
Found server at 192.168.1.100:5000
Connected to server.
```

The server shows `[CONNECTED] DESKTOP-ABC123 (192.168.1.105)   Connected clients: 1`.

**Optional, custom lab name:** open `client\config.py` in Notepad and set
`PC_NAME = "LAB-PC-01"` (with quotes). Otherwise the Windows computer name is used.

---

## Step 5: Plug in a USB drive

Within about 1 second the server shows:

```
====================================================
                     USB ALERT
====================================================
PC Name    : LAB-PC-01
IP Address : 192.168.1.105   (socket peer: 192.168.1.105)
Event      : USB INSERTED
Drive      : E:
Time       : 16:42:15
Connected clients: 2
====================================================
```

Remove it and the server shows a **USB REMOVED** block.
Every event is saved in `logs\events.csv` on the server laptop. You can open it in Excel.

---

## Step 6: Wireshark demonstration (Laptop 1)

Wireshark is a separate free program. Install it from https://www.wireshark.org/download.html
and choose to install **Npcap** when the installer asks.

1. Open Wireshark and pick the **Wi-Fi** (or Ethernet) interface.
2. Filter: `tcp.port == 5000 || udp.port == 5001`, then press Enter.
3. Start a client. You will see:
   - a **UDP broadcast** to `255.255.255.255:5001` (*"where is the server?"*) and the server's UDP reply
   - the TCP handshake: **SYN, SYN-ACK, ACK**
4. Plug in a USB drive. A TCP packet carrying the JSON event appears, then the server's `ACK`.
5. Right-click a TCP packet, then choose **Follow > TCP Stream** to read the JSON.
6. Point out the source and destination IP, the ports (random client port and 5000), TCP vs UDP.

---

## Stopping

Press **Ctrl+C**, or close the window.

---

## Optional

- **Test USB detection only:** double-click `test_usb.bat`, then plug in and remove a pen drive.
- **Test on ONE laptop:** run `start_server.bat`, then `start_client.bat` on the same laptop.
  Discovery also works locally.
- **Auto-start on lab PCs:** double-click `autostart_client.bat`. To undo, run
  `autostart_client.bat --remove` from Command Prompt.
- **Run the tests manually:** `python -m unittest discover tests -v`
- **Fixed server IP (no discovery):** in `client\config.py` set `SERVER_IP = "192.168.1.100"`.
- **Different port:** change `PORT` in `server\config.py` and `SERVER_PORT` in `client\config.py`.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `setup.bat` says Python not found | Install Python, tick "Add python.exe to PATH", then run `setup.bat` again. |
| `Server unavailable (no server answered the discovery broadcast)` | Server not running, firewall blocking (run `allow_firewall.bat` on the server), or the network blocks broadcasts. Then set the server IP manually (see next row). |
| Discovery never works on college Wi-Fi | Many college networks block broadcasts. On the server run `ipconfig`, note the IPv4 Address, and put it in `client\config.py`: `SERVER_IP = "192.168.x.x"`. |
| `Server unavailable (TimeoutError)` | Firewall is blocking. Run `allow_firewall.bat` on the server and make sure the network is *Private*. |
| `Server unavailable (ConnectionRefusedError)` | Server is not running or was closed. The client keeps retrying by itself. |
| `ping` between laptops times out | The Wi-Fi blocks laptop-to-laptop traffic ("client isolation"). Use a phone hotspot or a LAN switch. |
| `Could not start server on port 5000` | A server window is already open. Close it first. |
| USB drive not detected | Only storage with a drive letter (E:, F: ...) is detected. Phones (MTP), keyboards and mice are not reported. |
| Self-test failed | Read the error shown, or run `python -m unittest discover tests -v` for details. |
