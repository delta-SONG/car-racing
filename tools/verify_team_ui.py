"""Render team feedback in offscreen buffers only; never controls desktop input."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from panda3d.core import GraphicsBuffer
from game3d import Game3D, options
from highway_ui import MUTED


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    output = parser.parse_args().output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    app = Game3D(options(['--mode', 'escort', '--smoke', '3600']))
    app.taskMgr.remove('highway-tick')
    checks, captures, bounds = {}, [], {}
    badge = app.label('离屏检查 · 合成路况 · 非真人试玩', (0, 0.965), 0.025,
                      parent=app.aspect2d, color=MUTED)
    try:
        for width, height in ((1280, 720), (960, 720), (960, 540)):
            assert app.openMainWindow(type='offscreen', size=(width, height), keepCamera=True)
            assert isinstance(app.win, GraphicsBuffer), 'Visible windows are forbidden in this tool'
            app.setAspectRatio(width / height)
            app.layout_ui()
            size = f'{width}x{height}'
            checks['buffer-size-' + size] = app.win.getXSize() == width and app.win.getYSize() == height

            def capture(name):
                app.hud_update()
                app.scene(0)
                for _ in range(3):
                    app.graphicsEngine.renderFrame()
                path = output / (name + '.png')
                app.capture(path)
                captures.append(path.name)

            app.action('menu')
            capture('menu-' + size)
            if width == 1280:
                app.capture(output / 'menu.png')
            for state, gap, detached in (('healthy', 140, 0), ('warning', 360, 0),
                                         ('detached', 620, 1.25), ('recovered', 180, 0)):
                app.action('start')
                app.model.distance = 2400
                app.model.escort_distance = 2400 - gap
                app.model.detached_seconds = detached
                app.model.message('邻道占用或有来车', hint='S / ↓ 减速等空隙，再按 H', kind='warning')
                capture('team-' + state + '-' + size)
                if state == 'healthy' and width == 1280:
                    app.capture(output / 'escort.png')
                if state == 'warning' and width == 960 and height == 540:
                    app.capture(output / 'request-blocked-960x540.png')
                local_bounds = {}
                for name in ('team_status', 'team_gap_value', 'team_hint'):
                    lower, upper = getattr(app, name).getTightBounds(app.team_card)
                    local_bounds[name] = [list(lower), list(upper)]
                    checks[f'text-contained-{state}-{size}-{name}'] = (
                        lower.x >= -0.34 and upper.x <= 0.34 and
                        lower.z >= -0.20 and upper.z <= 0.20)
                checks[f'countdown-nonnegative-{state}-{size}'] = '-' not in app.team_status.getText()
                checks[f'collision-guidance-independent-{state}-{size}'] = (
                    app.feedback.getText() == '邻道占用或有来车' and '再按 H' in app.feedback_hint.getText())
                bounds[state + '-' + size] = local_bounds
            app.pause()
            capture('pause-' + size)
            app.state = 'over'
            app.model.reason = '队伍脱节：持续加速甩开了护送车'
            app.refresh()
            capture('result-fixture-' + size)
            app.action('menu')
            app.switch_mode()
            app.action('start')
            capture('classic-' + size)
            checks['classic-hides-team-' + size] = app.team_card.isHidden()
            app.action('menu')
            app.switch_mode()
        root = Path(__file__).resolve().parents[1]
        source_hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                         for name in ('highway_ui.py', 'escort_model.py', 'game3d.py', 'scene3d.py')}
        result = dict(offscreen=True, native_window=False, human_playtest=False,
                      synthetic_fixtures=True, no_save=True, failure=None,
                      checks=checks, captures=captures, text_bounds=bounds,
                      source_sha256=source_hashes, passed=all(checks.values()))
        (output / 'visual-validation.json').write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(dict(passed=result['passed'], checks=len(checks),
                              captures=len(captures), failed=[k for k,v in checks.items() if not v])))
        return 0 if result['passed'] else 1
    finally:
        app.destroy()


if __name__ == '__main__':
    raise SystemExit(main())
