"""Fetch the pinned OFL font for building; the finished game stays offline."""
import hashlib
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
FONT_SHA256 = '2c76254f6fc379fddfce0a7e84fb5385bb135d3e399294f6eeb6680d0365b74b'
FONT_URL = ('https://raw.githubusercontent.com/notofonts/noto-cjk/'
            '165c01b46ea533872e002e0785ff17e44f6d97d8/'
            'Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf')


def main():
    destination = ROOT / 'assets' / 'NotoSansCJKsc-Regular.otf'
    if destination.is_file() and hashlib.sha256(destination.read_bytes()).hexdigest() == FONT_SHA256:
        print('Bundled Chinese font checksum verified.')
        return
    with urllib.request.urlopen(FONT_URL, timeout=120) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != FONT_SHA256:
        raise RuntimeError('Font checksum mismatch; refusing to bundle an unexpected file.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    print('Downloaded and verified Noto Sans CJK SC Regular.')


if __name__ == '__main__':
    main()
