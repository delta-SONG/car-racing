# 极速公路 · Speed Highway

**版本：v2.0.0（待验收的 Release 草稿）**。这是继 v1.0.0 后的新版本；正式发布须完成最终 EXE 的真实窗口验收。

离线赛车项目，包含 Pygame 经典版本、Panda3D 经典模式和处于试玩阶段的领航模式。

## 领航试验

在 90 秒内带领后方护送车通过直线路段。按 **H** 请求前方车辆在邻道安全时让行，观察反馈并通过控速保持队形。方向键或 WASD 驾驶；Esc 暂停，Enter 开始或重试，Tab 在菜单切换模式，C 在菜单切换路况。

该模式为可调整的设计假设。本分支为本地预览开发版，尚未完成最终 Windows EXE 的真实窗口性能、交互与真人试玩验收，不代表正式发布。经典模式与领航评分保持隔离。

## 从源码运行（Windows）

安装 Python 3.11 后，在 PowerShell 中执行：

```powershell
.\setup_dev.ps1
.\.venv-dev\Scripts\python.exe macos\prepare_assets.py
.\.venv-dev\Scripts\python.exe escort_launcher.py
```

字体文件不存入仓库；上面的准备脚本会下载指定版本并校验 SHA-256。依赖安装与准备字体需要网络；完成准备后游戏离线运行。运行经典模式可用 `game3d.py --mode classic`；Pygame 版入口为 `game.py`。

```powershell
.\.venv-dev\Scripts\python.exe -B -m unittest discover -s tests -v
.\build_escort.ps1
```

Windows 测试包、临时环境、构建结果和本地报告不纳入仓库。2026-11-02 的本地源码通过 61 项回归；100 秒 EXE 自动离屏验证通过，离屏 FPS 不代表真实窗口性能。macOS 领航版本仍待实际设备验证。

## 资源许可

Kenney Input Prompts 按键图标采用 CC0，来源与校验值见 `assets/ui/sources.json`。Noto Sans CJK SC 字体采用 SIL OFL 1.1，来源与哈希见 `assets/SOURCES.md`。除明确列出的资源许可外，不应假定项目源码已有许可。
