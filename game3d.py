"""Speed Highway — procedural low-poly 3D edition."""
import argparse, json, math, random, time
from pathlib import Path
from panda3d.core import CardMaker, AmbientLight, DirectionalLight, Fog, Filename, NodePath, TextNode, TransparencyAttrib, WindowProperties, loadPrcFileData
from direct.gui.DirectGui import DirectButton, DirectFrame
from direct.gui.OnscreenText import OnscreenText
from direct.showbase.ShowBase import ShowBase
from platform_support import chinese_font, save_directory
MAX_SPEED, SAVE_DIR = 220.0, save_directory()
VEHICLES=(
 {'id':'scarlet','name':'极速跑车','shape':'racer','color':(238,91,66),'accent':(255,215,116)}, {'id':'azure','name':'巡航轿跑','shape':'coupe','color':(52,170,222),'accent':(184,239,255)}, {'id':'trail','name':'方盒越野','shape':'suv','color':(91,182,114),'accent':(238,231,172)}, {'id':'amber','name':'复古肌肉','shape':'muscle','color':(244,164,61),'accent':(255,232,185)}, {'id':'violet','name':'城市掀背','shape':'hatch','color':(176,103,216),'accent':(242,207,255)}, {'id':'cargo','name':'重载皮卡','shape':'truck','color':(77,202,191),'accent':(202,255,242)},)
class Model:
 def __init__(self,seed=None):
  self.rng=random.Random(seed);self.x=self.speed=self.distance=self.elapsed=self.invulnerable=0.;self.life,self.passed,self.spawn_timer=3,0,0.;self.cars=[];self.dead=False
 @property
 def score(self):return int(self.distance/5)+self.passed*150
 @property
 def difficulty(self):return min(1.,self.elapsed/180)
 def update(self,dt,steer=0,gas=False,brake=False):
  if self.dead:return False
  self.elapsed+=dt;self.invulnerable=max(0,self.invulnerable-dt);target=65 if brake else (MAX_SPEED if gas else 180)
  if abs(self.x)>1:target=min(target,75)
  delta=(115 if brake or abs(self.x)>1 else 45)*dt;self.speed+=max(-delta,min(delta,target-self.speed));self.x=max(-1.18,min(1.18,self.x+steer*1.35*dt*self.speed/180));self.distance+=self.speed*dt;self.spawn_timer-=dt
  if self.spawn_timer<=0:
   lanes=self.rng.sample([-.66,0,.66],2 if self.rng.random()<self.difficulty*.65 else 1)
   for lane in lanes:self.cars.append({'z':1700.,'x':lane,'speed':65+self.difficulty*35,'vehicle':self.rng.choice(VEHICLES),'hit':False})
   self.spawn_timer=3.5-self.difficulty*1.4
  collision=False
  for car in self.cars:
   old,car['z']=car['z'],car['z']-(self.speed-car['speed'])*dt
   if min(old,car['z'])<=20 and max(old,car['z'])>=-25 and abs(car['x']-self.x)<.25 and not car['hit'] and self.invulnerable<=0:
    self.life-=1;self.speed*=.45;self.invulnerable=2.;car['hit']=True;collision=True
   if car['z']<-45 and not car.get('counted'):
    car['counted']=True
    if not car['hit']:self.passed+=1
  self.cars=[c for c in self.cars if -100<c['z']<2300];self.dead=self.life<=0;return collision
