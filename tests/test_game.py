import unittest
from game import Model


class ModelTests(unittest.TestCase):
    def test_frame_rate(self):
        results=[]
        for fps in [30,60,144]:
            m=Model(1)
            m.spawn_timer=9999
            for _ in range(fps*20):
                m.update(1/fps,steer=m.curve*.12/1.35,gas=True)
            results.append((m.speed,m.distance))
        self.assertLess(max(r[1] for r in results)-min(r[1] for r in results),6)
        self.assertTrue(all(r[0]==220 for r in results))

    def test_collision_and_immunity(self):
        m=Model(1)
        m.speed=180
        m.cars=[dict(z=10,x=0,speed=70,hit=False) for _ in range(2)]
        self.assertTrue(m.update(.01))
        self.assertEqual(m.life,2)
        self.assertEqual(m.invulnerable,2)
        self.assertFalse(m.update(.01))
        self.assertEqual(m.life,2)

    def test_death_and_restart(self):
        m=Model(1)
        m.life=1
        m.cars=[dict(z=0,x=0,speed=0,hit=False)]
        m.update(.01)
        self.assertTrue(m.dead)
        elapsed=m.elapsed
        m.update(1)
        self.assertEqual(m.elapsed,elapsed)
        self.assertEqual(Model().life,3)

    def test_overtake(self):
        m=Model(1)
        m.speed=180
        m.cars=[dict(z=-44,x=.66,speed=0,hit=False)]
        m.update(.1)
        self.assertEqual(m.passed,1)
        m.update(.1)
        self.assertEqual(m.passed,1)

    def test_offroad_and_difficulty(self):
        m=Model(1)
        m.x=1.4
        m.speed=220
        m.update(.5)
        self.assertLess(m.speed,220)
        m.elapsed=999
        self.assertEqual(m.difficulty,1)
        for _ in range(20):
            m.cars=[]
            m.spawn_timer=0
            m.update(.01)
            self.assertLessEqual(len(m.cars),2)
            self.assertEqual(len({c['x'] for c in m.cars}),len(m.cars))


if __name__=='__main__': unittest.main()
