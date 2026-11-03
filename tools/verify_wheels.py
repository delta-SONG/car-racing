"""Offscreen-only wheel geometry and screenshot checks; never opens a game window."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from panda3d.core import (AmbientLight, DirectionalLight, GeomVertexReader)
from direct.gui.OnscreenText import OnscreenText
from classic3d_model import VEHICLES
from game3d import Game3D, options


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    output = parser.parse_args().output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    app = Game3D(options(["--mode", "escort", "--smoke", "3600"]))
    app.taskMgr.remove("highway-tick")
    app.hud.hide()
    app.panel.hide()
    for child in app.render.getChildren():
        if child != app.camera:
            child.hide()
    app.render.clearFog()
    app.render.clearLight()
    ambient = AmbientLight("wheel-review-ambient")
    ambient.setColor((0.65, 0.68, 0.72, 1))
    app.render.setLight(app.render.attachNewNode(ambient))
    sun = DirectionalLight("wheel-review-sun")
    sun.setColor((0.8, 0.76, 0.7, 1))
    sun_node = app.render.attachNewNode(sun)
    sun_node.setHpr(-30, -40, 0)
    app.render.setLight(sun_node)
    app.setBackgroundColor(0.12, 0.17, 0.21, 1)
    app.camLens.setFov(48)
    app.camLens.setNearFar(0.01, 200)
    floor = app.cube(app.render, pos=(0, 0, -0.045), scale=(14, 14, 0.04),
                     color=(0.24, 0.31, 0.34, 1))
    title = OnscreenText("", pos=(0, 0.88), scale=0.055, font=app.font,
                         fg=(1, 0.78, 0.4, 1), mayChange=True)
    subtitle = OnscreenText("离屏渲染检查 · 不占用桌面窗口", pos=(0, -0.90),
                            scale=0.033, font=app.font, fg=(0.85, 0.9, 0.92, 1))
    car = app.car(VEHICLES[0], "wheel-review-car")
    car.reparentTo(app.render)
    checks = {}
    try:
        geometry = car.getPythonTag("wheels")[0].node().getGeom(0)
        data = geometry.getVertexData()
        vertices, normals = GeomVertexReader(data, "vertex"), GeomVertexReader(data, "normal")
        points, directions = [], []
        while not vertices.isAtEnd():
            points.append(vertices.getData3())
            directions.append(normals.getData3())
        primitive = geometry.getPrimitive(0).decompose()
        valid_faces = []
        for index in range(primitive.getNumPrimitives()):
            start = primitive.getPrimitiveStart(index)
            a, b, c = [primitive.getVertex(start + j) for j in range(3)]
            face = (points[b] - points[a]).cross(points[c] - points[a])
            expected = directions[a] + directions[b] + directions[c]
            valid_faces.append(face.dot(expected) > 1e-9)
        checks["closed_cylinder_faces_have_outward_winding"] = all(valid_faces)
        checks["four_wheels_on_player_model"] = len(car.getPythonTag("wheels")) == 4

        def capture(name, caption, position, target):
            title.setText(caption)
            app.camera.setPos(*position)
            app.camera.lookAt(*target)
            for _ in range(3):
                app.graphicsEngine.renderFrame()
            app.capture(output / (name + ".png"))

        capture("wheel-side", "圆柱体车轮 · 侧视检查", (7.2, 0, 1.6), (0, 0, 0.55))
        capture("wheel-perspective", "圆柱体车轮 · 斜视检查", (6.7, -8.5, 4.0), (0, 0, 0.5))
        car.hide()
        wheel = app.wheel(app.render, (0, 0, 0))
        floor.setZ(-0.35)
        capture("wheel-detail", "圆柱轮胎 + 圆形轮毂 · 模型细节", (1.2, -0.85, 0.55), (0, 0, 0))
        wheel.removeNode()
        floor.setZ(-0.045)
        cars = []
        for index, vehicle in enumerate(VEHICLES):
            model = app.car(vehicle, "wheel-review-" + vehicle["shape"])
            model.reparentTo(app.render)
            model.setPos((index % 3 - 1) * 5, (index // 3) * 8 - 4, 0)
            cars.append(model)
        checks["all_six_models_use_four_wheels"] = all(len(model.getPythonTag("wheels")) == 4 for model in cars)
        capture("all-vehicles", "六款车型 · 统一圆柱车轮", (15, -23, 22), (0, 0, 0))
        result = dict(offscreen=True, native_window=False, no_save=True, human_playtest=False,
                      triangles_per_wheel=primitive.getNumPrimitives(), checks=checks,
                      passed=all(checks.values()))
        (output / "wheel-visual-validation.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=True))
        return 0 if result["passed"] else 1
    finally:
        app.destroy()


if __name__ == "__main__":
    raise SystemExit(main())
