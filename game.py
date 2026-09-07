"""Speed Highway — offline, procedural arcade racer."""
import argparse
import array
from collections import OrderedDict
import json
import math
from pathlib import Path
import random
import sys
import time

import pygame as pg
from platform_support import chinese_font, save_directory

W, H = 1280, 720
MAX_SPEED = 220.0
SAVE_DIR = save_directory()
VEHICLES = (
    {'id': 'scarlet', 'name': '极速跑车', 'shape': 'racer', 'color': (238, 91, 66), 'accent': (255, 215, 116)},
    {'id': 'azure', 'name': '巡航轿跑', 'shape': 'coupe', 'color': (52, 170, 222), 'accent': (184, 239, 255)},
    {'id': 'trail', 'name': '方盒越野', 'shape': 'suv', 'color': (91, 182, 114), 'accent': (238, 231, 172)},
    {'id': 'amber', 'name': '复古肌肉', 'shape': 'muscle', 'color': (244, 164, 61), 'accent': (255, 232, 185)},
    {'id': 'violet', 'name': '城市掀背', 'shape': 'hatch', 'color': (176, 103, 216), 'accent': (242, 207, 255)},
    {'id': 'cargo', 'name': '重载皮卡', 'shape': 'truck', 'color': (77, 202, 191), 'accent': (202, 255, 242)},
)


class Model:
    def __init__(self, seed=None):
        self.rng = random.Random(seed)
        self.x = self.speed = self.distance = self.elapsed = self.invulnerable = 0.0
        self.life, self.passed, self.spawn_timer = 3, 0, 0.0
        self.cars = []
        self.dead = False

    @property
    def score(self):
        return int(self.distance / 5) + self.passed * 150

    @property
    def difficulty(self):
        return min(1.0, self.elapsed / 180)

    @property
    def curve(self):
        return math.sin(self.distance / 2100) * .65 + math.sin(self.distance / 4300) * .3

    def update(self, dt, steer=0, gas=False, brake=False):
        if self.dead:
            return False
        self.elapsed += dt
        self.invulnerable = max(0, self.invulnerable - dt)
        target = 65 if brake else (MAX_SPEED if gas else 180)
        if abs(self.x) > 1:
            target = min(target, 75)
        change = (115 if brake or abs(self.x) > 1 else 45) * dt
        self.speed += max(-change, min(change, target - self.speed))
        # The arcade car follows its lane through bends unless the player steers.
        self.x += steer * 1.35 * dt * self.speed / 180
        self.x = max(-1.18, min(1.18, self.x))
        self.distance += self.speed * dt
        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            lanes = self.rng.sample([-.66, 0, .66], 2 if self.rng.random() < self.difficulty * .65 else 1)
            velocity = 65 + self.difficulty * 35
            for lane in lanes:
                self.cars.append({'z': 1700.0, 'x': lane, 'speed': velocity,
                                  'vehicle': self.rng.choice(VEHICLES), 'hit': False})
            self.spawn_timer = 3.5 - self.difficulty * 1.4
        collision = False
        for car in self.cars:
            old_z = car['z']
            car['z'] -= (self.speed - car['speed']) * dt
            if min(old_z, car['z']) <= 20 and max(old_z, car['z']) >= -25 and abs(car['x'] - self.x) < .25:
                if not car['hit'] and self.invulnerable <= 0:
                    self.life -= 1
                    self.speed *= .45
                    self.invulnerable = 2.0
                    car['hit'] = True
                    collision = True
            if car['z'] < -45 and not car.get('counted'):
                car['counted'] = True
                if not car['hit']:
                    self.passed += 1
        self.cars = [c for c in self.cars if -100 < c['z'] < 2300]
        self.dead = self.life <= 0
        return collision


