"""USB detection tests. Insert/remove logic is tested with fake drive lists;
the real Windows query is checked to run without errors."""

import sys
import unittest

from helpers import load

usb_monitor = load("client", "usb_monitor")


class FakeDrives:
    def __init__(self, *drives):
        self.drives = set(drives)

    def __call__(self):
        return set(self.drives)


class UsbMonitorLogicTests(unittest.TestCase):
    def test_insert_and_remove(self):
        drives = FakeDrives()
        monitor = usb_monitor.UsbMonitor(drives)
        self.assertEqual(monitor.initial_scan(), [])
        self.assertEqual(monitor.poll(), [])

        drives.drives.add("E:")
        self.assertEqual(monitor.poll(), [("USB_INSERTED", "E:")])
        self.assertEqual(monitor.poll(), [])          # no repeat while it stays plugged in

        drives.drives.discard("E:")
        self.assertEqual(monitor.poll(), [("USB_REMOVED", "E:")])

    def test_two_drives_at_once(self):
        drives = FakeDrives("E:")
        monitor = usb_monitor.UsbMonitor(drives)
        self.assertEqual(monitor.initial_scan(), ["E:"])
        drives.drives = {"F:", "G:"}
        self.assertEqual(monitor.poll(), [("USB_INSERTED", "F:"), ("USB_INSERTED", "G:"),
                                          ("USB_REMOVED", "E:")])


@unittest.skipUnless(sys.platform == "win32", "Windows only")
class RealWindowsQueryTests(unittest.TestCase):
    def test_get_usb_drives_runs(self):
        drives = usb_monitor.get_usb_drives()
        self.assertIsInstance(drives, set)
        for d in drives:
            self.assertRegex(d, r"^[A-Z]:$")
        self.assertNotIn("C:", drives)   # the system disk is never reported as USB
        print(f"\n  USB drives currently detected: {sorted(drives) or 'none'}")


if __name__ == "__main__":
    unittest.main()
