"""Reproduce rear-traffic culling in offscreen buffers, without desktop input."""

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from panda3d.core import GraphicsBuffer, Point2, Point3
from classic3d_model import VEHICLES
from game3d import Game3D, options
from highway_ui import MUTED


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--baseline', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise RuntimeError('Use an empty report directory')
    app = Game3D(options(['--mode', 'escort', '--smoke', '3600']))
    app.taskMgr.remove('highway-tick')
    app.label('离屏检查 · 合成后方路况 · 非真人试玩', (0, 0.965), 0.025,
              parent=app.aspect2d, color=MUTED)
    checks, captures, fixtures = {}, [], []
    try:
        for width, height in ((1280, 720), (960, 720), (960, 540)):
            assert app.openMainWindow(type='offscreen', size=(width, height), keepCamera=True)
            assert isinstance(app.win, GraphicsBuffer), 'Visible windows are forbidden'
            app.setAspectRatio(width / height)
            app.layout_ui()
            size = f'{width}x{height}'
            for gap in (140, 360, 540, 620):
                app.action('start')
                model = app.model
                model.distance = 2400
                model.escort_distance = model.distance - gap
                model.x, model.escort_x = 0.66, -0.66
                model.detached_seconds = 1.25 if gap > model.max_gap else 0
                # A slow car 90 ticks ahead of the escort affects its braking.
                hazard = model.make_car(model.escort_distance + 90, -0.66,
                                        speed=60, vehicle=VEHICLES[3])
                rear = model.make_car(model.escort_distance - 140, 0.66,
                                      speed=160, vehicle=VEHICLES[0])
                front = model.make_car(model.distance + 180, 0.66,
                                       speed=110, vehicle=VEHICLES[4])
                model.cars = [hazard, rear, front]
                # make_car seeds z for a new mission at distance zero. These
                # later-route fixtures must refresh its relative coordinate.
                for car in model.cars:
                    car['z'] = car['distance'] - model.distance
                before = copy.deepcopy(model.__dict__)
                app.hud_update()
                app.scene(0)
                for _ in range(3):
                    app.graphicsEngine.renderFrame()
                name = f'rear-gap-{gap}-{size}'
                app.capture(output / (name + '.png'))
                captures.append(name + '.png')
                visible = {}
                projections = {}
                for role, car in (('hazard', hazard), ('rear', rear), ('front', front)):
                    visible[role] = id(car) in app.traffic
                    checks[f'{name}-{role}-rendered'] = visible[role]
                    point = Point2()
                    position = Point3(*app.pose(car['distance'], car['x']))
                    position.z = 0.8
                    projected = app.camLens.project(app.cam.getRelativePoint(app.render, position), point)
                    projections[role] = [float(point.x), float(point.y)] if projected else None
                    checks[f'{name}-{role}-inside-frustum'] = bool(
                        projected and abs(point.x) < 0.95 and abs(point.y) < 0.95)
                    if role == 'hazard':
                        checks[name + '-hazard-clear-of-hud'] = bool(
                            projected and abs(point.x) < 0.95 and -0.53 < point.y < 0.64)
                checks[name + '-model-unchanged'] = all(
                    model.__dict__[key] == value for key, value in before.items() if key != 'rng')
                fixtures.append(dict(size=size, gap=gap, hazard_z=hazard['z'],
                                     rendered=visible, projection=projections))
        root = Path(__file__).resolve().parents[1]
        result = dict(offscreen=True, native_window=False, human_playtest=False,
                      synthetic_fixtures=True, no_save=True, baseline=args.baseline,
                      checks=checks, captures=captures, fixtures=fixtures,
                      source_sha256={name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                                     for name in ('scene3d.py', 'game3d.py', 'escort_model.py', 'highway_ui.py')},
                      passed=all(checks.values()))
        (output / 'rear-traffic-validation.json').write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(dict(passed=result['passed'], checks=len(checks), captures=len(captures),
                              baseline=args.baseline, failed=[key for key, value in checks.items() if not value])))
        return 0 if args.baseline or result['passed'] else 1
    finally:
        app.destroy()


if __name__ == '__main__':
    raise SystemExit(main())
