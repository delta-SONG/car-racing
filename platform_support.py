"""Platform-specific save locations and fonts; never depend on working directory."""
import os
from pathlib import Path
import sys


def disable_game_ime():
    """Disable IME only in this game's window thread, before creating it."""
    if sys.platform != 'win32':
        return None
    try:
        import ctypes
        from ctypes import wintypes
        current = ctypes.windll.kernel32.GetCurrentThreadId
        current.restype = wintypes.DWORD
        disable = ctypes.windll.imm32.ImmDisableIME
        disable.argtypes = (wintypes.DWORD,)
        disable.restype = wintypes.BOOL
        return bool(disable(current()))
    except (AttributeError, OSError):
        return False


def monitor_rectangle(window, fallback):
    """Current monitor in desktop coordinates, without changing display mode."""
    if sys.platform != 'win32':
        return fallback
    try:
        import ctypes
        from ctypes import wintypes
        class MonitorInfo(ctypes.Structure):
            _fields_ = [('cbSize', wintypes.DWORD), ('rcMonitor', wintypes.RECT),
                        ('rcWork', wintypes.RECT), ('dwFlags', wintypes.DWORD)]
        user = ctypes.windll.user32
        find = user.MonitorFromWindow
        find.argtypes = (wintypes.HWND, wintypes.DWORD)
        find.restype = wintypes.HANDLE
        info = user.GetMonitorInfoW
        info.argtypes = (wintypes.HANDLE, ctypes.POINTER(MonitorInfo))
        info.restype = wintypes.BOOL
        hwnd = window.getWindowHandle().getIntHandle()
        monitor = find(hwnd, 2)  # MONITOR_DEFAULTTONEAREST
        rect = MonitorInfo()
        rect.cbSize = ctypes.sizeof(rect)
        if monitor and info(monitor, ctypes.byref(rect)):
            r = rect.rcMonitor
            return (r.left, r.top, r.right - r.left, r.bottom - r.top)
    except (AttributeError, OSError, TypeError, ValueError):
        pass
    return fallback


def save_directory(platform=None, home=None, environ=None):
    platform = sys.platform if platform is None else platform
    home = Path.home() if home is None else Path(home)
    environ = os.environ if environ is None else environ
    if platform == 'darwin':
        return home / 'Library' / 'Application Support' / 'SpeedHighway'
    if platform == 'win32':
        return Path(environ.get('LOCALAPPDATA', str(home))) / 'SpeedHighway'
    return Path(environ.get('XDG_DATA_HOME', str(home / '.local' / 'share'))) / 'SpeedHighway'


def chinese_font(platform=None, root=None):
    platform = sys.platform if platform is None else platform
    root = Path(__file__).resolve().parent if root is None else Path(root)
    bundled = root / 'assets' / 'NotoSansCJKsc-Regular.otf'
    windows = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / 'msyh.ttc'
    candidates = [windows, bundled] if platform == 'win32' else [bundled]
    if platform == 'darwin':
        candidates.extend([Path('/System/Library/Fonts/PingFang.ttc'),
                           Path('/System/Library/Fonts/STHeiti Light.ttc')])
    return next((str(path) for path in candidates if path.is_file()), None)

