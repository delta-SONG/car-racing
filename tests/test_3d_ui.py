import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import game3d
from classic3d_model import Model, VEHICLES
from escort_model import EscortModel
from procedural_audio import ProceduralAudio


class ThreeDInterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = game3d.Game3D(game3d.options(["--mode", "escort", "--smoke", "3600"]))

    @classmethod
    def tearDownClass(cls):
        cls.app.destroy()

    def setUp(self):
        self.app.action("menu")
        if self.app.mode != "escort":
            self.app.switch_mode()
        self.app.action("start")

    def test_modes_use_distinct_models_and_can_restart(self):
        app = self.app
        self.assertIsInstance(app.model, EscortModel)
        app.action("menu")
        app.switch_mode()
        self.assertIsInstance(app.model, Model)
        app.action("start")
        app.scene(0.1)
        self.assertTrue(app.escort_car.isHidden())
        app.action("menu")
        app.switch_mode()
        app.action("start")
        app.scene(0.1)
        self.assertFalse(app.escort_car.isHidden())

    def test_menu_names_current_mode_and_switch_target(self):
        app = self.app
        app.action("menu")
        self.assertEqual(app.mode_title.getText(), "领航挑战")
        self.assertIn("切换到经典超车", app.mode_button["text"])
        app.messenger.send("tab")
        self.assertEqual(app.mode_title.getText(), "经典超车")
        self.assertIn("切换到领航挑战", app.mode_button["text"])

    def test_raw_letter_keys_control_vehicle_and_release(self):
        app = self.app
        app.messenger.send("raw-w")
        app.messenger.send("raw-a")
        self.assertTrue({"w", "a"}.issubset(app.keys))
        app.messenger.send("raw-w-up")
        app.messenger.send("raw-a-up")
        self.assertFalse({"w", "a"} & app.keys)
        app.model.cars = [app.model.make_car(400, 0, vehicle=VEHICLES[0])]
        app.messenger.send("raw-h")
        self.assertEqual(app.model.requests, 1)

    def test_borderless_toggle_restores_window_geometry_without_fullscreen_mode(self):
        from panda3d.core import WindowProperties
        original = WindowProperties()
        original.setOrigin(120, 80)
        original.setSize(960, 540)
        requests = []
        fake_window = SimpleNamespace(getProperties=lambda: original,
                                      requestProperties=requests.append)
        fake = SimpleNamespace(win=fake_window, fullscreen=False, _windowed_rect=None,
                               pipe=SimpleNamespace(getDisplayWidth=lambda: 1920,
                                                    getDisplayHeight=lambda: 1080))
        with patch("game3d.monitor_rectangle", return_value=(-1920, 0, 1920, 1080)):
            game3d.Game3D.full(fake)
        self.assertTrue(fake.fullscreen)
        self.assertTrue(requests[0].getUndecorated())
        self.assertFalse(requests[0].hasFullscreen())
        self.assertEqual(tuple(requests[0].getOrigin()), (-1920, 0))
        self.assertEqual(tuple(requests[0].getSize()), (1920, 1080))
        game3d.Game3D.full(fake)
        self.assertFalse(fake.fullscreen)
        self.assertFalse(requests[1].getUndecorated())
        self.assertFalse(requests[1].hasFullscreen())
        self.assertEqual(tuple(requests[1].getOrigin()), (120, 80))
        self.assertEqual(tuple(requests[1].getSize()), (960, 540))

    def test_stall_telemetry_accounts_for_lost_time_without_advancing_model(self):
        app = self.app
        before = dict(app.timing)
        elapsed, active = app.model.elapsed, app.active_seconds
        with patch("game3d.time.perf_counter", return_value=app.last + 0.45):
            app.tick(SimpleNamespace(cont="continue", done="done"))
        self.assertAlmostEqual(app.model.elapsed - elapsed, 0.1)
        self.assertAlmostEqual(app.active_seconds - active, 0.1)
        for name, expected in (("frame_seconds", .45), ("accepted_seconds", .1),
                               ("clamped_seconds", .35), ("long_frames", 1),
                               ("playing_wall_seconds", .45),
                               ("playing_clamped_seconds", .35)):
            self.assertAlmostEqual(app.timing[name] - before[name], expected)
        self.assertGreaterEqual(app.timing["max_frame_seconds"], .45 - 1e-8)

    def test_paused_stall_is_not_counted_as_driving_and_report_preserves_timing(self):
        app = self.app
        app.pause_for_focus_loss()
        before = dict(app.timing)
        elapsed = app.model.elapsed
        with patch("game3d.time.perf_counter", return_value=app.last + 2):
            app.tick(SimpleNamespace(cont="continue", done="done"))
        self.assertEqual(app.model.elapsed, elapsed)
        self.assertEqual(app.timing["playing_wall_seconds"], before["playing_wall_seconds"])
        self.assertEqual(app.timing["playing_clamped_seconds"], before["playing_clamped_seconds"])
        self.assertAlmostEqual(app.timing["clamped_seconds"] - before["clamped_seconds"], 1.9)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            with patch.object(app.args, "report", str(path)):
                app.write_report(10)
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["timing"], app.timing)
            self.assertFalse(data["native_window"])

    def test_messenger_signal_and_pause_events(self):
        app = self.app
        app.model.cars = [app.model.make_car(400, 0, vehicle=VEHICLES[0])]
        app.messenger.send("raw-h")
        self.assertEqual(app.model.requests, 1)
        app.messenger.send("escape")
        self.assertEqual(app.state, "paused")
        before = app.model.elapsed
        with patch("game3d.time.perf_counter", return_value=app.last + 0.05):
            app.tick(SimpleNamespace(cont="continue", done="done"))
        self.assertEqual(app.model.elapsed, before)
        app.messenger.send("enter")
        self.assertEqual(app.state, "playing")

    def test_refusal_guidance_survives_repeated_h_and_pause(self):
        app = self.app
        app.model.cars = [app.model.make_car(400, lane, vehicle=VEHICLES[0])
                          for lane in (0, -0.66, 0.66)]
        app.messenger.send("raw-h")
        app.hud_update()
        reason, hint = app.feedback.getText(), app.feedback_hint.getText()
        self.assertIn("占用", reason)
        self.assertIn("S", hint)
        self.assertIn("冷却", app.signal_caption.getText())
        app.messenger.send("raw-h")
        app.pause()
        before = app.model.cooldown, app.model.feedback_seconds
        with patch("game3d.time.perf_counter", return_value=app.last + 0.05):
            app.tick(SimpleNamespace(cont="continue", done="done"))
        self.assertEqual((app.model.cooldown, app.model.feedback_seconds), before)
        app.confirm()
        app.hud_update()
        self.assertEqual((app.feedback.getText(), app.feedback_hint.getText()), (reason, hint))

    def test_classic_mode_hides_escort_guidance_and_resets_warning_color(self):
        from highway_ui import WHITE
        app = self.app
        app.model.message("拒绝", hint="减速", kind="warning")
        app.hud_update()
        self.assertFalse(app.feedback_hint.isHidden())
        app.action("menu")
        app.switch_mode()
        app.action("start")
        app.hud_update()
        self.assertTrue(app.feedback_hint.isHidden())
        for actual, expected in zip(app.feedback.textNode.getTextColor(), WHITE):
            self.assertAlmostEqual(actual, expected, places=6)

    def test_team_warning_does_not_overwrite_passage_or_collision_guidance(self):
        from highway_ui import RED
        app = self.app
        app.model.escort_distance = app.model.distance - 620
        app.model.detached_seconds = 1.25
        app.model.message("护送车受损", hint="留出空间", kind="danger")
        app.hud_update()
        self.assertEqual(app.team_status.getText(), "脱队 3.8s")
        self.assertEqual(app.team_gap_bar["value"], 100)
        self.assertIn("620 / 540", app.team_gap_value.getText())
        self.assertIn("S", app.team_hint.getText())
        self.assertEqual(app.feedback.getText(), "护送车受损")
        self.assertEqual(app.feedback_hint.getText(), "留出空间")
        self.assertEqual(tuple(app.team_status.textNode.getTextColor()), tuple(app.feedback.textNode.getTextColor()))

    def test_team_countdown_freezes_on_focus_loss_and_restart_resets_it(self):
        app = self.app
        app.model.escort_distance = app.model.distance - 620
        app.model.detached_seconds = 2
        app.hud_update()
        before = app.team_status.getText(), app.team_gap_bar["value"]
        app.pause_for_focus_loss()
        with patch("game3d.time.perf_counter", return_value=app.last + 0.05):
            app.tick(SimpleNamespace(cont="continue", done="done"))
        self.assertEqual((app.team_status.getText(), app.team_gap_bar["value"]), before)
        app.action("start")
        app.hud_update()
        self.assertEqual(app.team_status.getText(), "队距良好")
        self.assertLess(app.team_gap_bar["value"], 50)
        app.action("menu")
        app.switch_mode()
        app.action("start")
        app.hud_update()
        self.assertTrue(app.team_card.isHidden())

    def test_team_recovery_restores_calm_color_and_hint(self):
        from highway_ui import MINT
        app = self.app
        app.model.escort_distance = app.model.distance - 360
        app.hud_update()
        self.assertEqual(app.team_status.getText(), "队距拉大")
        app.model.escort_distance = app.model.distance - 180
        app.hud_update()
        self.assertEqual(app.team_status.getText(), "队距良好")
        self.assertNotIn("减速", app.team_hint.getText())
        for actual, expected in zip(app.team_status.textNode.getTextColor(), MINT):
            self.assertAlmostEqual(actual, expected, places=6)

    def test_focus_loss_clears_keys_and_does_not_auto_resume(self):
        app = self.app
        app.keys.update(("w", "a"))
        app.pause_for_focus_loss()
        self.assertEqual(app.state, "paused")
        self.assertFalse(app.keys)
        app.pause_for_focus_loss()
        self.assertEqual(app.state, "paused")
        app.confirm()
        self.assertEqual(app.state, "playing")

    def test_vehicle_selection_and_scene_reset(self):
        app = self.app
        app.scene(0.1)
        self.assertGreater(len(app.traffic), 0)
        app.action("start")
        self.assertEqual(app.traffic, {})
        app.action("menu")
        previous = app.vehicle_index
        app.messenger.send("arrow_right")
        self.assertEqual(app.vehicle_index, (previous + 1) % len(VEHICLES))
        app.messenger.send("arrow_left")
        self.assertEqual(app.vehicle_index, previous)
        self.assertFalse(app.keys)

    def test_save_scores_are_separate_and_legacy_file_is_untouched(self):
        app = self.app
        with tempfile.TemporaryDirectory() as directory, patch.object(game3d, "SAVE_DIR", Path(directory)):
            root = Path(directory)
            legacy = '{"best":123,"muted":true,"vehicle":2}'
            (root / "save.json").write_text(legacy, encoding="utf-8")
            with patch.object(app.args, "smoke", 0):
                app.load_settings()
                self.assertEqual((app.best, app.escort_best), (123, 0))
                app.model.escort_distance = app.model.route_length
                app.model.distance = app.model.route_length + app.model.ideal_gap
                app.model.update(0.1)
                app.remember_score()
                data = json.loads((root / "save3d.json").read_text(encoding="utf-8"))
                self.assertEqual(data["best"], 123)
                self.assertGreater(data["escort_best"], 0)
                self.assertEqual((root / "save.json").read_text(encoding="utf-8"), legacy)
                (root / "save3d.json").write_text("{broken", encoding="utf-8")
                app.load_settings()
                self.assertEqual((app.best, app.escort_best), (0, 0))

    def test_smoke_mode_cannot_load_or_write_player_data(self):
        app = self.app
        with tempfile.TemporaryDirectory() as directory, patch.object(game3d, "SAVE_DIR", Path(directory)):
            app.best = 321
            app.save()
            app.load_settings()
            self.assertEqual(app.best, 321)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_all_vehicle_wheels_have_a_circular_cross_section_and_closed_caps(self):
        import math
        from panda3d.core import GeomVertexReader
        for vehicle in VEHICLES:
            car = self.app.car(vehicle, "wheel-regression")
            try:
                wheels = car.getPythonTag("wheels")
                self.assertEqual(len(wheels), 4)
                for wheel in wheels:
                    data = wheel.node().getGeom(0).getVertexData()
                    positions = GeomVertexReader(data, "vertex")
                    normals = GeomVertexReader(data, "normal")
                    rim_points, caps = set(), set()
                    while not positions.isAtEnd():
                        x, y, z = positions.getData3()
                        nx, ny, nz = normals.getData3()
                        radius = math.hypot(y, z)
                        self.assertLessEqual(radius, 0.30001)
                        self.assertLessEqual(abs(x), 0.193)
                        if abs(radius - 0.30) < 1e-5:
                            rim_points.add((round(y, 5), round(z, 5)))
                        if abs(nx) > 0.99:
                            caps.add(round(nx))
                    # A box has just four corners and a varying corner radius.
                    self.assertGreaterEqual(len(rim_points), 24)
                    self.assertEqual(caps, {-1, 1})
            finally:
                car.removeNode()

    def test_wheels_rotate_about_axle_without_growing_a_square_silhouette(self):
        for wheel in self.app.player.getPythonTag("wheels"):
            center = tuple(wheel.getPos())
            wheel.setP(0)
            before = wheel.getTightBounds(self.app.player)
            wheel.setP(22.5)
            after = wheel.getTightBounds(self.app.player)
            self.assertEqual(tuple(wheel.getPos()), center)
            for axis in (1, 2):
                self.assertAlmostEqual(before[1][axis] - before[0][axis], 0.6, places=5)
                self.assertAlmostEqual(after[1][axis] - after[0][axis], 0.6, places=5)

    def test_pause_freezes_wheel_animation(self):
        app = self.app
        app.scene(0.05)
        app.pause()
        wheel = app.player.getPythonTag("wheels")[0]
        before = wheel.getP()
        app.scene(1.0)
        self.assertEqual(wheel.getP(), before)

    def test_traffic_near_escort_remains_rendered_at_large_team_gaps(self):
        app = self.app
        for gap in (140, 360, 540, 620):
            app.model.escort_distance = app.model.distance - gap
            hazard = app.model.make_car(-gap + 90, -0.66, vehicle=VEHICLES[3])
            behind = app.model.make_car(-gap - 140, 0.66, vehicle=VEHICLES[0])
            distant = app.model.make_car(-gap - 221, 0, vehicle=VEHICLES[4])
            app.model.cars = [hazard, behind, distant]
            app.scene(0)
            self.assertIn(id(hazard), app.traffic, gap)
            self.assertIn(id(behind), app.traffic, gap)
            self.assertNotIn(id(distant), app.traffic, gap)
            node = app.traffic[id(hazard)][0]
            self.assertAlmostEqual(node.getY(), hazard["z"] / app.SCALE, places=5)
            # Pause must not drop the follower's surrounding traffic.
            app.pause()
            app.scene(1)
            self.assertIn(id(hazard), app.traffic)
            app.confirm()

    def test_rear_traffic_does_not_pop_out_at_old_leader_cutoff(self):
        app = self.app
        app.model.escort_distance = -360
        car = app.model.make_car(-219, -0.66, vehicle=VEHICLES[3])
        app.model.cars = [car]
        app.scene(0)
        node = app.traffic[id(car)][0]
        for relative in (-220, -221, -270, -450):
            car.update(distance=relative, z=relative)
            app.scene(0)
            self.assertEqual(app.traffic[id(car)][0], node)
        car.update(distance=-581, z=-581)
        app.scene(0)
        self.assertNotIn(id(car), app.traffic)
        self.assertTrue(node.isEmpty())
        app.action("start")
        app.scene(0)
        self.assertNotIn(id(car), app.traffic)

    def test_classic_keeps_original_front_only_traffic_culling(self):
        app = self.app
        app.action("menu")
        app.switch_mode()
        app.action("start")
        app.model.cars = [dict(z=z, x=0, speed=100, vehicle=VEHICLES[0])
                          for z in (-221, -1, 0, 100, 2299, 2300)]
        app.scene(0)
        self.assertEqual([car["z"] for car in app.model.cars if id(car) in app.traffic],
                         [0, 100, 2299])

    def test_generated_audio_resources_load_and_cleanup(self):
        audio = ProceduralAudio(self.app.loader)
        self.assertEqual(set(audio.sounds), {"engine", "click", "crash", "signal"})
        folder = Path(audio.directory.name)
        self.assertTrue((folder / "engine.wav").is_file())
        audio.update(180, True, False)
        self.assertTrue(audio.running)
        audio.update(180, True, True)
        self.assertFalse(audio.running)
        audio.close()
        self.assertFalse(folder.exists())

    def test_scenario_selection_only_applies_in_escort_menu(self):
        app = self.app
        scenario = app.args.scenario
        app.messenger.send("raw-c")
        self.assertEqual(app.args.scenario, scenario)
        app.action("menu")
        app.messenger.send("raw-c")
        self.assertNotEqual(app.args.scenario, scenario)
        app.messenger.send("raw-c")
        app.messenger.send("raw-c")
        self.assertEqual(app.args.scenario, scenario)
        self.assertFalse(app.scenario_button.isHidden())
        app.switch_mode()
        self.assertTrue(app.scenario_button.isHidden())

    def test_ui_scales_as_one_layout_on_narrow_windows(self):
        app = self.app
        with patch.object(app, "getAspectRatio", return_value=4 / 3):
            app.layout_ui()
            for node in (app.menu_content, app.hud, app.end_content):
                self.assertAlmostEqual(node.getScale().x, (4 / 3) / 1.78, places=5)
        app.layout_ui()


if __name__ == "__main__":
    unittest.main()
