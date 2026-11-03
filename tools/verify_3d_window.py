"""Automated native-window acceptance. Does not load/write player saves.

Uses engine messages and OS window properties, not a human playtest.
"""

import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from panda3d.core import WindowProperties
from game3d import Game3D, options
from classic3d_model import VEHICLES


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-desktop", action="store_true",
                        help="Requires the user's explicit permission for visible window tests")
    args = parser.parse_args()
    if not args.allow_desktop:
        parser.error("Visible window checks require explicit user permission and --allow-desktop")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    app = Game3D(options(["--mode", "escort", "--no-save"]))
    app.muted = True
    foreground = WindowProperties()
    foreground.setForeground(True)
    foreground.setMinimized(False)
    app.win.requestProperties(foreground)
    started = time.monotonic()
    checks = {}
    state = {}
    next_action = 0
    last_action = time.perf_counter()

    from direct.showbase.DirectObject import DirectObject
    observer = DirectObject()

    def observe_window(window):
        properties = window.getProperties()
        state.setdefault("window_events", []).append(dict(
            seconds=round(time.perf_counter() - last_action, 3),
            screen=app.state, foreground=properties.getForeground(),
            minimized=properties.getMinimized(), fullscreen=properties.getFullscreen()))

    observer.accept("window-event", observe_window)

    def restore_initial_window():
        # Win32 launch show-state can arrive after ShowBase opens the window.
        props = WindowProperties()
        props.setMinimized(False)
        props.setForeground(True)
        app.win.requestProperties(props)

    def capture(name):
        check("screenshot_window_restored_" + name, not app.win.getProperties().getMinimized())
        app.scene(0)
        app.hud_update()
        app.graphicsEngine.renderFrame()
        app.graphicsEngine.renderFrame()
        app.capture(output / (name + ".png"))

    def check(name, condition):
        checks[name] = bool(condition)
        properties = app.win.getProperties()
        state.setdefault("check_states", {})[name] = dict(
            screen=app.state, foreground=properties.getForeground(),
            minimized=properties.getMinimized(), fullscreen=properties.getFullscreen())
        if not condition:
            state["failed_state"] = dict(screen=app.state, life=app.model.life,
                                        foreground=app.win.getProperties().getForeground())
            raise AssertionError(name)

    def pause():
        # Launch/focus events may have paused before the scheduled ESC.
        # Resume explicitly so ESC itself is tested from a known playing state.
        if app.state == "paused":
            state["startup_focus_pause_observed"] = True
            app.confirm()
        check("playing_before_escape", app.state == "playing")
        app.messenger.send("escape")
        state["paused_time"] = app.model.elapsed
        check("escape_pauses", app.state == "paused")
        capture("pause")

    def resume():
        check("paused_model_frozen", app.model.elapsed == state["paused_time"])
        app.messenger.send("enter")
        check("enter_resumes", app.state == "playing")

    def minimize():
        check("window_restored_before_minimize", not app.win.getProperties().getMinimized())
        app.key_down("w")
        app.key_down("a")
        check("keys_held_before_focus_loss", bool(app.keys))
        props = WindowProperties()
        props.setMinimized(True)
        app.win.requestProperties(props)

    def restore():
        check("native_focus_loss_pauses", app.state == "paused")
        check("native_focus_loss_clears_keys", not app.keys)
        props = WindowProperties()
        props.setMinimized(False)
        props.setForeground(True)
        app.win.requestProperties(props)

    def after_restore():
        check("restore_does_not_resume", app.state == "paused")
        app.confirm()
        check("explicit_resume_after_focus_loss", app.state == "playing")
        capture("escort")

    def fullscreen():
        app.messenger.send("f")

    def check_fullscreen():
        check("fullscreen_requested", app.fullscreen)
        check("native_fullscreen_applied", app.win.getProperties().getFullscreen())

    def windowed():
        app.messenger.send("f")

    def check_windowed():
        check("windowed_requested", not app.fullscreen)
        check("native_windowed_applied", not app.win.getProperties().getFullscreen())

    def classic():
        app.action("menu")
        app.switch_mode()
        check("switch_to_classic", app.mode == "classic")
        app.action("start")

    def result_fixture():
        capture("classic")
        app.action("menu")
        app.switch_mode()
        app.action("start")
        app.model.cars.clear()
        app.model.escort_distance = app.model.route_length
        app.model.distance = app.model.route_length + app.model.ideal_gap
        app.model.update(0.02)
        app.remember_score()
        app.state = "over"
        app.refresh()
        capture("result-fixture")
        check("result_screen_fixture", app.model.success and not app.panel.isHidden())

    def resize(width, height):
        app.action("menu")
        props = WindowProperties()
        props.setSize(width, height)
        app.win.requestProperties(props)

    def capture_narrow():
        check("narrow_window_layout_scaled", app.menu_content.getScale().x < 0.76)
        capture("menu-960x720")

    def feedback_bounds():
        for name in ("signal_caption", "feedback", "feedback_hint"):
            bounds = getattr(app, name).getTightBounds(app.status_frame)
            check(name + "_inside_card_" + str(app.win.getXSize()) + "x" + str(app.win.getYSize()),
                  bounds is not None and bounds[0].x >= -0.78 and bounds[1].x <= 0.78
                  and bounds[0].z >= -0.14 and bounds[1].z <= 0.14)

    def feedback_fixture(kind, name):
        # These traffic states are synthetic fixtures for UI/engine checks;
        # they do not represent a human drive or a completed mission.
        app.action("start")
        model = app.model
        model.cars = [model.make_car(400, 0, vehicle=VEHICLES[0])]
        if kind == "blocked":
            model.cars.extend(model.make_car(400, lane, vehicle=VEHICLES[0]) for lane in (-0.66, 0.66))
        elif kind == "empty":
            model.cars.clear()
        elif kind == "close":
            model.cars[0]["distance"] = 80
        app.messenger.send("h")
        if kind == "cancelled":
            model.cars.append(model.make_car(400, -0.66, vehicle=VEHICLES[0]))
            model.update(0.9)
        elif kind == "ready":
            model.cooldown = 0
            model.feedback_seconds = 0
            model.cars.clear()
        capture(name)
        feedback_bounds()
        if kind == "blocked":
            check(name + "_reason_and_action", "占用" in app.feedback.getText()
                  and "S" in app.feedback_hint.getText())
            before = model.passage_feedback, model.cooldown
            app.messenger.send("h")
            check(name + "_repeated_h_preserves_reason", before == (model.passage_feedback, model.cooldown))
        elif kind == "cancelled":
            check("cancelled_request_explained", "取消" in app.feedback.getText()
                  and model.cars[0]["x"] == 0)
        elif kind == "accepted":
            check("accepted_request_acknowledged", model.cars[0]["state"] == "responding"
                  and "收到" in app.feedback.getText())
        elif kind == "ready":
            check("cooldown_ready_visible", "就绪" in app.signal_caption.getText())
        elif kind == "empty":
            check("no_target_costs_no_cooldown", "没有" in app.feedback.getText() and model.cooldown == 0)
        elif kind == "close":
            check("too_close_explained", "过近" in app.feedback.getText() and model.cooldown == 0)

    # Each interval starts AFTER the previous operation finishes. Native
    # fullscreen transitions can block several seconds; absolute timestamps
    # must not cause request/check pairs to run together in one frame.
    actions = [
        (0.5, restore_initial_window),
        (0.7, lambda: capture("menu")),
        (0.5, lambda: app.messenger.send("enter")),
        (5.8, pause),
        (1.0, resume),
        (1.0, minimize),
        (1.0, restore),
        (1.0, after_restore),
        (2.0, fullscreen),
        (1.0, check_fullscreen),
        (1.0, windowed),
        (1.0, check_windowed),
        (1.0, classic),
        (5.0, result_fixture),
        (1.0, lambda: resize(960, 720)),
        (1.0, capture_narrow),
        (1.0, lambda: resize(960, 540)),
        (1.0, lambda: capture("menu-960x540")),
        (1.0, lambda: resize(1280, 720)),
        (1.0, lambda: feedback_fixture("blocked", "request-blocked-1280x720")),
        (1.0, lambda: feedback_fixture("accepted", "request-accepted")),
        (1.0, lambda: feedback_fixture("cancelled", "request-cancelled")),
        (1.0, lambda: resize(960, 720)),
        (1.0, lambda: feedback_fixture("blocked", "request-blocked-960x720")),
        (1.0, lambda: resize(960, 540)),
        (1.0, lambda: feedback_fixture("blocked", "request-blocked-960x540")),
        (1.0, lambda: feedback_fixture("ready", "request-ready")),
        (1.0, lambda: feedback_fixture("empty", "request-no-target")),
        (1.0, lambda: feedback_fixture("close", "request-too-close")),
    ]

    def exercise(task):
        nonlocal next_action, last_action
        try:
            if app.mode == "escort" and app.state == "playing" and app.model.cooldown <= 0:
                if any(150 < car["z"] < 400 and car["state"] == "cruising" for car in app.model.cars):
                    app.messenger.send("h")
            if next_action == len(actions):
                app.taskMgr.stop()
                return task.done
            delay, action = actions[next_action]
            if time.perf_counter() - last_action >= delay:
                action()
                next_action += 1
                last_action = time.perf_counter()
        except Exception as error:
            state["failure"] = repr(error)
            app.taskMgr.stop()
            return task.done
        return task.cont

    app.taskMgr.add(exercise, "native-acceptance", sort=40)
    try:
        app.run()
    finally:
        report = dict(native_window=True, no_save=True, muted=True,
                      human_playtest=False, result_screen_is_synthetic_fixture=True,
                      request_screens_are_synthetic_fixtures=True,
                      elapsed_seconds=time.monotonic() - started,
                      checks=checks, observations=state, failure=state.get("failure"))
        (output / "native-acceptance.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        app.destroy()
    return 0 if not state.get("failure") else 1


if __name__ == "__main__":
    raise SystemExit(main())




