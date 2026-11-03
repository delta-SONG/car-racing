"""Speed Highway: classic racing and the cooperative escort prototype."""

import argparse
import json
from pathlib import Path
import time

from direct.showbase.ShowBase import ShowBase
from panda3d.core import ClockObject, Filename, TextNode, WindowProperties, loadPrcFileData

from classic3d_model import MAX_SPEED, Model, VEHICLES
from escort_model import EscortModel
from highway_ui import HighwayUI
from platform_support import chinese_font, save_directory
from procedural_audio import ProceduralAudio
from scene3d import HighwayScene


SAVE_DIR = save_directory()


def options(argv=None):
    parser = argparse.ArgumentParser(description="极速公路 · 经典超车与领航试验")
    parser.add_argument("--mode", choices=("classic", "escort"), default="classic")
    parser.add_argument("--scenario", choices=("open", "staggered", "blocked"), default="open")
    parser.add_argument("--smoke", type=float, default=0, help="Seconds of automated driving; never loads player saves")
    parser.add_argument("--native-smoke", action="store_true", help="Use a real window for automated driving")
    parser.add_argument("--no-save", action="store_true", help="Neither load nor write player saves")
    parser.add_argument("--screenshot")
    parser.add_argument("--screenshot-at", type=float, default=5)
    parser.add_argument("--report")
    args = parser.parse_args(argv)
    if args.smoke < 0 or args.screenshot_at < 0:
        parser.error("Durations must be non-negative")
    return args


