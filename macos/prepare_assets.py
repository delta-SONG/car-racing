"""Fetch the pinned OFL font for building; the finished game stays offline."""
import hashlib
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
FONT_SHA256 = 'a3041811a78c361b1de50f953c805e0244951c21c5bd412f7232ef0d899af0da'
FONT_URL = ('https://raw.githubusercontent.com/google/fonts/'
            '2894aab31764f10f29c421bdfd2340d3b382d384/'
            'ofl/notosanssc/NotoSansSC%5Bwght%5D.ttf')


def main():
    destination = ROOT / 'assets' / 'NotoSansSC.ttf'
    if destination.is_file() and hashlib.sha256(destination.read_bytes()).hexdigest() == FONT_SHA256:
        print('Bundled Chinese font checksum verified.')
        return
    with urllib.request.urlopen(FONT_URL, timeout=120) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != FONT_SHA256:
        raise RuntimeError('Font checksum mismatch; refusing to bundle an unexpected file.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    print('Downloaded and verified Noto Sans SC.')


if __name__ == '__main__':
    main()
