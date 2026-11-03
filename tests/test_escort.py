import unittest

from escort_model import EscortModel


class EscortTests(unittest.TestCase):
    def model_with_car(self, position=400):
        model = EscortModel()
        model.cars = [model.make_car(position, 0)]
        return model

    def test_request_has_range_and_requires_same_lane(self):
        model = self.model_with_car(700)
        self.assertFalse(model.request_passage())
        self.assertEqual(model.cooldown, 0)
        model.cars[0]["distance"] = 400
        model.x = 0.66
        self.assertFalse(model.request_passage())

    def test_signal_waits_then_changes_lane_continuously(self):
        model = self.model_with_car()
        self.assertTrue(model.request_passage())
        model.update(0.4)
        self.assertEqual(model.cars[0]["x"], 0)
        model.update(0.6)
        self.assertLess(model.cars[0]["x"], 0)
        self.assertGreater(model.cars[0]["x"], -0.66)
        model.update(1.3)
        self.assertEqual(model.cars[0]["x"], -0.66)
        self.assertEqual(model.yields, 1)
        model.update(1)
        self.assertEqual(model.yields, 1)

    def test_busy_adjacent_lanes_refuse_without_teleporting(self):
        model = self.model_with_car()
        model.cars.extend([model.make_car(400, lane) for lane in (-0.66, 0.66)])
        self.assertFalse(model.request_passage())
        self.assertIn("占用", model.feedback)
        self.assertEqual(model.cars[0]["state"], "cruising")
        self.assertEqual(model.cars[0]["x"], 0)

    def test_fast_approaching_car_blocks_both_target_lanes(self):
        model = self.model_with_car()
        model.cars.extend([model.make_car(100, lane, 260) for lane in (-0.66, 0.66)])
        self.assertFalse(model.request_passage())

    def test_delay_rechecks_space_when_another_car_arrives(self):
        model = self.model_with_car()
        self.assertTrue(model.request_passage())
        model.cars.append(model.make_car(400, -0.66))
        model.update(0.9)
        self.assertEqual(model.cars[0]["state"], "cruising")
        self.assertEqual(model.cars[0]["x"], 0)
        self.assertEqual(model.yields, 0)

    def test_reservations_prevent_two_cars_using_same_gap(self):
        model = self.model_with_car()
        self.assertTrue(model.request_passage())
        other = model.make_car(400, -0.66)
        model.cars.append(other)
        self.assertFalse(model._safe_lane(other, 0))

    def test_signal_cooldown_does_not_duplicate_responses(self):
        model = self.model_with_car()
        self.assertTrue(model.request_passage())
        self.assertFalse(model.request_passage())
        self.assertEqual(model.requests, 1)

    def test_repeated_signal_preserves_refusal_and_does_not_extend_cooldown(self):
        model = self.model_with_car()
        model.cars.extend([model.make_car(400, lane) for lane in (-0.66, 0.66)])
        self.assertFalse(model.request_passage())
        refusal = model.passage_feedback
        self.assertEqual(refusal[2], "warning")
        self.assertIn("减速", refusal[1])
        model.update(0.25, brake=True)
        remaining = model.cooldown
        for _ in range(10):
            self.assertFalse(model.request_passage())
        self.assertEqual(model.passage_feedback, refusal)
        self.assertEqual(model.cooldown, remaining)
        self.assertEqual(model.requests, 1)
        self.assertEqual(model.yields, 0)

    def test_refused_request_can_retry_after_cooldown_when_gap_opens(self):
        model = self.model_with_car()
        model.cars.extend([model.make_car(400, lane) for lane in (-0.66, 0.66)])
        self.assertFalse(model.request_passage())
        model.update(3.01, brake=True)
        self.assertFalse(model.dead)
        model.cars = model.cars[:1]
        self.assertTrue(model.request_passage())
        self.assertEqual(model.requests, 2)
        self.assertEqual(model.passage_feedback[2], "accepted")

    def test_too_close_request_explains_distance_without_spending_cooldown(self):
        model = self.model_with_car(80)
        self.assertFalse(model.request_passage())
        self.assertIn("距离过近", model.passage_feedback[0])
        self.assertIn("减速", model.passage_feedback[1])
        self.assertEqual((model.requests, model.cooldown), (0, 0))

    def test_cancelled_response_explains_why_and_preserves_safety(self):
        model = self.model_with_car()
        self.assertTrue(model.request_passage())
        model.cars.append(model.make_car(400, -0.66))
        model.update(0.9)
        self.assertIn("取消", model.passage_feedback[0])
        self.assertEqual(model.passage_feedback[2], "warning")
        self.assertIn("减速", model.passage_feedback[1])
        self.assertEqual(model.cars[0]["x"], 0)
        before = model.passage_feedback
        self.assertFalse(model.request_passage())
        self.assertEqual(model.passage_feedback, before)

    def test_waiting_traffic_does_not_erase_collision_alert(self):
        model = self.model_with_car()
        actor = model.cars[0]
        actor.update(state="changing", target=-0.66, requested=True)
        model.cars.append(model.make_car(400, -0.66))
        model.cars.append(model.make_car(20, 0))
        model.update(1 / 60)
        self.assertIn("碰撞", model.passage_feedback[0])
        self.assertEqual(model.passage_feedback[2], "danger")
        model.update(0.5, brake=True)
        self.assertIn("碰撞", model.passage_feedback[0])
        self.assertEqual(model.passage_feedback[2], "danger")

    def test_expired_message_retains_in_progress_guidance_without_mutation(self):
        model = self.model_with_car()
        self.assertTrue(model.request_passage())
        model.feedback_seconds = 0
        model.cooldown = 0
        before = dict(model.cars[0])
        self.assertEqual(model.passage_feedback[2], "accepted")
        self.assertIn("让行", model.passage_feedback[0])
        self.assertFalse(model.request_passage())
        self.assertIn("让行", model.feedback)
        self.assertEqual(model.cars[0], before)
        self.assertEqual(model.requests, 1)

    def test_restart_discards_previous_refusal_and_guidance(self):
        model = self.model_with_car(80)
        model.request_passage()
        model = EscortModel()
        self.assertEqual(model.passage_feedback[2], "info")
        self.assertNotIn("过近", model.passage_feedback[0])
        self.assertEqual((model.cooldown, model.requests), (0, 0))

    def test_follower_never_overtakes_braking_leader(self):
        model = self.model_with_car()
        model.cars.clear()
        for _ in range(600):
            model.update(1 / 60, brake=True)
            self.assertGreaterEqual(model.gap, 60 - 1e-6)
            self.assertLessEqual(model.escort_distance, model.distance)

    def test_escort_brakes_for_traffic_in_its_path(self):
        model = self.model_with_car(-20)
        model.x = 0.66
        model.update(0.2)
        self.assertLess(model.escort_speed, 150)

    def test_always_accelerating_can_lose_the_team(self):
        model = EscortModel()
        model.cars.clear()
        for _ in range(1800):
            model.update(1 / 60, gas=True)
        self.assertTrue(model.dead)
        self.assertFalse(model.success)
        self.assertIn("脱节", model.reason)

    def test_timeout_is_failure_even_if_player_remains_alive(self):
        model = EscortModel()
        model.cars.clear()
        model.elapsed = 89.99
        model.update(0.1, brake=True)
        self.assertTrue(model.dead)
        self.assertFalse(model.success)
        self.assertIn("时间", model.reason)

    def test_smoke_controller_completes_open_scenario(self):
        model = EscortModel()
        while not model.dead:
            model.update(1 / 60, *model.autopilot())
        self.assertTrue(model.success, model.reason)
        self.assertGreaterEqual(model.yields, 3)
        self.assertGreaterEqual(model.progress, 1)
        self.assertEqual(model.life, 3)
        self.assertEqual(model.escort_life, 3)

    def test_finished_mission_is_frozen_and_restart_is_clean(self):
        model = EscortModel()
        model.escort_distance = model.route_length
        model.distance = model.route_length + model.ideal_gap
        model.update(0.1)
        self.assertTrue(model.success)
        elapsed, score = model.elapsed, model.score
        model.update(3, gas=True)
        self.assertEqual((model.elapsed, model.score), (elapsed, score))
        fresh = EscortModel()
        self.assertFalse(fresh.dead)
        self.assertEqual((fresh.requests, fresh.yields), (0, 0))

    def test_frame_rates_have_consistent_unobstructed_progress(self):
        distances = []
        for fps in (30, 60, 144):
            model = EscortModel()
            model.cars.clear()
            for _ in range(fps * 10):
                model.update(1 / fps)
            distances.append(model.escort_distance)
        self.assertLess(max(distances) - min(distances), 1)

    def test_team_guidance_uses_existing_warning_and_loss_boundaries(self):
        model = EscortModel()
        for gap, kind in ((140, "info"), (270, "info"), (270.01, "warning"),
                          (540, "warning")):
            model.escort_distance = model.distance - gap
            self.assertEqual(model.team_feedback[2], kind)
        model.detached_seconds = 1.25
        self.assertEqual(model.team_feedback, ("脱队 3.8s", "S / ↓ 减速等候", "danger"))
        model.detached_seconds = 5.5
        self.assertEqual(model.team_feedback[0], "脱队 0.0s")

    def test_reading_team_guidance_does_not_change_traffic_or_signal(self):
        import copy
        model = EscortModel(scenario="blocked")
        model.request_passage()
        before = copy.deepcopy(model.__dict__)
        rng_before = model.rng.getstate()
        for _ in range(30):
            model.team_feedback
        for key, value in before.items():
            if key != "rng":
                self.assertEqual(model.__dict__[key], value, key)
        self.assertEqual(model.rng.getstate(), rng_before)

    def test_braking_recovers_from_detachment_before_deadline(self):
        model = EscortModel()
        model.cars.clear()
        while model.detached_seconds < 0.5 and not model.dead:
            model.update(1 / 60, gas=True)
        self.assertEqual(model.team_feedback[2], "danger")
        for _ in range(8 * 60):
            model.update(1 / 60, brake=True)
            if model.team_feedback[2] == "info":
                break
        self.assertFalse(model.dead, model.reason)
        self.assertEqual(model.detached_seconds, 0)
        self.assertEqual(model.team_feedback[2], "info")

    def test_invalid_time_step_is_rejected(self):
        for dt in (-1, float("inf"), float("nan")):
            with self.assertRaises(ValueError):
                EscortModel().update(dt)

    def test_blocked_scenario_rewards_waiting_for_a_gap(self):
        results = []
        for wait in (False, True):
            model = EscortModel(scenario="blocked")
            while not model.dead:
                steer, gas, brake = model.autopilot()
                if wait and model.elapsed < 10:
                    brake = True
                model.update(1 / 60, steer, gas, brake)
            results.append(model)
        self.assertFalse(results[0].success)
        self.assertTrue(results[1].success)
        self.assertEqual(results[1].collisions, 0)
        self.assertGreater(results[1].score, results[0].score)

    def test_follower_also_slows_down_when_off_the_road(self):
        from collections import deque
        model = EscortModel()
        model.cars.clear()
        model.x = model.escort_x = 1.1
        model.path = deque([(-140, 1.1), (0, 1.1)])
        model.update(2)
        self.assertLessEqual(model.escort_speed, 75)


if __name__ == "__main__":
    unittest.main()
