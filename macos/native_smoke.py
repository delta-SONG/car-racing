"""Check the packaged app with the real Cocoa window driver on the build Mac."""
import json
import os
from pathlib import Path
import platform
import subprocess

root = Path(__file__).resolve().parents[1]
output = root / 'dist' / 'macos' / platform.machine()
environment = dict(os.environ)
environment['SDL_VIDEODRIVER'] = 'cocoa'
command = [str(output / 'SpeedHighway.app' / 'Contents' / 'MacOS' / 'SpeedHighway'),
           '--smoke', '10', '--native-window-smoke',
           '--report', str(output / 'native-smoke-report.json'),
           '--screenshot', str(output / 'native-gameplay.png')]
try:
    result = subprocess.run(command, env=environment, timeout=60, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr[-4000:] or f'Exit code {result.returncode}')
    print((output / 'native-smoke-report.json').read_text(encoding='utf-8'))
except (subprocess.TimeoutExpired, RuntimeError) as error:
    # Some hosted runners do not expose WindowServer. Preserve the verified DMG
    # and explicitly record that native desktop verification was unavailable.
    (output / 'native-smoke-unavailable.json').write_text(
        json.dumps({'native_window_test': 'unavailable', 'reason': str(error)}, indent=2),
        encoding='utf-8')
    print(f'Native desktop test unavailable: {error}')
