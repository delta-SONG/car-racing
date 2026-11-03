"""Native, resolution-independent interface for Speed Highway."""

import math
from pathlib import Path

from direct.gui.DirectGui import DirectButton, DirectFrame, DirectWaitBar
from direct.gui.OnscreenImage import OnscreenImage
from direct.gui.OnscreenText import OnscreenText
from panda3d.core import (Filename, Geom, GeomNode, GeomTriangles, GeomVertexData,
                         GeomVertexFormat, GeomVertexWriter, NodePath, TextNode,
                         TransparencyAttrib)

from classic3d_model import VEHICLES


INK = (0.035, 0.064, 0.085, 0.98)
CARD = (0.055, 0.098, 0.126, 0.97)
BORDER = (0.18, 0.28, 0.31, 0.75)
WHITE = (0.94, 0.96, 0.93, 1)
MUTED = (0.67, 0.77, 0.79, 1)
MINT = (0.36, 0.91, 0.73, 1)
GOLD = (1, 0.73, 0.30, 1)
RED = (1, 0.43, 0.35, 1)


def rounded(width, height, color, radius=0.035):
    """Draw a rounded XZ card directly as geometry, without raster stretching."""
    radius = min(radius, width, height)
    points = []
    for cx, cz, start in ((width - radius, height - radius, 0),
                          (-width + radius, height - radius, 90),
                          (-width + radius, -height + radius, 180),
                          (width - radius, -height + radius, 270)):
        for index in range(9):
            angle = math.radians(start + index * 90 / 8)
            points.append((cx + radius * math.cos(angle), cz + radius * math.sin(angle)))
    data = GeomVertexData("rounded-card", GeomVertexFormat.getV3c4(), Geom.UHStatic)
    vertex, colours = GeomVertexWriter(data, "vertex"), GeomVertexWriter(data, "color")
    vertex.addData3(0, 0, 0)
    colours.addData4(*color)
    for x, z in points:
        vertex.addData3(x, 0, z)
        colours.addData4(*color)
    triangles = GeomTriangles(Geom.UHStatic)
    for index in range(len(points)):
        triangles.addVertices(0, index + 1, (index + 1) % len(points) + 1)
    triangles.closePrimitive()
    geometry = Geom(data)
    geometry.addPrimitive(triangles)
    node = GeomNode("rounded-card")
    node.addGeom(geometry)
    result = NodePath(node)
    result.setTransparency(TransparencyAttrib.MAlpha)
    result.setTwoSided(True)
    result.setLightOff()
    result.setDepthTest(False)
    result.setDepthWrite(False)
    return result


