"""Build a native .app and a verified compressed DMG on macOS."""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run(*args, **kwargs):
    subprocess.run([str(arg) for arg in args], check=True, cwd=ROOT, **kwargs)


def main():
    if sys.platform != 'darwin':
        raise SystemExit('DMG must be built on macOS. Use build_macos.command on a Mac or the GitHub Actions workflow.')
    if sys.version_info[:2] != (3, 11):
        raise SystemExit('Please use Python 3.11 to build this project.')
    arch = platform.machine()
    if arch not in ('arm64', 'x86_64'):
        raise SystemExit(f'Unsupported architecture: {arch}')
    for tool in ('hdiutil', 'codesign', 'ditto'):
        if not shutil.which(tool):
            raise SystemExit(f'Missing macOS tool: {tool}')
    if not (ROOT / 'assets' / 'NotoSansCJKsc-Regular.otf').is_file():
        raise SystemExit('Missing bundled Chinese font: assets/NotoSansCJKsc-Regular.otf')
    # Rocket plug-ins are unused.  The bundled Cg runtime is Intel-only, but the
    # Intel Panda3D core still links it, so remove it only from arm64 builds.
    import panda3d
    legacy_patterns = ('rocket*.so', 'libRocket*.dylib')
    if arch == 'arm64':
        legacy_patterns += ('libCg.dylib',)
    for pattern in legacy_patterns:
        for legacy in Path(panda3d.__file__).resolve().parent.glob(pattern):
            legacy.unlink()
    work = ROOT / 'build' / 'macos' / arch
    output = ROOT / 'dist' / 'macos' / arch
    work.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    run(sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir', '--collect-all', 'panda3d',
        '--windowed', '--name', 'SpeedHighway', '--target-arch', arch,
        '--osx-bundle-identifier', 'local.speedhighway.game',
        '--add-data', f'{ROOT / "assets"}:assets',
        '--distpath', output, '--workpath', work / 'pyinstaller', '--specpath', work,
        ROOT / 'game3d.py')
    app = output / 'SpeedHighway.app'
    run('codesign', '--verify', '--deep', '--strict', app)
    # Verify the actual frozen executable, not just the source interpreter.
    report = output / 'smoke-report.json'
    run(app / 'Contents' / 'MacOS' / 'SpeedHighway', '--smoke', '10',
        '--report', report, '--screenshot', output / 'gameplay.png', timeout=60)
    stats = json.loads(report.read_text(encoding='utf-8'))
    if stats['seconds'] < 10 or stats['frames'] < 120:
        raise RuntimeError(f'Frozen application smoke test failed: {stats}')
    dmg = output / f'SpeedHighway-macOS-{arch}.dmg'
    with tempfile.TemporaryDirectory(prefix='dmg-stage-', dir=work) as temporary:
        stage = Path(temporary)
        run('ditto', app, stage / app.name)
        (stage / 'Applications').symlink_to('/Applications', target_is_directory=True)
        shutil.copy2(ROOT / 'macos' / '使用说明.txt', stage / '使用说明.txt')
        shutil.copy2(ROOT / 'assets' / 'OFL.txt', stage / '字体许可.txt')
        run('hdiutil', 'create', '-volname', 'Speed Highway', '-srcfolder', stage,
            '-fs', 'HFS+', '-format', 'UDZO', '-ov', dmg)
    run('hdiutil', 'verify', dmg)
    # Mount the image read-only and verify its actual app payload.
    with tempfile.TemporaryDirectory(prefix='dmg-mount-', dir=work) as temporary:
        mount = Path(temporary)
        run('hdiutil', 'attach', '-readonly', '-nobrowse', '-mountpoint', mount, dmg)
        try:
            run('codesign', '--verify', '--deep', '--strict', mount / app.name)
            if not (mount / 'Applications').is_symlink():
                raise RuntimeError('DMG is missing the Applications shortcut')
        finally:
            run('hdiutil', 'detach', mount)
    digest = hashlib.sha256(dmg.read_bytes()).hexdigest()
    (output / f'{dmg.name}.sha256').write_text(f'{digest}  {dmg.name}\n', encoding='utf-8')
    (output / 'build-report.json').write_text(json.dumps({
        'platform': platform.platform(), 'architecture': arch,
        'dmg': dmg.name, 'sha256': digest, 'bytes': dmg.stat().st_size,
        'smoke': stats, 'signing': 'ad-hoc, not Apple-notarized',
        'display_driver': os.environ.get('SDL_VIDEODRIVER', 'native'),
    }, indent=2), encoding='utf-8')
    print(f'Built and verified: {dmg}')


if __name__ == '__main__':
    main()





