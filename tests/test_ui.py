import argparse
from collections import defaultdict
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pygame as pg
import game


class InterfaceTests(unittest.TestCase):
    def test_menus_display_events_and_save(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(game, 'SAVE_DIR', Path(folder)):
            args=argparse.Namespace(smoke=0,screenshot=None,report=None)
            app=game.Game(args)
            app.draw()
            pg.image.save(app.canvas,'menu.png')
            self.assertEqual(len(app.buttons),2)
            app.action('start')
            self.assertEqual(app.state,'playing')
            app.model.distance=5000
            app.action('menu')
            self.assertEqual(app.best,1000)
            app.action('start')
            self.assertEqual(app.model.life,3)
            app.state='paused'
            app.draw()
            self.assertEqual(len(app.buttons),3)
            pg.image.save(app.canvas,'pause.png')
            app.action('resume')
            self.assertEqual(app.state,'playing')
            app.screen=pg.display.set_mode((960,540),pg.RESIZABLE)
            app.draw()
            self.assertEqual(app.viewport.size,(960,540))
            # Drive real event handling one frame at a time without sleeping.
            steps=iter([
                [pg.event.Event(pg.KEYDOWN,key=pg.K_ESCAPE)],
                [pg.event.Event(pg.KEYDOWN,key=pg.K_ESCAPE)],
                [pg.event.Event(pg.KEYDOWN,key=pg.K_F11)],
                [pg.event.Event(pg.KEYDOWN,key=pg.K_F11)],
                [pg.event.Event(pg.KEYDOWN,key=pg.K_m)],
                [pg.event.Event(pg.WINDOWFOCUSLOST)],
                [pg.event.Event(pg.MOUSEBUTTONDOWN,button=1,pos=(640,497))],
                [pg.event.Event(pg.QUIT)],
            ])
            states=[]
            original_draw=app.draw
            def draw():
                original_draw()
                states.append((app.state,app.fullscreen,app.model.elapsed))
            app.draw=draw
            with patch.object(pg.event,'get',side_effect=lambda:next(steps)), patch.object(pg.key,'get_pressed',return_value=defaultdict(bool)):
                app.run()
            self.assertEqual(states[0][0],'paused')
            self.assertEqual(states[0][2],0)
            self.assertEqual(states[1][0],'playing')
            self.assertTrue(states[2][1])
            self.assertFalse(states[3][1])
            self.assertEqual(states[5][0],'paused')
            self.assertEqual(states[6][0],'playing')
            self.assertTrue(app.muted)
            restored=game.Game(args)
            self.assertEqual(restored.best,1000)
            self.assertTrue(restored.muted)
            restored.state='over'
            restored.draw()
            pg.image.save(restored.canvas,'results.png')
            pg.quit()
            (Path(folder)/'save.json').write_text('{broken',encoding='utf-8')
            recovered=game.Game(args)
            self.assertEqual(recovered.best,0)
            recovered.draw()
            pg.quit()


if __name__=='__main__': unittest.main()
