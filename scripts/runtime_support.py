"""Windows process primitives used by the non-admin startup workers."""
import ctypes
from ctypes import wintypes
import socket
import subprocess

CREATE_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)

def single_instance(name):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateMutexW.restype = wintypes.HANDLE
    handle = kernel.CreateMutexW(None, False, 'Local\\' + name)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error() == 183:
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle(handle)
        return None
    return handle  # Keep the handle alive for this process lifetime.

def port_open(port):
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=2):
            return True
    except OSError:
        return False

def stop_child(process):
    if process is not None and process.poll() is None:
        # Only the still-live process handle created by this worker is eligible.
        subprocess.run(['taskkill.exe', '/PID', str(process.pid), '/T', '/F'],
                       capture_output=True, creationflags=CREATE_NO_WINDOW, timeout=20)
        try: process.wait(timeout=10)
        except subprocess.TimeoutExpired: process.kill()