class Game3D(ShowBase):
 STEP,COUNT,SCALE=38.,62,18.
 def __init__(self,args):
  self.args=args;loadPrcFileData('','window-title 极速公路 · SPEED HIGHWAY 3D\nwin-size 1280 720\nframebuffer-multisample 1\nmultisamples 4\n')
  if args.smoke:loadPrcFileData('','window-type offscreen\naudio-library-name null\n')
  super().__init__();self.disableMouse();self.font=self.loader.loadFont(Filename.fromOsSpecific(str(Path(__file__).resolve().parent/'assets'/'NotoSansCJKsc-Regular.otf')).getFullpath());self.best,self.muted,self.vehicle_index=0,False,0
  if not args.smoke:
   try:
    saved=json.loads((SAVE_DIR/'save.json').read_text('utf-8'));self.best=max(0,int(saved.get('best',0)));self.muted=bool(saved.get('muted',False));self.vehicle_index=int(saved.get('vehicle',0))%len(VEHICLES)
   except (OSError,ValueError,TypeError,AttributeError):pass
  self.model=Model(42 if args.smoke else None);self.state='menu';self.keys=set();self.traffic={};self.started=self.last=time.monotonic();self.frames=0;self.fullscreen=False;self.world();self.ui();self.events();self.taskMgr.add(self.tick,'tick')
  if args.smoke:self.action('start')
 def save(self):
  if self.args.smoke:return
  try:
   SAVE_DIR.mkdir(parents=True,exist_ok=True);t=SAVE_DIR/'save.tmp';t.write_text(json.dumps({'best':self.best,'muted':self.muted,'vehicle':self.vehicle_index}),encoding='utf-8');t.replace(SAVE_DIR/'save.json')
  except OSError:pass
 def cube(self,parent,pos=(0,0,0),scale=(1,1,1),color=(1,1,1,1),hpr=(0,0,0)):
  n=self.loader.loadModel('models/box');n.reparentTo(parent);n.setPos(*pos);n.setScale(*scale);n.setColor(*color);n.setTextureOff(1);n.setHpr(*hpr);return n
 def world(self):
  self.setBackgroundColor(.31,.64,.76,1);fog=Fog('fog');fog.setColor(.31,.64,.76);fog.setExpDensity(.006);self.render.setFog(fog);a=AmbientLight('ambient');a.setColor((.55,.62,.68,1));self.render.setLight(self.render.attachNewNode(a));sun=DirectionalLight('sun');sun.setColor((1,.91,.72,1));sun.setShadowCaster(True,1024,1024);sn=self.render.attachNewNode(sun);sn.setHpr(-35,-55,0);self.render.setLight(sn);self.render.setShaderAuto();cm=CardMaker('grass');cm.setFrame(-220,220,-80,320);grass=self.render.attachNewNode(cm.generate());grass.setP(-90);grass.setColor(.22,.48,.25,1);grass.setTextureOff(1)
  for i in range(18):self.cube(self.render,(-120+i*14,185+i%3*9,5),(12,12,5+i%4*2),(.18,.38,.38,1),(0,0,45))
  self.road=[]
  for _ in range(self.COUNT):
   p=NodePath('road');p.reparentTo(self.render);self.cube(p,scale=(8.7,self.STEP/self.SCALE,.12),color=(.13,.16,.19,1))
   for x in (-9.,9.):self.cube(p,(x,0,.03),(.22,self.STEP/self.SCALE,.05),(.85,.20,.13,1))
   for x in (-2.85,2.85):self.cube(p,(x,0,.04),(.07,self.STEP/self.SCALE*.68,.025),(.92,.86,.61,1))
   self.road.append(p)
  self.props=[self.tree() for _ in range(40)];self.player=self.car(VEHICLES[self.vehicle_index],'player');self.player.reparentTo(self.render);self.camera.setPos(0,-13,6.7);self.camera.lookAt(0,10,.2)
 def tree(self):
  n=NodePath('tree');n.reparentTo(self.render);self.cube(n,scale=(.2,.2,1),pos=(0,0,.8),color=(.27,.16,.08,1));self.cube(n,scale=(1.1,1.1,2.2),pos=(0,0,2.3),color=(.04,.30,.18,1),hpr=(0,0,45));return n
 def car(self,v,name):
  n=NodePath(name);c=tuple(x/255 for x in v['color'])+(1,);a=tuple(x/255 for x in v['accent'])+(1,);shape=v['shape'];ln={'racer':2.25,'coupe':2.4,'suv':2.45,'muscle':2.5,'hatch':2.15,'truck':2.8}[shape];self.cube(n,scale=(1.15,ln,.32),pos=(0,0,.52),color=c);self.cube(n,scale=(.76,ln*.42,.30 if shape in ('suv','truck') else .24),pos=(0,-.06,.88),color=(.05,.12,.16,1));self.cube(n,scale=(.18,.18,.06),pos=(0,-ln*.75,.65),color=a)
  if shape=='truck':self.cube(n,scale=(1.05,.78,.32),pos=(0,.76,.84),color=c)
  if shape=='muscle':self.cube(n,scale=(.45,.5,.10),pos=(0,-.45,1.18),color=a)
  ws=[]
  for x in (-1.18,1.18):
   for y in (-ln*.58,ln*.58):ws.append(self.cube(n,scale=(.17,.30,.30),pos=(x,y,.35),color=(.025,.03,.035,1)))
  s=self.cube(n,scale=(1.35,ln*.9,.015),pos=(0,0,.04),color=(.02,.03,.025,.42));s.setTransparency(TransparencyAttrib.MAlpha);n.setPythonTag('wheels',ws);return n
 def rx(self,d):return math.sin(d/2100)*16+math.sin(d/4300)*8
 def pose(self,d,lane=0):
  b=self.model.distance;return self.rx(d)-self.rx(b)+lane*8.,(d-b)/self.SCALE,math.degrees(math.atan2((self.rx(d+10)-self.rx(d-10))/20,1))-math.degrees(math.atan2((self.rx(b+10)-self.rx(b-10))/20,1))
 def label(self,t,pos,scale=.05,parent=None,align=TextNode.ACenter):return OnscreenText(t,pos=pos,scale=scale,font=self.font,align=align,parent=parent,mayChange=True)
 def ui(self):
  self.hud=DirectFrame(frameColor=(.03,.08,.1,.87),frameSize=(-1.25,1.25,-.12,.12),pos=(0,0,.88));self.hudtext=self.label('',(-1.15,.89),.052,self.hud,TextNode.ALeft);self.tip=self.label('',(0,-.88),.042);self.panel=DirectFrame(frameColor=(.03,.09,.11,.90),frameSize=(-.62,.62,-.68,.68),relief=1);self.title=self.label('',(0,.43),.085,self.panel);self.info=self.label('',(0,.17),.042,self.panel);self.pick=self.label('',(0,-.07),.048,self.panel);style={'text_font':self.font,'text_scale':.05,'frameColor':(.16,.30,.34,1),'text_fg':(.94,.96,.90,1),'relief':1};self.left=DirectButton(text='←',command=lambda:self.action('prev'),pos=(-.43,0,-.20),scale=.09,**style);self.right=DirectButton(text='→',command=lambda:self.action('next'),pos=(.43,0,-.20),scale=.09,**style);self.primary=DirectButton(pos=(0,0,-.36),scale=.075,frameColor=(.92,.64,.18,1),text_fg=(.05,.11,.13,1),text_font=self.font,relief=1);self.secondary=DirectButton(pos=(0,0,-.53),scale=.06,**style);self.refresh()
 def events(self):
  for k in ('arrow_left','arrow_right','arrow_up','arrow_down','w','a','s','d'):self.accept(k,self.keys.add,[k]);self.accept(k+'-up',self.keys.discard,[k])
  self.accept('escape',self.pause);self.accept('m',self.mute);self.accept('f11',self.full);self.accept('f',self.full);self.accept('enter',self.confirm);self.accept('space',self.confirm)
 def pause(self):self.state='paused' if self.state=='playing' else ('playing' if self.state=='paused' else 'menu');self.keys.clear();self.refresh()
 def mute(self):self.muted=not self.muted;self.save();self.refresh()
 def full(self):self.fullscreen=not self.fullscreen;p=WindowProperties();p.setFullscreen(self.fullscreen);self.win.requestProperties(p)
 def confirm(self):
  if self.state!='playing':self.action('resume' if self.state=='paused' else 'start')
 def action(self,a):
  if a in ('start','menu','quit'):self.best=max(self.best,self.model.score);self.save()
  if a=='start':self.model=Model(42 if self.args.smoke else None);self.state='playing'
  elif a=='resume':self.state='playing'
  elif a=='menu':self.state='menu'
  elif a=='quit':self.userExit()
  elif a in ('prev','next'):
   self.vehicle_index=(self.vehicle_index+(-1 if a=='prev' else 1))%len(VEHICLES);self.player.removeNode();self.player=self.car(VEHICLES[self.vehicle_index],'player');self.player.reparentTo(self.render);self.save()
  self.refresh()
 def refresh(self):
  active=self.state=='playing';self.hud.show() if active else self.hud.hide();self.panel.hide() if active else self.panel.show();self.tip.setText('方向键 / WASD 驾驶    ESC 暂停    M '+('开启声音' if self.muted else '静音'));self.left.show() if self.state=='menu' else self.left.hide();self.right.show() if self.state=='menu' else self.right.hide()
  if self.state=='menu':self.title.setText('极速公路');self.info.setText('低多边形 3D 公路 · 无限超车挑战\n方向键 / WASD 转向、加速和刹车\n自动加速 · 三次碰撞结束 · 超车 +150');self.pick.setText('车型库  '+VEHICLES[self.vehicle_index]['name']);self.primary['text']='开始挑战';self.primary['command']=lambda:self.action('start');self.secondary['text']='退出游戏';self.secondary['command']=lambda:self.action('quit')
  elif self.state=='paused':self.title.setText('稍作停留');self.info.setText('呼吸一下，再向前出发。\nF11 全屏 · M 静音 · ESC 继续');self.pick.setText('');self.primary['text']='继续驾驶';self.primary['command']=lambda:self.action('resume');self.secondary['text']='返回首页';self.secondary['command']=lambda:self.action('menu')
  else:self.title.setText('本次旅程结束');self.info.setText(f'{self.model.score:06d}\n超车 {self.model.passed} 辆 · 行驶 {self.model.distance/1000:.2f} km');self.pick.setText(f'最高纪录 {self.best:06d}');self.primary['text']='再跑一次';self.primary['command']=lambda:self.action('start');self.secondary['text']='返回首页';self.secondary['command']=lambda:self.action('menu')
 def scene(self,dt):
  b=self.model.distance
  for i,p in enumerate(self.road):x,y,h=self.pose(b+i*self.STEP);p.setPos(x,y,0);p.setH(h)
  for i,t in enumerate(self.props):x,y,h=self.pose(b+(i%20)*110+80,(-1 if i%2 else 1)*1.45);t.setPos(x,y,0);t.setH(h)
  x,y,h=self.pose(b,self.model.x);self.player.setPos(x,y,.12);self.player.setH(h+(dt*18 if self.state=='menu' else 0));self.player.setR(-self.model.x*5);self.player.setAlphaScale(.42 if self.model.invulnerable and int(self.model.invulnerable*12)%2 else 1)
  for w in self.player.getPythonTag('wheels'):w.setP(w.getP()+self.model.speed*dt*4)
  live=set()
  for c in self.model.cars:
   if c['z']<0:continue
   k=id(c);live.add(k);n=self.traffic.get(k)
   if not n:n=self.car(c['vehicle'],'traffic');n.reparentTo(self.render);self.traffic[k]=n
   x,y,h=self.pose(b+c['z'],c['x']);n.setPos(x,y,.1);n.setH(h)
   for w in n.getPythonTag('wheels'):w.setP(w.getP()+c['speed']*dt*4)
  for k in set(self.traffic)-live:self.traffic.pop(k).removeNode()
  self.camera.setPos(self.player.getX()*.35,-13,6.7);self.camera.lookAt(self.player.getX()*.25,11,.15)
 def tick(self,task):
  now=time.monotonic();dt=min(now-self.last,.1);self.last=now
  if self.state=='playing':
   steer=int(bool({'arrow_right','d'}&self.keys))-int(bool({'arrow_left','a'}&self.keys));gas=bool({'arrow_up','w'}&self.keys) or bool(self.args.smoke);brake=bool({'arrow_down','s'}&self.keys);self.model.update(dt,steer,gas,brake)
   if self.model.dead:self.best=max(self.best,self.model.score);self.save();self.state='over';self.refresh()
  self.scene(dt);self.hudtext.setText(f'极速公路     {int(self.model.speed):03d} km/h     分数 {self.model.score:06d}     生命 '+('● '*self.model.life)+f'    最高 {self.best}');self.frames+=1
  if self.args.screenshot and self.frames==90:self.win.saveScreenshot(Filename(self.args.screenshot))
  if self.args.smoke and now-self.started>=self.args.smoke:
   if self.args.report:
    p=Path(self.args.report);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps({'seconds':now-self.started,'frames':self.frames,'average_fps':self.frames/(now-self.started),'score':self.model.score,'life':self.model.life}),encoding='utf-8')
   raise SystemExit(0)
  return task.cont
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--smoke',type=float,default=0);p.add_argument('--screenshot');p.add_argument('--report');Game3D(p.parse_args()).run()








