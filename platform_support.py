"""Platform-specific save locations and fonts; never depend on working directory."""
import os
from pathlib import Path
import sys


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
