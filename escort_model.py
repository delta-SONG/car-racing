"""Deterministic, renderer-independent prototype of cooperative highway escort.

Distances use the existing game's arcade road units, not physical metres.
"""

from collections import deque
import math
import random


LANES = (-0.66, 0.0, 0.66)


class EscortModel:
    duration = 90.0
    route_length = 10000.0
    request_range = 460.0
    request_cooldown = 3.0
    reaction_delay = 0.8
    lane_change_seconds = 1.4
    ideal_gap = 140.0
    max_gap = 540.0

    def __init__(self, seed=42, vehicles=(), scenario="open"):
        if scenario not in ("open", "staggered", "blocked"):
            raise ValueError("Unknown escort scenario")
        self.rng = random.Random(seed)
        self._accumulator = 0.0
        self.scenario = scenario
        self.x = self.distance = self.elapsed = self.invulnerable = 0.0
        self.speed = 160.0
        self.life = 3
        self.passed = 0
        self.dead = self.success = False
        self.reason = ""
        self.escort_x = 0.0
        self.escort_distance = -self.ideal_gap
        self.escort_speed = 150.0
        self.escort_life = 3
        self.escort_invulnerable = 0.0
        self.detached_seconds = 0.0
        self.cooldown = 0.0
        self.requests = self.yields = self.collisions = 0
        self.feedback = "先靠近前方同车道慢车"
        self.feedback_hint = "按 H 请求；S / ↓ 减速等队伍"
        self.feedback_kind = "info"
        self.feedback_seconds = 4.0
        self.path = deque([(-self.ideal_gap, 0.0), (0.0, 0.0)])
        self.cars = []
        for index, position in enumerate(range(650, 14000, 1500)):
            lane = 0.0 if scenario != "staggered" else LANES[index % 3]
            vehicle = vehicles[index % len(vehicles)] if vehicles else None
            self.cars.append(self.make_car(position, lane, 95.0, vehicle))
        if scenario == "blocked":
            vehicle = vehicles[0] if vehicles else None
            self.cars.extend([self.make_car(650, -0.66, 110, vehicle),
                              self.make_car(650, 0.66, 125, vehicle)])

    @staticmethod
    def make_car(distance, lane, speed=95.0, vehicle=None):
        return dict(distance=float(distance), x=float(lane), z=float(distance),
                    speed=float(speed), vehicle=vehicle, hit=False,
                    escort_hit=False, counted=False, state="cruising",
                    origin=float(lane), target=float(lane), phase=0.0,
                    requested=False)

    @property
    def gap(self):
        return self.distance - self.escort_distance

    @property
    def remaining(self):
        return max(0.0, self.duration - self.elapsed)

    @property
    def progress(self):
        return max(0.0, min(1.0, self.escort_distance / self.route_length))

    @property
    def score(self):
        return max(0, int(self.progress * 1000) + self.yields * 50
                   - self.collisions * 200
                   + (int(self.remaining) * 10 if self.success else 0))

    def message(self, text, seconds=3.5, *, hint="", kind="info"):
        self.feedback, self.feedback_seconds = text, seconds
        self.feedback_hint, self.feedback_kind = hint, kind

    @property
    def passage_feedback(self):
        """Readable status and action hint; querying it never changes simulation."""
        if self.feedback_seconds > 0:
            return self.feedback, self.feedback_hint, self.feedback_kind
        if any(car["state"] in ("responding", "changing")
               and -100 <= car["distance"] - self.distance <= self.request_range
               for car in self.cars):
            return ("慢车正在让行", "保持间距，等慢车完全让开", "accepted")
        return ("观察前方同车道慢车", "按 H 请求；S / ↓ 减速等空隙", "info")

    @property
    def team_feedback(self):
        """Read-only team guidance; the existing gap and grace rules still decide loss."""
        if self.detached_seconds > 0:
            remaining = max(0.0, 5.0 - self.detached_seconds)
            return f"脱队 {remaining:.1f}s", "S / ↓ 减速等候", "danger"
        if self.gap > self.max_gap * 0.5:
            return "队距拉大", "S / ↓ 减速等候", "warning"
        return "队距良好", "保持队形，一起前进", "info"

    def _safe_lane(self, actor, lane):
        """Reserve the entire swept corridor, including delayed changes.

        Project the start and end of a manoeuvre to reject cars approaching
        from behind as well as those already occupying the target lane.
        """
        left, right = sorted((actor["x"], lane))
        horizon = self.reaction_delay + self.lane_change_seconds
        if actor["state"] == "responding":
            horizon -= min(self.reaction_delay, actor["phase"])
        elif actor["state"] == "changing":
            horizon = (1 - actor["phase"]) * self.lane_change_seconds
        for other in self.cars:
            if other is actor:
                continue
            occupied = [other["x"]]
            if other["state"] in ("responding", "changing"):
                occupied += [other["origin"], other["target"]]
            if max(occupied) < left - 0.25 or min(occupied) > right + 0.25:
                continue
            gap = other["distance"] - actor["distance"]
            future_gap = gap + (other["speed"] - actor["speed"]) * horizon
            if min(gap, future_gap) < 180 and max(gap, future_gap) > -180:
                return False
        for x, distance, speed in ((self.x, self.distance, self.speed),
                                   (self.escort_x, self.escort_distance,
                                    self.escort_speed)):
            if left - 0.25 <= x <= right + 0.25:
                gap = distance - actor["distance"]
                future_gap = gap + (speed - actor["speed"]) * horizon
                if min(gap, future_gap) < 95 and max(gap, future_gap) > -95:
                    return False
        return True

    def request_passage(self):
        if self.dead:
            return False
        if self.cooldown > 0:
            # The HUD already shows a live countdown. Repeated H presses must
            # not erase a refusal reason, acknowledgement, or collision alert.
            return False
        candidates = [car for car in self.cars
                      if 100 <= car["distance"] - self.distance <= self.request_range
                      and abs(car["x"] - self.x) < 0.3
                      and car["state"] == "cruising"
                      and not car["requested"]]
        if not candidates:
            if any(car["state"] in ("responding", "changing")
                   and -100 <= car["distance"] - self.distance <= self.request_range
                   for car in self.cars):
                self.message("慢车正在让行", hint="保持间距，等慢车完全让开", kind="accepted")
            elif any(0 <= car["distance"] - self.distance < 100
                     and abs(car["x"] - self.x) < 0.3
                     and car["state"] == "cruising" and not car["requested"]
                     for car in self.cars):
                self.message("距离过近，暂不能请求", hint="先减速拉开距离，再按 H", kind="warning")
            else:
                self.message("暂时没有可响应车辆", hint="靠近前方同车道慢车，再按 H")
            return False
        actor = min(candidates, key=lambda car: car["distance"])
        self.cooldown = self.request_cooldown
        self.requests += 1
        lane_index = min(range(3), key=lambda i: abs(LANES[i] - actor["x"]))
        neighbours = [LANES[i] for i in (lane_index - 1, lane_index + 1)
                      if 0 <= i < len(LANES)]
        for lane in neighbours:
            if self._safe_lane(actor, lane):
                actor.update(state="responding", origin=actor["x"],
                             target=lane, phase=0.0, requested=True)
                self.message("请求已收到 · 慢车准备让行",
                             hint="先保持间距，等慢车完全让开", kind="accepted")
                return True
        self.message("邻道占用或有来车 · 暂不能让行",
                     hint="按住 S / ↓ 减速，等空隙再按 H", kind="warning")
        return False

    @staticmethod
    def _approach(value, target, step):
        return value + max(-step, min(step, target - value))

    def _path_x(self, distance):
        while len(self.path) > 2 and self.path[1][0] < distance:
            self.path.popleft()
        previous, following = self.path[0], self.path[1]
        span = following[0] - previous[0]
        blend = max(0.0, min(1.0, (distance - previous[0]) / max(span, 0.001)))
        return previous[1] + (following[1] - previous[1]) * blend

    def update(self, dt, steer=0.0, gas=False, brake=False):
        if not math.isfinite(dt) or dt < 0:
            raise ValueError("dt must be a finite non-negative number")
        if self.dead:
            return False
        collision = False
        self._accumulator += dt
        step = 1 / 120
        while self._accumulator + 1e-10 >= step and not self.dead:
            collision = self._step(step, steer, gas, brake) or collision
            self._accumulator = max(0.0, self._accumulator - step)
        return collision

    def _step(self, dt, steer, gas, brake):
        self.elapsed += dt
        self.invulnerable = max(0.0, self.invulnerable - dt)
        self.escort_invulnerable = max(0.0, self.escort_invulnerable - dt)
        self.cooldown = max(0.0, self.cooldown - dt)
        self.feedback_seconds = max(0.0, self.feedback_seconds - dt)
        target = 65.0 if brake else (220.0 if gas else 180.0)
        if abs(self.x) > 1:
            target = min(target, 75.0)
        self.speed = self._approach(self.speed, target,
                                    (115 if brake or abs(self.x) > 1 else 45) * dt)
        self.x = max(-1.18, min(1.18, self.x + steer * 1.35 * dt * self.speed / 180))
        previous_player = self.distance
        self.distance += self.speed * dt
        self.path.append((self.distance, self.x))
        # Avoid storing one point per high-FPS frame for the entire journey.
        if len(self.path) > 3 and self.path[-1][0] - self.path[-3][0] < 5:
            newest = self.path.pop()
            self.path.pop()
            self.path.append(newest)

        collision = False
        for car in self.cars:
            old_distance = car["distance"]
            car["distance"] += car["speed"] * dt
            if car["state"] == "responding":
                car["phase"] += dt
                if car["phase"] >= self.reaction_delay:
                    if self._safe_lane(car, car["target"]):
                        car.update(state="changing", phase=0.0)
                    else:
                        car.update(state="cruising", phase=0.0, requested=False)
                        self.message("空隙已变化 · 让行取消",
                                     hint="先减速保持间距，等空隙再请求", kind="warning")
            elif car["state"] == "changing":
                if self._safe_lane(car, car["target"]):
                    car["phase"] = min(1.0, car["phase"] + dt / self.lane_change_seconds)
                    blend = car["phase"] ** 2 * (3 - 2 * car["phase"])
                    car["x"] = car["origin"] + (car["target"] - car["origin"]) * blend
                    if car["phase"] >= 1:
                        car.update(state="yielded", x=car["target"])
                        self.yields += 1
                        self.message("通道已打开 · 带队通过",
                                     hint="留意队距，别甩开后方护送车", kind="accepted")
                elif self.feedback_seconds <= 0:
                    # Do not refresh this every simulation step: doing so can
                    # hide a collision warning from later in the previous step.
                    self.message("让行车等待安全空隙",
                                 hint="按住 S / ↓ 减速，保持间距", kind="warning")
            old_z = old_distance - previous_player
            car["z"] = car["distance"] - self.distance
            if (min(old_z, car["z"]) <= 45 and max(old_z, car["z"]) >= -45
                    and abs(car["x"] - self.x) < 0.28
                    and not car["hit"] and self.invulnerable <= 0):
                car["hit"] = True
                self.life -= 1
                self.collisions += 1
                self.speed *= 0.45
                self.invulnerable = 2.0
                collision = True
                self.message("领航车碰撞 · 注意队距",
                             hint="减速重新组织队伍；两秒碰撞保护", kind="danger")
            if car["z"] < -60 and not car["counted"]:
                car["counted"] = True
                self.passed += 1

        previous_escort = self.escort_distance
        desired_x = self._path_x(self.escort_distance + 20)
        self.escort_x = self._approach(self.escort_x, desired_x,
                                       1.35 * dt * self.escort_speed / 180)
        desired_speed = max(0.0, min(180.0, self.speed + (self.gap - self.ideal_gap) * 0.6))
        desired_speed = min(desired_speed, max(0.0, (self.gap - 60) / 0.6))
        for car in self.cars:
            gap = car["distance"] - self.escort_distance
            if 0 < gap < 260 and abs(car["x"] - self.escort_x) < 0.32:
                desired_speed = min(desired_speed, max(0.0, car["speed"] + (gap - 130) * 0.8))
        if abs(self.escort_x) > 1:
            desired_speed = min(desired_speed, 75.0)
        self.escort_speed = self._approach(self.escort_speed, desired_speed,
                                          (130 if desired_speed < self.escort_speed else 45) * dt)
        self.escort_distance = min(self.distance - 60,
                                   self.escort_distance + self.escort_speed * dt)
        for car in self.cars:
            old_gap = car["distance"] - car["speed"] * dt - previous_escort
            gap = car["distance"] - self.escort_distance
            if (min(old_gap, gap) <= 45 and max(old_gap, gap) >= -45
                    and abs(car["x"] - self.escort_x) < 0.28
                    and not car["escort_hit"] and self.escort_invulnerable <= 0):
                car["escort_hit"] = True
                self.escort_life -= 1
                self.collisions += 1
                self.escort_invulnerable = 2.0
                self.escort_speed *= 0.45
                collision = True
                self.message("护送车受损 · 请留出空间",
                             hint="减速等队伍，留意护送车生命", kind="danger")
        self.detached_seconds = self.detached_seconds + dt if self.gap > self.max_gap else 0.0
        if self.life <= 0:
            self.reason = "领航车损坏"
        elif self.escort_life <= 0:
            self.reason = "护送车损坏"
        elif self.detached_seconds >= 5:
            self.reason = "队伍脱节：持续加速甩开了护送车"
        elif self.escort_distance >= self.route_length:
            self.success, self.reason = True, "全队抵达"
        elif self.elapsed >= self.duration:
            self.reason = "时间用尽：护送车尚未抵达"
        self.dead = bool(self.reason)
        return collision

    def autopilot(self):
        """A disclosed reproducible smoke controller, never human playtest evidence."""
        if self.cooldown <= 0 and any(
                100 <= car["distance"] - self.distance <= self.request_range
                and abs(car["x"] - self.x) < 0.3
                and car["state"] == "cruising" for car in self.cars):
            self.request_passage()
        return 0.0, False, self.gap > self.ideal_gap + 35