class HighwayUI:
    def label(self, text, pos, scale=0.05, parent=None, align=TextNode.ACenter,
              color=WHITE):
        # Small captions were difficult to read even on a large monitor.
        # Enlarge the supporting labels throughout menu, HUD and results.
        if scale <= 0.04:
            scale *= 1.60
        return OnscreenText(text, pos=pos, scale=scale, font=self.font, fg=color,
                            align=align, parent=parent, mayChange=True)

    def card(self, parent, x, z, width, height, color=CARD, outline=True):
        frame = DirectFrame(parent=parent, pos=(x, 0, z), relief=None,
                             frameColor=(0, 0, 0, 0), frameSize=(-width, width, -height, height))
        if outline:
            edge = rounded(width + 0.003, height + 0.003, BORDER)
            edge.reparentTo(frame)
        fill = rounded(width, height, color)
        fill.reparentTo(frame)
        return frame

    def button(self, text, pos, command, parent, primary=False, width=0.47, height=0.067):
        base = GOLD if primary else (0.10, 0.17, 0.20, 1)
        hover = (1, 0.81, 0.44, 1) if primary else (0.16, 0.26, 0.29, 1)
        pressed = (0.88, 0.59, 0.20, 1) if primary else (0.07, 0.13, 0.16, 1)
        return DirectButton(parent=parent, text=text, command=command, pos=pos,
                            geom=tuple(rounded(width, height, color, 0.025)
                                       for color in (base, pressed, hover, base)),
                            frameSize=(-width, width, -height, height), relief=None,
                            frameColor=(0, 0, 0, 0), text_font=self.font, text_scale=0.052,
                            text_fg=INK if primary else WHITE, text_pos=(0, -0.018),
                            pressEffect=False, rolloverSound=None, clickSound=None)

    def key_icon(self, name, parent, x, z, scale=0.044):
        path = Path(__file__).resolve().parent / "assets" / "ui" / ("keyboard_" + name + ".png")
        if not path.is_file():
            return self.label(name.upper(), (x, z - 0.012), scale * 0.7, parent)
        icon = OnscreenImage(image=Filename.fromOsSpecific(str(path)).getFullpath(),
                             parent=parent, pos=(x, 0, z), scale=scale)
        icon.setTransparency(TransparencyAttrib.MAlpha)
        return icon

    def ui(self):
        self.hud = DirectFrame(frameColor=(0, 0, 0, 0), relief=None)
        speed = self.card(self.hud, -1.35, 0.78, 0.31, 0.145)
        self.label("当前速度", (-0.23, 0.075), 0.032, speed, TextNode.ALeft, MUTED)
        self.speed_value = self.label("180", (-0.23, -0.045), 0.10, speed, TextNode.ALeft)
        self.label("km/h", (0.16, -0.045), 0.032, speed, TextNode.ALeft, MUTED)

        mission = self.card(self.hud, -0.10, 0.80, 0.86, 0.125)
        self.mission_caption = self.label("领航挑战", (-0.76, 0.065), 0.032, mission, TextNode.ALeft, MINT)
        self.hudtext = self.label("", (-0.76, -0.015), 0.054, mission, TextNode.ALeft)
        self.progress_bar = DirectWaitBar(parent=mission, range=100, value=0,
                                          frameSize=(-0.76, 0.76, -0.007, 0.007), pos=(0, 0, -0.075),
                                          barColor=MINT, frameColor=(0.12, 0.23, 0.27, 1), relief=None)
        timer = self.card(self.hud, 1.25, 0.78, 0.40, 0.145)
        self.timer_caption = self.label("剩余时间", (-0.30, 0.075), 0.032, timer, TextNode.ALeft, MUTED)
        self.timer_value = self.label("90.0", (-0.30, -0.045), 0.09, timer, TextNode.ALeft, GOLD)

        health = self.card(self.hud, -1.27, -0.71, 0.39, 0.13)
        self.player_health = self.label("", (-0.29, 0.025), 0.038, health, TextNode.ALeft)
        self.escort_health = self.label("", (-0.29, -0.060), 0.038, health, TextNode.ALeft, MINT)
        self.team_card = self.card(self.hud, 1.31, -0.64, 0.34, 0.20)
        self.label("护送队距", (-0.26, 0.130), 0.030, self.team_card, TextNode.ALeft, MUTED)
        self.team_status = self.label("队距良好", (-0.26, 0.055), 0.038,
                                       self.team_card, TextNode.ALeft, MINT)
        self.team_gap_bar = DirectWaitBar(parent=self.team_card, range=100, value=0,
                                          frameSize=(-0.26, 0.26, -0.009, 0.009),
                                          pos=(0, 0, -0.005), barColor=MINT,
                                          frameColor=(0.12, 0.23, 0.27, 1), relief=None)
        # Match the existing early warning at half the detachment distance.
        marker = rounded(0.002, 0.014, WHITE, 0.001)
        marker.reparentTo(self.team_card)
        marker.setPos(0, 0, -0.005)
        self.team_gap_value = self.label("", (-0.26, -0.065), 0.029,
                                         self.team_card, TextNode.ALeft, WHITE)
        self.team_hint = self.label("", (-0.26, -0.135), 0.030,
                                    self.team_card, TextNode.ALeft, MINT)
        self.status_frame = self.card(self.hud, 0.03, -0.73, 0.82, 0.15)
        self.signal_icon = self.key_icon("h", self.status_frame, -0.70, 0.015, 0.064)
        self.signal_caption = self.label("请求通行", (-0.57, 0.080), 0.030,
                                          self.status_frame, TextNode.ALeft, MINT)
        self.feedback = self.label("", (-0.57, -0.002), 0.038,
                                   self.status_frame, TextNode.ALeft)
        self.feedback_hint = self.label("", (-0.57, -0.080), 0.032,
                                        self.status_frame, TextNode.ALeft, WHITE)
        self.tip = self.label("WASD / 方向键驾驶     ESC 暂停     F 全屏     M 声音", (0, -0.955), 0.033, self.hud, color=MUTED)

        self.panel = DirectFrame(frameColor=(0, 0, 0, 0), relief=None)
        self.shade = rounded(5, 2, (0.015, 0.035, 0.055, 0.88), 0.01)
        self.shade.reparentTo(self.panel)
        self.shade.setBin("fixed", -20)
        self.menu_content = DirectFrame(parent=self.panel, frameColor=(0, 0, 0, 0), relief=None)
        root = self.menu_content
        badge = self.card(root, -1.08, 0.74, 0.38, 0.045, (0.07, 0.21, 0.20, 1), outline=False)
        self.label("单人离线  /  公路街机", (0, -0.012), 0.034, badge, color=MINT)
        self.title = self.label("极速公路", (-1.46, 0.43), 0.145, root, TextNode.ALeft)
        self.label("S P E E D   H I G H W A Y", (-1.45, 0.31), 0.034, root, TextNode.ALeft, MUTED)
        self.subtitle = self.label("", (-1.45, 0.12), 0.055, root, TextNode.ALeft, MINT)
        self.info = self.label("", (-1.45, -0.04), 0.055, root, TextNode.ALeft)
        self.menu_story = DirectFrame(parent=root, frameColor=(0, 0, 0, 0), relief=None)
        self._route_story(self.menu_story)
        self.hero_note = self.label("", (-1.45, -0.58), 0.034, root, TextNode.ALeft, MUTED)
        self.label("带上队伍，再出发。", (-1.45, -0.87), 0.034, root, TextNode.ALeft, MUTED)

        self.menu_card = self.card(root, 0.95, 0.01, 0.60, 0.77, INK)
        self.mode_title = self.label("", (0.48, 0.59), 0.057, root, TextNode.ALeft)
        self.label("当前模式", (0.48, 0.68), 0.032, root, TextNode.ALeft, MUTED)
        self.mode_button = self.button("", (0.95, 0, 0.405), self.switch_mode, root)
        self.scenario_caption = self.label("路况", (0.48, 0.285), 0.032, root, TextNode.ALeft, MUTED)
        self.scenario_button = self.button("", (0.95, 0, 0.175), self.cycle_scenario, root, height=0.055)
        self.classic_route = self.label("无限公路 · 挑战最高分", (0.95, 0.16), 0.036, root, color=MUTED)
        self.label("我的座驾", (0.48, 0.055), 0.032, root, TextNode.ALeft, MUTED)
        self.pick = self.label("", (0.95, -0.07), 0.055, root)
        self.left = self.button("‹", (0.53, 0, -0.055), lambda: self.action("prev"), root, width=0.065, height=0.050)
        self.right = self.button("›", (1.37, 0, -0.055), lambda: self.action("next"), root, width=0.065, height=0.050)
        self.record_caption = self.label("护送纪录", (0.48, -0.205), 0.034, root, TextNode.ALeft, MUTED)
        self.record_value = self.label("0000", (1.41, -0.22), 0.046, root, TextNode.ARight, WHITE)
        self.primary = self.button("", (0.95, 0, -0.405), self.confirm, root, primary=True, height=0.079)
        self.secondary = self.button("", (0.95, 0, -0.585), lambda: self.action("quit"), root, height=0.055)
        self.label("ENTER 出发  ·  TAB 切换模式", (0.95, -0.70), 0.029, root, color=MUTED)
        for key, label, x in (("enter", "出发", 0.40), ("tab", "切换模式", 0.84), ("escape", "暂停", 1.43)):
            self.key_icon(key, root, x - 0.10, -0.865)
            self.label(label, (x, -0.878), 0.033, root, TextNode.ALeft, MUTED)

        self.end_content = self.card(self.panel, 0, 0.02, 0.91, 0.77, INK)
        self.end_badge = self.label("", (0, 0.56), 0.038, self.end_content, color=MINT)
        self.end_title = self.label("", (0, 0.38), 0.105, self.end_content)
        self.end_info = self.label("", (0, 0.225), 0.039, self.end_content, color=MUTED)
        self.metrics = []
        for x in (-0.55, 0, 0.55):
            metric = self.card(self.end_content, x, -0.035, 0.235, 0.125, CARD, outline=False)
            caption = self.label("", (0, 0.055), 0.032, metric, color=MUTED)
            value = self.label("", (0, -0.065), 0.065, metric)
            self.metrics.append((caption, value))
        self.end_record = self.label("", (0, -0.245), 0.034, self.end_content, color=MINT)
        self.layout_ui()
        self.refresh()

    def _route_story(self, parent):
        line = rounded(0.56, 0.002, (0.21, 0.39, 0.40, 1), 0.002)
        line.reparentTo(parent)
        line.setPos(-0.87, 0, -0.35)
        for x, number, name in ((-1.40, "01", "请求"), (-0.88, "02", "等待"), (-0.35, "03", "通行")):
            dot = self.card(parent, x, -0.35, 0.06, 0.044, (0.09, 0.26, 0.24, 1), outline=False)
            self.label(number, (0, -0.011), 0.032, dot, color=MINT)
            self.label(name, (x, -0.46), 0.036, parent, color=MUTED)

    def layout_ui(self):
        scale = min(1.0, self.getAspectRatio() / 1.78)
        for node in (self.menu_content, self.hud, self.end_content):
            node.setScale(scale)

    def refresh(self):
        active = self.state == "playing"
        escort = self.mode == "escort"
        menu = self.state == "menu"
        self.hud.show() if active else self.hud.hide()
        self.panel.hide() if active else self.panel.show()
        self.menu_content.show() if menu else self.menu_content.hide()
        self.end_content.hide() if menu else self.end_content.show()
        for control in (self.left, self.right, self.mode_button):
            control.show() if menu else control.hide()
        self.scenario_button.show() if menu and escort else self.scenario_button.hide()
        self.classic_route.hide() if escort else self.classic_route.show()
        self.primary.reparentTo(self.menu_content if menu else self.end_content)
        self.secondary.reparentTo(self.menu_content if menu else self.end_content)
        self.primary.setPos(0.95 if menu else 0, 0, -0.405)
        self.secondary.setPos(0.95 if menu else 0, 0, -0.585)
        scenario_name = dict(open="通行练习", staggered="错峰车流", blocked="拥堵开局")[self.args.scenario]
        self.scenario_button["text"] = scenario_name + "    ›    C"
        self.pick.setText(VEHICLES[self.vehicle_index]["name"])
        self.record_caption.setText("护送纪录" if escort else "最高分")
        self.record_value.setText(f"{self.escort_best if escort else self.best:04d}")
        if menu:
            self.title.setText("极速公路")
            self.mode_title.setText("领航挑战" if escort else "经典超车")
            self.subtitle.setText("把整队，一起带过去。" if escort else "穿过车流，保持节奏。")
            self.info.setText("看懂车流，创造空隙。\n驾驶领航车，把后方队伍安全带到终点。" if escort else
                              "一条公路，一路向前。\n在车流之间寻找节奏，挑战你的最高分。")
            self.hero_note.setText("90 秒任务  /  安全让行  /  车队协作" if escort else
                                   "无限公路  /  六种车型  /  超车 +150")
            self.menu_story.show() if escort else self.menu_story.hide()
            self.mode_button["text"] = "切换到经典超车  /  TAB" if escort else "切换到领航挑战  /  TAB"
            self.primary["text"] = "开始领航     →" if escort else "开始挑战     →"
            self.secondary["text"] = "退出游戏"
            self.secondary["command"] = lambda: self.action("quit")
            return
        self.secondary["text"] = "返回首页"
        self.secondary["command"] = lambda: self.action("menu")
        if self.state == "paused":
            self.end_badge.setText("TAKE A BREATH  /  暂停中")
            self.end_title.setText("队伍在等你" if escort else "稍作停留")
            self.end_info.setText("准备好了，就继续出发。")
            values = (("护送进度", f"{self.model.progress:.0%}"), ("剩余时间", f"{self.model.remaining:.0f}s"),
                      ("护送生命", f"{self.model.escort_life} / 3")) if escort else (
                          ("当前分数", str(self.model.score)), ("已超车", str(self.model.passed)), ("生命", str(self.model.life)))
            self.primary["text"] = "继续驾驶     →"
            self.end_record.setText("ENTER / ESC 继续    ·    F 切换全屏")
        else:
            success = escort and self.model.success
            self.end_badge.setText("MISSION COMPLETE" if success else "ANOTHER JOURNEY")
            self.end_title.setText("全队抵达" if success else "下一程，再出发")
            self.end_info.setText(self.model.reason if escort else "每一次出发，都能更进一步。")
            values = (("护送进度", f"{self.model.progress:.0%}"), ("成功让行", str(self.model.yields)),
                      ("任务评分", str(self.model.score))) if escort else (
                          ("本次分数", str(self.model.score)), ("成功超车", str(self.model.passed)), ("最高分", str(self.best)))
            self.primary["text"] = "再跑一次     →"
            self.end_record.setText(f"护送纪录  {self.escort_best:04d}" if escort else f"最高纪录  {self.best:06d}")
        for (caption, value), (text, number) in zip(self.metrics, values):
            caption.setText(text)
            value.setText(number)

    def hud_update(self):
        model = self.model
        escort = self.mode == "escort"
        self.speed_value.setText(f"{int(model.speed):03d}")
        self.player_health.setText("领航  " + "● " * model.life if escort else "生命  " + "● " * model.life)
        if escort:
            self.mission_caption.setText("领航挑战  /  护送任务")
            self.hudtext.setText(f"全队抵达进度   {model.progress:.0%}")
            self.timer_caption.setText("剩余时间")
            self.timer_value.setText(f"{model.remaining:04.1f}")
            self.timer_value.setFg(RED if model.remaining < 15 else GOLD)
            self.progress_bar.show()
            self.progress_bar["value"] = model.progress * 100
            self.escort_health.setText("护送  " + "● " * model.escort_life)
            self.team_card.show()
            status, team_hint, team_kind = model.team_feedback
            color = dict(info=MINT, warning=GOLD, danger=RED)[team_kind]
            self.team_status.setText(status)
            self.team_status.setFg(color)
            self.team_gap_bar["value"] = max(0.0, min(100.0, model.gap / model.max_gap * 100))
            self.team_gap_bar["barColor"] = color
            self.team_gap_value.setText(f"{model.gap:.0f} / {model.max_gap:.0f}  ·  脱队线")
            self.team_hint.setText(team_hint)
            self.team_hint.setFg(color)
            self.signal_icon.show()
            self.signal_caption.setText(f"信号冷却  {model.cooldown:.1f}s" if model.cooldown > 0 else "请求通行  /  信号就绪")
            self.signal_caption.setFg(GOLD if model.cooldown > 0 else MINT)
            message, hint, kind = model.passage_feedback
            self.feedback.setText(message)
            self.feedback.setFg(dict(info=WHITE, accepted=MINT, warning=GOLD, danger=RED)[kind])
            self.feedback_hint.setText(hint)
            self.feedback_hint.show()
        else:
            self.mission_caption.setText("经典超车  /  无限公路")
            self.hudtext.setText(f"分数   {model.score:06d}      最高   {self.best:06d}")
            self.progress_bar.hide()
            self.timer_caption.setText("本次驾驶")
            self.timer_value.setText(f"{int(model.elapsed) // 60:02d}:{int(model.elapsed) % 60:02d}")
            self.timer_value.setFg(WHITE)
            self.escort_health.setText(f"超车  {model.passed} 辆")
            self.team_card.hide()
            self.signal_icon.hide()
            self.signal_caption.setText("保持节奏，向前出发。")
            self.signal_caption.setFg(MINT)
            self.feedback.setText("驶出路面会减速；碰撞后有两秒保护。")
            self.feedback.setFg(WHITE)
            self.feedback_hint.hide()
