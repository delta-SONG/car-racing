from pathlib import Path
import unittest

import pygame as pg
from platform_support import chinese_font, save_directory


class PlatformTests(unittest.TestCase):
    def test_macos_save_location(self):
        home = Path('/Users/player')
        self.assertEqual(save_directory('darwin', home, {'LOCALAPPDATA': '/wrong'}),
                         home / 'Library' / 'Application Support' / 'SpeedHighway')

    def test_windows_save_location_is_preserved(self):
        self.assertEqual(save_directory('win32', '/player', {'LOCALAPPDATA': '/local'}),
                         Path('/local') / 'SpeedHighway')

    def test_bundled_font_is_independent_of_working_directory(self):
        root = Path(__file__).resolve().parents[1]
        font_path = chinese_font('darwin', root)
        self.assertEqual(font_path, str(root / 'assets' / 'NotoSansCJKsc-Regular.otf'))
        pg.font.init()
        font = pg.font.Font(font_path, 24)
        self.assertTrue(all(metric is not None for metric in font.metrics('极速公路开始挑战生命最高纪录●')))
        self.assertGreater(font.render('极速公路', True, 'white').get_width(), 50)


if __name__ == '__main__':
    unittest.main()