class Game:
    def __init__(self, args):
        pg.mixer.pre_init(22050, -16, 1, 512)
        pg.init()
        self.args = args
        self.screen = pg.display.set_mode((W, H), pg.RESIZABLE)
        pg.display.set_caption('极速公路 · SPEED HIGHWAY')
        self.canvas = pg.Surface((W, H))
        self.fonts = {}
        self.text_cache = OrderedDict()
        self.font_path = chinese_font()
        self.best, self.muted, self.vehicle_index = 0, False, 0
        if not args.smoke:
            try:
                saved = json.loads((SAVE_DIR / 'save.json').read_text('utf-8'))
                self.best = max(0, int(saved.get('best', 0)))
                self.muted = bool(saved.get('muted', False))
                self.vehicle_index = int(saved.get('vehicle', 0)) % len(VEHICLES)
            except (OSError, ValueError, TypeError, AttributeError):
                pass
        self.model = Model(42 if args.smoke else None)
        self.state, self.fullscreen = 'menu', False
        self.buttons = []
        self.audio = {}
        if pg.mixer.get_init():
            for name, frequency, duration in [('engine', 65, 1), ('click', 660, .09), ('crash', 90, .3)]:
                samples = array.array('h')
                for i in range(int(22050 * duration)):
                    envelope = 1 if name == 'engine' else 1 - i / (22050 * duration)
                    wave = math.sin(2 * math.pi * frequency * i / 22050)
                    if name == 'crash':
                        wave *= random.uniform(-1, 1)
                    samples.append(int(2200 * envelope * wave))
                self.audio[name] = pg.mixer.Sound(buffer=samples)
            self.channel = self.audio['engine'].play(-1)
        self.running = True

    def save(self):
        if self.args.smoke:
            return
        try:
            SAVE_DIR.mkdir(parents=True, exist_ok=True)
            temporary = SAVE_DIR / 'save.tmp'
            temporary.write_text(json.dumps({'best': self.best, 'muted': self.muted,
                                             'vehicle': self.vehicle_index}), encoding='utf-8')
            temporary.replace(SAVE_DIR / 'save.json')
        except OSError:
            pass

    def sound(self, name):
        if not self.muted and name in self.audio:
            self.audio[name].play()

    def text(self, value, x, y, size=24, color=(240, 247, 240), center=False):
        if size not in self.fonts:
            self.fonts[size] = pg.font.Font(self.font_path, size)
        cache_key = (str(value), size, tuple(color))
        surface = self.text_cache.get(cache_key)
        if surface is None:
            surface = self.fonts[size].render(str(value), True, color)
            self.text_cache[cache_key] = surface
            if len(self.text_cache) > 128:
                self.text_cache.popitem(last=False)
        else:
            self.text_cache.move_to_end(cache_key)
        self.canvas.blit(surface, surface.get_rect(center=(x, y)) if center else (x, y))

    def project(self, z, lane=0):
        scale = 240 / (240 + max(0, z))
        bend = self.model.curve * 380 * (1 - scale) ** 2
        center = W / 2 + bend - self.model.x * 70 * (1 - scale)
        return center + lane * 540 * scale, 245 + 490 * scale, 540 * scale

    def car(self, x, y, width, vehicle, player=False):
        width = max(8, int(width))
        shape, color, accent = vehicle['shape'], vehicle['color'], vehicle['accent']
        height = int(width * {'racer': 1.4, 'coupe': 1.32, 'suv': 1.25,
                              'muscle': 1.18, 'hatch': 1.28, 'truck': 1.08}[shape])
        x, y = int(x), int(y)
        pg.draw.ellipse(self.canvas, (25, 39, 38), (x-width*.62, y-12, width*1.24, 22))
        body = pg.Rect(x-width//2, y-height, width, height)
        for side in [-1, 1]:
            tire_height = .54 if shape == 'truck' else .7
            pg.draw.rect(self.canvas, (18, 27, 36), (x+side*width*.48-width*.1, y-height*.76, width*.2, height*tire_height), border_radius=max(1,width//15))
        pg.draw.rect(self.canvas, color, body, border_radius=max(2, width//7))
        if shape == 'truck':
            pg.draw.rect(self.canvas, (31, 65, 78), (x-width*.37, y-height*.77, width*.74, height*.30), border_radius=max(1, width//12))
            pg.draw.rect(self.canvas, accent, (x-width*.28, y-height*.94, width*.56, height*.12))
        elif shape == 'suv':
            pg.draw.polygon(self.canvas, (26, 65, 77), [(x-width*.32,y-height*.79),(x+width*.32,y-height*.79),(x+width*.38,y-height*.36),(x-width*.38,y-height*.36)])
            pg.draw.rect(self.canvas, accent, (x-width*.33,y-height*.93,width*.66,height*.1))
        elif shape == 'muscle':
            pg.draw.rect(self.canvas, (43, 57, 66), (x-width*.34, y-height*.65, width*.68, height*.25), border_radius=max(1, width//16))
            pg.draw.rect(self.canvas, accent, (x-width*.15,y-height*.92,width*.3,height*.16))
        elif shape == 'hatch':
            pg.draw.polygon(self.canvas, (24, 55, 72), [(x-width*.29,y-height*.79),(x+width*.29,y-height*.79),(x+width*.38,y-height*.39),(x-width*.39,y-height*.39)])
            pg.draw.rect(self.canvas, accent, (x-width*.12,y-height*.94,width*.24,height*.15))
        else:
            pg.draw.polygon(self.canvas, (24, 55, 72), [(x-width*.32,y-height*.76),(x+width*.32,y-height*.76),(x+width*.39,y-height*.4),(x-width*.39,y-height*.4)])
            pg.draw.rect(self.canvas, accent, (x-width*.08,y-height*.96,width*.16,height*.18))
        pg.draw.rect(self.canvas, (255, 232, 174), (x-width*.34,y-height*.12,width*.2,height*.055))
        pg.draw.rect(self.canvas, (255, 232, 174), (x+width*.14,y-height*.12,width*.2,height*.055))
        if player:
            pg.draw.rect(self.canvas, (30, 39, 47), (x-width*.55,y-height*.23,width*1.1,8), border_radius=3)

    def scenery(self):
        c = self.canvas
        for y in range(0, 280, 4):
            t = y / 280
            pg.draw.rect(c, (int(83+67*t), int(177+36*t), int(205+15*t)), (0,y,W,4))
        pg.draw.circle(c, (255, 225, 147), (1030, 110), 46)
        shift = int(self.model.curve * 65)
        pg.draw.polygon(c, (105, 153, 155), [(-100,280),(100+shift,130),(270,245),(480+shift,95),(690,246),(920+shift,150),(1370,280)])
        pg.draw.polygon(c, (58, 125, 116), [(0,275),(180,215),(345,267),(680,190),(920,255),(1150,205),(1280,265),(1280,310),(0,310)])
        pg.draw.rect(c, (80, 151, 93), (0, 270, W, H-270))
        for z in range(3000, 0, -25):
            x1,y1,r1 = self.project(z)
            x2,y2,r2 = self.project(z-25)
            band = int((self.model.distance + z)/120) % 2
            pg.draw.polygon(c, (76,145,87) if band else (84,155,93), [(0,y1),(W,y1),(W,y2),(0,y2)])
            pg.draw.polygon(c, (243,230,191) if band else (211,84,65), [(x1-r1*1.07,y1),(x1+r1*1.07,y1),(x2+r2*1.07,y2),(x2-r2*1.07,y2)])
            pg.draw.polygon(c, (58,69,76) if band else (61,72,79), [(x1-r1,y1),(x1+r1,y1),(x2+r2,y2),(x2-r2,y2)])
            if band:
                for lane in [-1/3,1/3]:
                    pg.draw.polygon(c, (222,227,211), [(x1+r1*(lane-.008),y1),(x1+r1*(lane+.008),y1),(x2+r2*(lane+.008),y2),(x2+r2*(lane-.008),y2)])
        for i in range(24,0,-1):
            z = i*145 - self.model.distance % 145
            for side in [-1,1]:
                x,y,r = self.project(z,side*1.3)
                size = r*.18
                pg.draw.rect(c,(107,85,57),(x-size*.1,y-size*.4,size*.2,size*.5))
                pg.draw.polygon(c,(25,100,77),[(x,y-size*2.2),(x-size*.65,y-size*.3),(x+size*.65,y-size*.3)])
        for car in sorted(self.model.cars,key=lambda a:a['z'],reverse=True):
            if car['z'] >= 0:
                x,y,r = self.project(car['z'],car['x'])
                self.car(x,y,r*.20,car['vehicle'])
        if self.model.invulnerable <= 0 or int(self.model.invulnerable*12)%2:
            px, py, _ = self.project(24, self.model.x)
            self.car(px,py,108,VEHICLES[self.vehicle_index],True)

    def button(self, label, rect, action, primary=False):
        r = pg.Rect(rect)
        pg.draw.rect(self.canvas,(238,180,72) if primary else (46,69,76),r,border_radius=12)
        self.text(label,r.centerx,r.centery,24,(25,42,47) if primary else (237,242,231),True)
        self.buttons.append((r,action))

    def draw(self):
        self.buttons = []
        self.scenery()
        if self.state == 'playing':
            pg.draw.rect(self.canvas,(23,43,49),(28,24,1224,86),border_radius=14)
            self.text('极速公路',52,40,27)
            self.text(f'{int(self.model.speed):03d}',278,30,38,(255,203,103))
            self.text('km/h',363,55,16)
            self.text(f'分数  {self.model.score:06d}',474,43,25)
            self.text('生命  '+'● '*self.model.life,786,43,24,(255,135,108))
            self.text(f'最高  {self.best}',1040,47,20)
            self.text('方向键 / WASD 驾驶    ESC 暂停    M '+('开启声音' if self.muted else '静音'),38,685,17)
            if abs(self.model.x)>1:
                self.text('驶回公路！',640,155,30,(255,225,153),True)
        else:
            shade = pg.Surface((W,H),pg.SRCALPHA)
            shade.fill((8,25,33,170))
            self.canvas.blit(shade,(0,0))
            pg.draw.rect(self.canvas,(23,43,49),(340,105,600,535),border_radius=24)
            self.text('S P E E D   H I G H W A Y',640,150,20,(238,180,72),True)
            title = {'menu':'极速公路','paused':'稍作停留','over':'本次旅程结束'}[self.state]
            self.text(title,640,219,52,center=True)
            if self.state == 'menu':
                self.text('复古公路 · 无限超车挑战',640,282,22,center=True)
                self.text('方向键 / WASD 转向、加速和刹车',640,333,21,center=True)
                self.text('自动加速 · 三次碰撞结束 · 超车 +150',640,370,20,center=True)
                selected = VEHICLES[self.vehicle_index]
                self.text(f'车型库  {selected["name"]}',640,415,23,(238,180,72),True)
                self.car(640,478,72,selected,True)
            elif self.state == 'over':
                self.text(f'{self.model.score:06d}',640,305,54,(238,180,72),True)
                self.text(f'超车 {self.model.passed} 辆  ·  行驶 {self.model.distance/1000:.2f} km',640,369,23,center=True)
                self.text(f'最高纪录 {self.best:06d}',640,419,22,center=True)
            else:
                self.text('呼吸一下，再向前出发。',640,310,25,center=True)
                self.text('F / F11 全屏  ·  M 静音  ·  ESC 继续',640,375,21,center=True)
            if self.state == 'menu':
                self.button('‹',(394,440,70,52),'vehicle_prev')
                self.button('›',(816,440,70,52),'vehicle_next')
                self.button('开始挑战',(415,510,450,58),'start',True)
                self.button('退出游戏',(415,578,450,42),'quit')
            else:
                self.button('继续驾驶' if self.state=='paused' else '再跑一次',(415,468,450,58),'resume' if self.state=='paused' else 'start',True)
                if self.state=='paused':
                    self.button('重新开始',(415,543,215,50),'start')
                    self.button('返回首页',(650,543,215,50),'menu')
                else:
                    self.button('返回首页',(415,543,450,50),'menu')
        sw,sh=self.screen.get_size()
        scale=min(sw/W,sh/H)
        size=(max(1,int(W*scale)),max(1,int(H*scale)))
        self.viewport=pg.Rect((sw-size[0])//2,(sh-size[1])//2,*size)
        self.screen.fill((10,23,30))
        frame = self.canvas if size == (W, H) else pg.transform.smoothscale(self.canvas,size)
        self.screen.blit(frame,self.viewport)
        pg.display.flip()

    def action(self, action):
        self.sound('click')
        if action in ('start', 'menu', 'quit'):
            self.best=max(self.best,self.model.score)
            self.save()
        if action=='start':
            self.model=Model(42 if self.args.smoke else None)
            self.state='playing'
        elif action=='resume': self.state='playing'
        elif action=='menu': self.state='menu'
        elif action=='quit': self.running=False
        elif action in ('vehicle_prev', 'vehicle_next'):
            self.vehicle_index = (self.vehicle_index + (-1 if action == 'vehicle_prev' else 1)) % len(VEHICLES)
            self.save()

    def run(self):
        started=time.monotonic()
        last_frame=time.perf_counter()
        frames=0
        if self.args.smoke: self.action('start')
        while self.running:
            # macOS can coalesce both SDL and Python sleeps to ~40 ms.
            # Use a precise wait only while driving; menus and pause still sleep.
            wait_for=1/60-(time.perf_counter()-last_frame)
            if wait_for>0:
                if sys.platform=='darwin' and self.state=='playing':
                    deadline=last_frame+1/60
                    while time.perf_counter()<deadline:
                        pass
                else:
                    time.sleep(wait_for)
            frame_now=time.perf_counter()
            dt=min(frame_now-last_frame,.1)
            last_frame=frame_now
            for event in pg.event.get():
                if event.type==pg.QUIT: self.running=False
                elif event.type==pg.WINDOWFOCUSLOST and self.state=='playing' and not self.args.smoke: self.state='paused'
                elif event.type==pg.KEYDOWN:
                    if event.key in (pg.K_F11, pg.K_f):
                        self.fullscreen=not self.fullscreen
                        self.screen=pg.display.set_mode((0,0) if self.fullscreen else (W,H),pg.FULLSCREEN if self.fullscreen else pg.RESIZABLE)
                    elif event.key==pg.K_m:
                        self.muted=not self.muted
                        self.save()
                    elif event.key==pg.K_ESCAPE:
                        if self.state=='playing': self.state='paused'
                        elif self.state=='paused': self.state='playing'
                        else: self.state='menu'
                    elif event.key in (pg.K_RETURN,pg.K_SPACE) and self.state!='playing':
                        self.action('resume' if self.state=='paused' else 'start')
                    elif self.state == 'menu' and event.key in (pg.K_LEFT, pg.K_a, pg.K_RIGHT, pg.K_d):
                        self.action('vehicle_prev' if event.key in (pg.K_LEFT, pg.K_a) else 'vehicle_next')
                elif event.type==pg.MOUSEBUTTONDOWN and event.button==1 and hasattr(self,'viewport'):
                    mx=(event.pos[0]-self.viewport.x)*W/self.viewport.width
                    my=(event.pos[1]-self.viewport.y)*H/self.viewport.height
                    for rect,action in self.buttons:
                        if rect.collidepoint(mx,my):
                            self.action(action)
                            break
            if self.state=='playing':
                keys=pg.key.get_pressed()
                steer=int(keys[pg.K_RIGHT] or keys[pg.K_d])-int(keys[pg.K_LEFT] or keys[pg.K_a])
                gas=keys[pg.K_UP] or keys[pg.K_w]
                brake=keys[pg.K_DOWN] or keys[pg.K_s]
                if self.args.smoke:
                    danger=[c for c in self.model.cars if 0<c['z']<400]
                    lanes=[-.66,0,.66]
                    target=min(lanes,key=lambda x:sum(1/(max(20,c['z'])) for c in danger if abs(c['x']-x)<.3)+abs(x-self.model.x)*.0001)
                    steer=max(-1,min(1,(target-self.model.x)*5))
                    gas=True
                if self.model.update(dt,steer,gas,brake): self.sound('crash')
                if self.model.dead:
                    self.best=max(self.best,self.model.score)
                    self.save()
                    self.state='over'
                    if self.args.smoke: self.action('start')
            if hasattr(self,'channel') and self.channel:
                self.channel.set_volume(0 if self.muted or self.state!='playing' else .12+self.model.speed/MAX_SPEED*.35)
            self.draw()
            frames+=1
            if self.args.screenshot and frames==120:
                pg.image.save(self.canvas,self.args.screenshot)
            if self.args.smoke and time.monotonic()-started>=self.args.smoke:
                if self.args.report:
                    report_path = Path(self.args.report)
                    report_path.parent.mkdir(parents=True, exist_ok=True)
                    report_path.write_text(json.dumps({'seconds':time.monotonic()-started,'frames':frames,'average_fps':frames/(time.monotonic()-started),'score':self.model.score,'life':self.model.life}),encoding='utf-8')
                self.running=False
        self.best=max(self.best,self.model.score)
        self.save()
        pg.quit()


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--smoke',type=float,default=0,help='Run an automated driving soak test for N seconds')
    parser.add_argument('--screenshot')
    parser.add_argument('--report')
    Game(parser.parse_args()).run()
