"""Procedural scenery shared by classic and escort modes."""

import math
from panda3d.core import (AmbientLight, CardMaker, DirectionalLight, Fog,
                         Geom, GeomNode, GeomTriangles, GeomVertexData,
                         GeomVertexFormat, GeomVertexWriter, NodePath,
                         TextNode, TransparencyAttrib)
from classic3d_model import VEHICLES


class HighwayScene:
    STEP, COUNT, SCALE = 38.0, 62, 18.0

    def cube(self, parent, pos=(0, 0, 0), scale=(1, 1, 1),
             color=(1, 1, 1, 1), hpr=(0, 0, 0)):
        node = parent.attachNewNode("cube")
        model = self.loader.loadModel("models/box")
        model.reparentTo(node)
        model.setPos(-0.5, -0.5, -0.5)
        node.setPos(*pos)
        node.setScale(*(value * 2 for value in scale))
        node.setColor(*color)
        node.setTextureOff(1)
        node.setHpr(*hpr)
        return node

    def wheel(self, parent, pos):
        """Closed circular tyre and hub, with the axle along local X.

        Bake the three cylinders into one immutable mesh shared by all cars.
        Each wheel keeps its own transform so pitch spins it about its axle.
        """
        if not hasattr(self, "_wheel_geometry"):
            data = GeomVertexData("cylindrical-wheel", GeomVertexFormat.getV3n3c4(), Geom.UHStatic)
            vertex = GeomVertexWriter(data, "vertex")
            normal = GeomVertexWriter(data, "normal")
            colour = GeomVertexWriter(data, "color")
            triangles = GeomTriangles(Geom.UHStatic)
            segments = 32

            def point(x, y, z, nx, ny, nz, color):
                index = vertex.getWriteRow()
                vertex.addData3(x, y, z)
                normal.addData3(nx, ny, nz)
                colour.addData4(*color)
                return index

            # Widths retain the old tyre envelope; the shallow metal hub
            # protrudes from both sidewalls so its circular face is visible.
            for width, radius, color in (
                    (0.34, 0.30, (0.025, 0.03, 0.035, 1)),
                    (0.36, 0.165, (0.55, 0.60, 0.64, 1)),
                    (0.385, 0.065, (0.12, 0.16, 0.19, 1))):
                side = vertex.getWriteRow()
                for index in range(segments + 1):
                    angle = 2 * math.pi * index / segments
                    c, s = math.cos(angle), math.sin(angle)
                    for x in (-width / 2, width / 2):
                        point(x, radius * c, radius * s, 0, c, s, color)
                for index in range(segments):
                    left, right = side + index * 2, side + index * 2 + 1
                    triangles.addVertices(left, left + 2, right)
                    triangles.addVertices(right, left + 2, right + 2)
                for sign in (-1, 1):
                    x = sign * width / 2
                    center = point(x, 0, 0, sign, 0, 0, color)
                    ring = vertex.getWriteRow()
                    for index in range(segments + 1):
                        angle = 2 * math.pi * index / segments
                        point(x, radius * math.cos(angle), radius * math.sin(angle),
                              sign, 0, 0, color)
                    for index in range(segments):
                        a, b = ring + index, ring + index + 1
                        triangles.addVertices(center, a if sign > 0 else b,
                                              b if sign > 0 else a)
            triangles.closePrimitive()
            self._wheel_geometry = Geom(data)
            self._wheel_geometry.addPrimitive(triangles)
        mesh = GeomNode("cylindrical-wheel")
        mesh.addGeom(self._wheel_geometry)
        wheel = parent.attachNewNode(mesh)
        wheel.setPos(*pos)
        wheel.setTextureOff(1)
        return wheel

    def world(self):
        self.setBackgroundColor(0.31, 0.64, 0.76, 1)
        fog = Fog("fog")
        fog.setColor(0.31, 0.64, 0.76)
        fog.setExpDensity(0.006)
        self.render.setFog(fog)
        ambient = AmbientLight("ambient")
        ambient.setColor((0.55, 0.62, 0.68, 1))
        self.render.setLight(self.render.attachNewNode(ambient))
        sun = DirectionalLight("sun")
        sun.setColor((1, 0.91, 0.72, 1))
        light = self.render.attachNewNode(sun)
        light.setHpr(-35, -55, 0)
        self.render.setLight(light)
        card = CardMaker("grass")
        card.setFrame(-220, 220, -80, 320)
        grass = self.render.attachNewNode(card.generate())
        grass.setP(-90)
        grass.setColor(0.22, 0.48, 0.25, 1)
        grass.setTextureOff(1)
        for index in range(18):
            self.cube(self.render, (-120 + index * 14, 185 + index % 3 * 9, 5),
                      (12, 12, 5 + index % 4 * 2), (0.18, 0.38, 0.38, 1), (0, 0, 45))
        self.road = []
        for _ in range(self.COUNT):
            section = self.render.attachNewNode("road")
            self.cube(section, scale=(8.7, self.STEP / self.SCALE, 0.12),
                      color=(0.13, 0.16, 0.19, 1))
            for x in (-9, 9):
                self.cube(section, (x, 0, 0.16), (0.22, self.STEP / self.SCALE, 0.05),
                          (0.85, 0.20, 0.13, 1))
            for x in (-2.85, 2.85):
                self.cube(section, (x, 0, 0.15), (0.07, 0.45, 0.025), (0.92, 0.86, 0.61, 1))
            section.flattenStrong()
            self.road.append(section)
        self.props = [self.tree() for _ in range(40)]
        self.player = self.car(VEHICLES[self.vehicle_index], "player")
        self.player.reparentTo(self.render)
        self.escort_car = self.car(VEHICLES[2], "escort")
        self.escort_car.reparentTo(self.render)
        self.escort_tag = self.world_label(self.escort_car, "护送车", (0.4, 1, 0.87, 1))
        self.player_tag = self.world_label(self.player, "你 · 领航车", (1, 0.85, 0.35, 1))
        self.traffic = {}
        self.camera.setPos(0, -16.5, 7.3)
        self.camera.lookAt(0, 12, 0.2)

    def tree(self):
        node = self.render.attachNewNode("tree")
        self.cube(node, scale=(0.2, 0.2, 1), pos=(0, 0, 0.8), color=(0.27, 0.16, 0.08, 1))
        self.cube(node, scale=(1.1, 1.1, 2.2), pos=(0, 0, 2.3),
                  color=(0.04, 0.30, 0.18, 1), hpr=(0, 0, 45))
        node.flattenStrong()
        return node

    def car(self, vehicle, name):
        node = NodePath(name)
        color = tuple(value / 255 for value in vehicle["color"]) + (1,)
        accent = tuple(value / 255 for value in vehicle["accent"]) + (1,)
        shape = vehicle["shape"]
        length = dict(racer=2.25, coupe=2.4, suv=2.45, muscle=2.5, hatch=2.15, truck=2.8)[shape]
        self.cube(node, scale=(1.15, length, 0.32), pos=(0, 0, 0.52), color=color)
        self.cube(node, scale=(0.76, length * 0.42, 0.30 if shape in ("suv", "truck") else 0.24),
                  pos=(0, -0.06, 0.88), color=(0.05, 0.12, 0.16, 1))
        self.cube(node, scale=(0.18, 0.18, 0.06), pos=(0, -length * 0.75, 0.65), color=accent)
        if shape == "truck":
            self.cube(node, scale=(1.05, 0.78, 0.32), pos=(0, 0.76, 0.84), color=color)
        if shape == "muscle":
            self.cube(node, scale=(0.45, 0.5, 0.10), pos=(0, -0.45, 1.18), color=accent)
        wheels = []
        for x in (-1.18, 1.18):
            for y in (-length * 0.58, length * 0.58):
                wheels.append(self.wheel(node, (x, y, 0.35)))
        shadow = self.cube(node, scale=(1.35, length * 0.9, 0.015), pos=(0, 0, 0.04),
                           color=(0.02, 0.03, 0.025, 0.42))
        shadow.setTransparency(TransparencyAttrib.MAlpha)
        node.setTransparency(TransparencyAttrib.MAlpha)
        node.setPythonTag("wheels", wheels)
        return node

    def world_label(self, parent, value, color):
        text = TextNode("vehicle-label")
        text.setFont(self.font)
        text.setText(value)
        text.setAlign(TextNode.ACenter)
        text.setTextColor(*color)
        text.setShadow(0.04, 0.04)
        label = parent.attachNewNode(text)
        label.setPos(0, 0, 2.2)
        label.setScale(0.65)
        label.setBillboardPointEye()
        label.setLightOff()
        label.setDepthTest(False)
        label.setDepthWrite(False)
        label.setBin("fixed", 40)
        return label

    def pose(self, distance, lane=0):
        return lane * 8, (distance - self.model.distance) / self.SCALE, 0

    def scene(self, dt):
        base = self.model.distance
        for index, section in enumerate(self.road):
            cycle = self.COUNT * self.STEP
            distance = index * self.STEP + math.floor((base - index * self.STEP) / cycle) * cycle
            rear_sections = 22 if self.mode == "escort" else 2
            if distance < base - self.STEP * rear_sections:
                distance += cycle
            section.setPos(*self.pose(distance))
        for index, prop in enumerate(self.props):
            cycle = len(self.props) // 2 * 110
            origin = (index // 2) * 110 + 80
            distance = origin + math.floor((base - origin) / cycle) * cycle
            if distance < base + (-800 if self.mode == "escort" else 35):
                distance += cycle
            prop.setPos(*self.pose(distance, (-1 if index % 2 else 1) * 1.45))
        x, y, _ = self.pose(base, self.model.x)
        self.player.setPos(x, y, 0.12)
        self.player.setR(-self.model.x * 5)
        self.player.setAlphaScale(0.42 if self.model.invulnerable and int(self.model.invulnerable * 12) % 2 else 1)
        moving_dt = dt if self.state == "playing" else 0
        for wheel in self.player.getPythonTag("wheels"):
            wheel.setP(wheel.getP() + self.model.speed * moving_dt * 4)
        escort = self.mode == "escort"
        self.escort_car.show() if escort else self.escort_car.hide()
        self.player_tag.show() if escort else self.player_tag.hide()
        if escort:
            self.escort_car.setPos(*self.pose(self.model.escort_distance, self.model.escort_x))
            self.escort_car.setZ(0.12)
            self.escort_car.setAlphaScale(0.42 if self.model.escort_invulnerable and int(self.model.escort_invulnerable * 12) % 2 else 1)
            for wheel in self.escort_car.getPythonTag("wheels"):
                wheel.setP(wheel.getP() + self.model.escort_speed * moving_dt * 4)
        live = set()
        # Keep traffic around the follower visible after the leader passes it.
        # A fixed leader-relative cutoff hid cars that still brake/hit the
        # escort when the team gap exceeded 220 road ticks.
        rear_limit = min(-220, -self.model.gap - 220) if escort else -220
        for car in self.model.cars:
            if not (rear_limit < car["z"] < 2300) or (not escort and car["z"] < 0):
                continue
            key = id(car)
            live.add(key)
            if key not in self.traffic:
                node = self.car(car["vehicle"], "traffic")
                node.reparentTo(self.render)
                tag = self.world_label(node, "收到 · 让行", (1, 0.84, 0.28, 1))
                self.traffic[key] = (node, tag)
            node, tag = self.traffic[key]
            node.setPos(*self.pose(base + car["z"], car["x"]))
            node.setZ(0.1)
            responding = car.get("state") in ("responding", "changing")
            requestable = (escort and car.get("state") == "cruising"
                           and 100 <= car["z"] <= self.model.request_range
                           and abs(car["x"] - self.model.x) < 0.3)
            tag.node().setText("收到 · 让行" if responding else "H 请求通行")
            tag.show() if responding or requestable else tag.hide()
            for wheel in node.getPythonTag("wheels"):
                wheel.setP(wheel.getP() + car["speed"] * moving_dt * 4)
        for key in set(self.traffic) - live:
            self.traffic.pop(key)[0].removeNode()
        if escort:
            gap = self.model.gap / self.SCALE
            camera_distance = max(38, gap * 1.8 + 30)
            self.camera.setPos(self.player.getX() * 0.3, -camera_distance, camera_distance * 0.58)
            self.camera.lookAt(self.player.getX() * 0.2, -gap * 0.5, 0.15)
        else:
            self.camera.setPos(self.player.getX() * 0.35, -16.5, 7.3)
            self.camera.lookAt(self.player.getX() * 0.25, 12, 0.15)
