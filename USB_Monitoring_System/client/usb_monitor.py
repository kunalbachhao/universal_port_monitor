"""
Windows USB storage detection - standard library only (ctypes).

Approach: every second, ask Windows which drive letters exist and keep the
ones that are USB storage. Compare with the previous check:
    new letter      -> USB_INSERTED
    missing letter  -> USB_REMOVED

PRIVACY: this module only looks at drive letters and drive *type*.
It never opens, lists, reads, copies or changes any file on the drive.

Run on its own to test detection:   python client\\usb_monitor.py
"""

import ctypes
import string
import sys
import time

DRIVE_REMOVABLE = 2          # GetDriveTypeW result for pen drives / card readers
DRIVE_FIXED = 3              # some USB hard disks / SSDs report as "fixed"
BUS_TYPE_USB = 7             # STORAGE_BUS_TYPE value for USB
IOCTL_STORAGE_QUERY_PROPERTY = 0x002D1400
FILE_SHARE_READ_WRITE = 0x1 | 0x2
OPEN_EXISTING = 3
SEM_FAILCRITICALERRORS = 0x0001   # no "Insert a disk" pop-ups for empty card readers

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                     ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                                     wintypes.HANDLE]
    kernel32.DeviceIoControl.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p,
                                         wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                                         ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
    kernel32.SetErrorMode(SEM_FAILCRITICALERRORS)
    INVALID_HANDLE = wintypes.HANDLE(-1).value


def _bus_type(letter):
    """
    Ask the storage driver which bus the drive is on (USB, SATA, NVMe...).
    Opens the *device* with zero access rights - no file is read.
    Returns None if Windows does not answer.
    """
    handle = kernel32.CreateFileW(f"\\\\.\\{letter}:", 0, FILE_SHARE_READ_WRITE,
                                  None, OPEN_EXISTING, 0, None)
    if handle in (None, INVALID_HANDLE):
        return None
    try:
        query = (ctypes.c_ubyte * 12)()        # STORAGE_PROPERTY_QUERY, all zeros = device property
        out = (ctypes.c_ubyte * 1024)()        # STORAGE_DEVICE_DESCRIPTOR
        returned = wintypes.DWORD(0)
        ok = kernel32.DeviceIoControl(handle, IOCTL_STORAGE_QUERY_PROPERTY,
                                      query, ctypes.sizeof(query), out, ctypes.sizeof(out),
                                      ctypes.byref(returned), None)
        if not ok or returned.value < 32:
            return None
        return int.from_bytes(bytes(out[28:32]), "little")   # BusType field
    finally:
        kernel32.CloseHandle(handle)


def _has_media(letter):
    """False for an empty card-reader slot (drive letter exists but no disk)."""
    return bool(kernel32.GetVolumeInformationW(f"{letter}:\\", None, 0, None, None, None, None, 0))


def is_usb_storage(letter):
    drive_type = kernel32.GetDriveTypeW(f"{letter}:\\")
    if drive_type == DRIVE_REMOVABLE:
        return _has_media(letter)
    if drive_type == DRIVE_FIXED:
        return _bus_type(letter) == BUS_TYPE_USB     # external USB HDD/SSD
    return False


def get_usb_drives():
    """Return the set of drive letters that are USB storage, e.g. {"E:", "F:"}."""
    if not IS_WINDOWS:
        return set()
    bitmask = kernel32.GetLogicalDrives()   # bit 0 = A:, bit 1 = B:, bit 2 = C: ...
    drives = set()
    for i, letter in enumerate(string.ascii_uppercase):
        if bitmask & (1 << i) and is_usb_storage(letter):
            drives.add(f"{letter}:")
    return drives


class UsbMonitor:
    """
    Remembers which USB drives were present last time and reports changes.
    get_drives can be replaced by a fake function in tests.
    """

    def __init__(self, get_drives=get_usb_drives):
        self.get_drives = get_drives
        self.known = set()

    def initial_scan(self):
        """Drives already plugged in when monitoring starts."""
        self.known = set(self.get_drives())
        return sorted(self.known)

    def poll(self):
        """Return a list of ("USB_INSERTED" | "USB_REMOVED", drive) since the last poll."""
        current = set(self.get_drives())
        events = [("USB_INSERTED", d) for d in sorted(current - self.known)]
        events += [("USB_REMOVED", d) for d in sorted(self.known - current)]
        self.known = current
        return events


if __name__ == "__main__":
    if not IS_WINDOWS:
        print("USB detection is only implemented for Windows.")
        sys.exit(1)
    monitor = UsbMonitor()
    print("USB monitor test - insert/remove a pen drive. Ctrl+C to stop.")
    print("USB drives present now:", ", ".join(monitor.initial_scan()) or "none")
    try:
        while True:
            for event, drive in monitor.poll():
                print(f"{time.strftime('%H:%M:%S')}  {event}  Drive: {drive}", flush=True)
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopped.")