class Game3D(HighwayUI, HighwayScene, ShowBase):
    def __init__(self, args):
        self.args = args
        loadPrcFileData("speed-highway", "window-title 极速公路 · SPEED HIGHWAY 3D\n"
                        "win-size 1280 720\nsync-video false\nclock-mode limited\nclock-frame-rate 60\n")
        # Explicitly restore window type between test instances in one process.
        loadPrcFileData("test-window", "window-type " + ("offscreen" if args.smoke and not args.native_smoke else "onscreen"))
        if args.smoke:
            loadPrcFileData("test-audio", "audio-library-name null")
        super().__init__()
        clock = ClockObject.getGlobalClock()
        clock.setMode(ClockObject.MLimited)
        clock.setFrameRate(60)
        self.disableMouse()
        bundled_font = Path(__file__).resolve().parent / "assets" / "NotoSansCJKsc-Regular.otf"
        font_path = str(bundled_font) if bundled_font.is_file() else chinese_font()
        if not font_path:
            raise RuntimeError("No Chinese font is available; prepare assets before running")
        self.font = self.loader.loadFont(Filename.fromOsSpecific(str(font_path)).getFullpath())
        if not self.font:
            raise RuntimeError("Unable to load Chinese font")
        TextNode.setDefaultFont(self.font)
        self.best, self.escort_best, self.muted, self.vehicle_index = 0, 0, False, 0
        self.load_settings()
        self.mode = args.mode
        self.state = "menu"
        self.keys = set()
        self.fullscreen = False
        self.model = self.new_model()
        self.frames = self.playing_frames = self.episodes = self.successful_escorts = 0
        self.active_seconds = 0.0
        # Lifetime telemetry, including retries; never feed measurements back
        # into the model or weaken the 100 ms safety cap after a stall.
        self.timing = dict(frame_seconds=0.0, accepted_seconds=0.0,
                           clamped_seconds=0.0, long_frames=0,
                           max_frame_seconds=0.0, playing_wall_seconds=0.0,
                           playing_clamped_seconds=0.0)
        self.results = []
        self.screenshot_saved = False
        self.audio = ProceduralAudio(self.loader, enabled=not args.smoke)
        self.world()
        self.ui()
        self.events()
        # Exclude loading and shader/font warmup from measured gameplay time.
        self.started = self.last = time.perf_counter()
        self.taskMgr.add(self.tick, "highway-tick")
        if args.smoke:
            self.action("start")

    def new_model(self):
        if self.mode == "escort":
            return EscortModel(42, VEHICLES, self.args.scenario)
        return Model(42 if self.args.smoke else None)

    def load_settings(self):
        if self.args.smoke or self.args.no_save:
            return
        try:
            path = SAVE_DIR / "save3d.json"
            if not path.exists():
                path = SAVE_DIR / "save.json"  # Read legacy data once; never overwrite it.
            data = json.loads(path.read_text(encoding="utf-8"))
            self.best = max(0, int(data.get("best", 0)))
            self.escort_best = max(0, int(data.get("escort_best", 0)))
            self.muted = bool(data.get("muted", False))
            self.vehicle_index = int(data.get("vehicle", 0)) % len(VEHICLES)
        except (OSError, ValueError, TypeError, AttributeError, OverflowError):
            self.best, self.escort_best, self.muted, self.vehicle_index = 0, 0, False, 0

    def save(self):
        if self.args.smoke or self.args.no_save:
            return
        try:
            SAVE_DIR.mkdir(parents=True, exist_ok=True)
            temporary = SAVE_DIR / "save3d.tmp"
            temporary.write_text(json.dumps(dict(best=self.best, escort_best=self.escort_best,
                                                 muted=self.muted, vehicle=self.vehicle_index)), encoding="utf-8")
            temporary.replace(SAVE_DIR / "save3d.json")
        except OSError:
            pass

    def remember_score(self):
        if self.mode == "classic":
            self.best = max(self.best, self.model.score)
        elif self.model.success:
            self.escort_best = max(self.escort_best, self.model.score)
        self.save()




    def events(self):
        for key in ("arrow_left", "arrow_right", "arrow_up", "arrow_down", "w", "a", "s", "d"):
            self.accept(key, self.key_down, [key])
            self.accept(key + "-up", self.keys.discard, [key])
        self.accept("escape", self.pause)
        self.accept("m", self.mute)
        self.accept("h", self.signal)
        self.accept("f11", self.full)
        self.accept("f", self.full)
        self.accept("enter", self.confirm)
        self.accept("space", self.confirm)
        self.accept("tab", self.switch_mode)
        self.accept("c", self.cycle_scenario)

    def key_down(self, key):
        if self.state == "menu" and key in ("arrow_left", "arrow_right", "a", "d"):
            self.action("prev" if key in ("arrow_left", "a") else "next")
        elif self.state == "playing":
            self.keys.add(key)

    def windowEvent(self, window):
        super().windowEvent(window)
        if hasattr(self, "menu_content"):
            self.layout_ui()
        if (hasattr(self, "state") and window == self.win and hasattr(window, "getProperties")
                and not window.getProperties().getForeground() and not self.args.smoke):
            self.pause_for_focus_loss()

    def pause_for_focus_loss(self):
        self.keys.clear()
        if self.state == "playing":
            self.state = "paused"
            self.audio.update(0, False, self.muted)
            self.refresh()

    def pause(self):
        if self.state == "playing":
            self.state = "paused"
        elif self.state == "paused":
            self.state = "playing"
        else:
            return
        self.keys.clear()
        self.last = time.perf_counter()
        self.audio.update(self.model.speed, self.state == "playing", self.muted)
        self.refresh()

    def mute(self):
        self.muted = not self.muted
        self.save()
        self.audio.update(self.model.speed, self.state == "playing", self.muted)
        self.refresh()

    def full(self):
        if hasattr(self.win, "requestProperties"):
            self.fullscreen = not self.fullscreen
            properties = WindowProperties()
            properties.setFullscreen(self.fullscreen)
            if not self.fullscreen:
                properties.setSize(1280, 720)
            self.win.requestProperties(properties)

    def signal(self):
        if self.mode == "escort" and self.state == "playing":
            if self.model.request_passage():
                self.audio.play("signal", self.muted)

    def switch_mode(self):
        if self.state != "menu":
            return
        self.mode = "escort" if self.mode == "classic" else "classic"
        self.model = self.new_model()
        self.keys.clear()
        self.refresh()

    def cycle_scenario(self):
        if self.state != "menu" or self.mode != "escort":
            return
        scenarios = ("open", "staggered", "blocked")
        self.args.scenario = scenarios[(scenarios.index(self.args.scenario) + 1) % len(scenarios)]
        self.model = self.new_model()
        self.refresh()

    def confirm(self):
        if self.state != "playing":
            self.action("resume" if self.state == "paused" else "start")

    def action(self, action):
        if action in ("start", "menu", "quit"):
            self.remember_score()
        self.keys.clear()
        if action == "start":
            for node, _ in self.traffic.values():
                node.removeNode()
            self.traffic.clear()
            self.model = self.new_model()
            self.state = "playing"
            self.episodes += 1
        elif action == "resume":
            self.state = "playing"
        elif action == "menu":
            self.state = "menu"
        elif action == "quit":
            self.userExit()
            return
        elif action in ("prev", "next") and self.state == "menu":
            self.vehicle_index = (self.vehicle_index + (-1 if action == "prev" else 1)) % len(VEHICLES)
            self.player.removeNode()
            self.player = self.car(VEHICLES[self.vehicle_index], "player")
            self.player.reparentTo(self.render)
            self.player_tag = self.world_label(self.player, "你 · 领航车", (1, 0.85, 0.35, 1))
            self.save()
        self.last = time.perf_counter()
        self.audio.play("click", self.muted)
        self.refresh()



    def autopilot(self):
        if self.mode == "escort":
            return self.model.autopilot()
        danger = [car for car in self.model.cars if 0 < car["z"] < 450]
        target = min((-0.66, 0, 0.66), key=lambda x: sum(1 / max(20, car["z"]) for car in danger
                     if abs(car["x"] - x) < 0.3) + abs(x - self.model.x) * 0.0001)
        return max(-1, min(1, (target - self.model.x) * 5)), True, False

    def tick(self, task):
        now = time.perf_counter()
        raw_dt = max(0, now - self.last)
        dt = min(raw_dt, 0.1)
        self.last = now
        self.timing["frame_seconds"] += raw_dt
        self.timing["accepted_seconds"] += dt
        self.timing["clamped_seconds"] += raw_dt - dt
        self.timing["long_frames"] += int(raw_dt > 0.1)
        self.timing["max_frame_seconds"] = max(self.timing["max_frame_seconds"], raw_dt)
        if self.state == "playing":
            self.timing["playing_wall_seconds"] += raw_dt
            self.timing["playing_clamped_seconds"] += raw_dt - dt
            if self.args.smoke:
                steer, gas, brake = self.autopilot()
            else:
                steer = int(bool({"arrow_right", "d"} & self.keys)) - int(bool({"arrow_left", "a"} & self.keys))
                gas, brake = bool({"arrow_up", "w"} & self.keys), bool({"arrow_down", "s"} & self.keys)
            before = self.model.elapsed
            if self.model.update(dt, steer, gas, brake):
                self.audio.play("crash", self.muted)
            self.active_seconds += self.model.elapsed - before
            self.playing_frames += 1
            if self.model.dead:
                self.remember_score()
                success = self.mode == "escort" and self.model.success
                self.successful_escorts += int(success)
                self.results.append(dict(success=success, score=self.model.score,
                                          reason=getattr(self.model, "reason", "生命耗尽"),
                                          driving_seconds=self.model.elapsed))
                self.state = "over"
                self.refresh()
                # Continue driving instead of counting the result screen as a soak.
                if self.args.smoke:
                    self.action("start")
        self.scene(dt)
        self.hud_update()
        self.audio.update(self.model.speed, self.state == "playing", self.muted)
        self.frames += 1
        elapsed = now - self.started
        if self.args.screenshot and not self.screenshot_saved and elapsed >= self.args.screenshot_at:
            self.capture(self.args.screenshot)
            self.screenshot_saved = True
        if self.args.smoke and elapsed >= self.args.smoke:
            if self.args.screenshot and not self.screenshot_saved:
                self.capture(self.args.screenshot)
            self.write_report(elapsed)
            self.taskMgr.stop()
            return task.done
        return task.cont

    def capture(self, path):
        destination = Path(path).resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not self.win.saveScreenshot(Filename.fromOsSpecific(str(destination))):
            raise RuntimeError("Screenshot capture failed")

    def write_report(self, elapsed):
        if not self.args.report:
            return
        data = dict(mode=self.mode, scenario=self.args.scenario, seconds=elapsed,
                    frame_limit=60, vertical_sync=False, clock_source="perf_counter",
                    frames=self.frames, average_fps=self.frames / max(elapsed, 0.001),
                    active_driving_seconds=self.active_seconds, playing_frames=self.playing_frames,
                    timing=self.timing,
                    timing_note="Wall intervals and time removed by the unchanged 100ms frame cap; not native performance evidence.",
                    episodes=self.episodes, successful_escorts=self.successful_escorts,
                    completed_results=self.results, score=self.model.score, life=self.model.life,
                    controller="automated, not a human playtest", saves_disabled=True,
                    native_window=bool(self.args.native_smoke),
                    focus_pause_disabled_for_smoke=True)
        destination = Path(self.args.report)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def destroy(self):
        if hasattr(self, "model"):
            self.remember_score()
        if hasattr(self, "audio"):
            self.audio.close()
        super().destroy()


if __name__ == "__main__":
    application = Game3D(options())
    try:
        application.run()
    finally:
        application.destroy()
