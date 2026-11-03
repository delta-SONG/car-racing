"""Classic 3D rules extracted unchanged from the pre-escort game."""
import random
MAX_SPEED = 220.0

VEHICLES = ({'id': 'scarlet', 'name': '极速跑车', 'shape': 'racer', 'color': (238, 91, 66), 'accent': (255, 215, 116)}, {'id': 'azure', 'name': '巡航轿跑', 'shape': 'coupe', 'color': (52, 170, 222), 'accent': (184, 239, 255)}, {'id': 'trail', 'name': '方盒越野', 'shape': 'suv', 'color': (91, 182, 114), 'accent': (238, 231, 172)}, {'id': 'amber', 'name': '复古肌肉', 'shape': 'muscle', 'color': (244, 164, 61), 'accent': (255, 232, 185)}, {'id': 'violet', 'name': '城市掀背', 'shape': 'hatch', 'color': (176, 103, 216), 'accent': (242, 207, 255)}, {'id': 'cargo', 'name': '重载皮卡', 'shape': 'truck', 'color': (77, 202, 191), 'accent': (202, 255, 242)})

class Model:

    def __init__(self, seed=None):
        self.rng = random.Random(seed)
        self.x = self.speed = self.distance = self.elapsed = self.invulnerable = 0.0
        self.life, self.passed, self.spawn_timer = (3, 0, 0.0)
        self.cars = []
        self.dead = False

    @property
    def score(self):
        return int(self.distance / 5) + self.passed * 150

    @property
    def difficulty(self):
        return min(1.0, self.elapsed / 180)

    def update(self, dt, steer=0, gas=False, brake=False):
        if self.dead:
            return False
        self.elapsed += dt
        self.invulnerable = max(0, self.invulnerable - dt)
        target = 65 if brake else MAX_SPEED if gas else 180
        if abs(self.x) > 1:
            target = min(target, 75)
        delta = (115 if brake or abs(self.x) > 1 else 45) * dt
        self.speed += max(-delta, min(delta, target - self.speed))
        self.x = max(-1.18, min(1.18, self.x + steer * 1.35 * dt * self.speed / 180))
        self.distance += self.speed * dt
        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            lanes = self.rng.sample([-0.66, 0, 0.66], 2 if self.rng.random() < self.difficulty * 0.65 else 1)
            for lane in lanes:
                self.cars.append({'z': 1700.0, 'x': lane, 'speed': 65 + self.difficulty * 35, 'vehicle': self.rng.choice(VEHICLES), 'hit': False})
            self.spawn_timer = 3.5 - self.difficulty * 1.4
        collision = False
        for car in self.cars:
            old, car['z'] = (car['z'], car['z'] - (self.speed - car['speed']) * dt)
            if min(old, car['z']) <= 20 and max(old, car['z']) >= -25 and (abs(car['x'] - self.x) < 0.25) and (not car['hit']) and (self.invulnerable <= 0):
                self.life -= 1
                self.speed *= 0.45
                self.invulnerable = 2.0
                car['hit'] = True
                collision = True
            if car['z'] < -45 and (not car.get('counted')):
                car['counted'] = True
                if not car['hit']:
                    self.passed += 1
        self.cars = [c for c in self.cars if -100 < c['z'] < 2300]
        self.dead = self.life <= 0
        return collision
