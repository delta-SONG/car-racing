# 极速公路 · Speed Highway

Windows 离线复古赛车，所有图形和音效均由程序生成。

macOS 适配与打包步骤见 `macos/README.md`。本机 Windows EXE 已交付；DMG 需要在 Mac 或 macOS CI 上执行打包后生成。

## 开始游戏

双击 `dist\SpeedHighway.exe`，点击“开始挑战”或按回车。无需 Python 或网络。

| 按键 | 功能 |
| --- | --- |
| ← → / A D | 转向 |
| ↑ / W | 加速至 220 km/h |
| ↓ / S | 刹车 |
| Esc | 暂停 / 继续 |
| F11 | 全屏 / 窗口 |
| M | 静音 / 恢复声音 |
| Enter / 空格 | 开始 / 重试 / 继续 |

车辆会自动加速至 180 km/h。驶出公路会减速。每次碰撞扣一条生命并提供两秒保护，三条生命耗尽结束。距离每 5 米得 1 分，成功超车得 150 分。前三分钟车流逐渐增加，每组车流至少留出一条车道。失去窗口焦点自动暂停。

松开左右方向键后保持当前车道位置，弯道不会自动把小车推向路边。

最高分与静音设置保存在 `%LOCALAPPDATA%\SpeedHighway\save.json`。存档损坏时使用默认设置，无法写入时仍可继续游玩。中文字体使用 Windows 自带微软雅黑，未复制或分发系统字体。

## 从源码运行与构建

在项目目录使用 PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe game.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\build.ps1
```

自动驾驶运行检查（不读取或改写玩家存档）：

```powershell
.\dist\SpeedHighway.exe --smoke 600 --report soak-report.json --screenshot gameplay.png
```

使用固定随机种子控制测试车流；自动驾驶与正常游玩共用更新和绘制逻辑。声音设备不可用时游戏可无声运行。
