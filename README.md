# 极速公路 · Speed Highway

一款使用 Python 制作、可离线游玩的单人赛车小游戏。当前版本采用 Panda3D 构建低多边形三维公路、车辆、树木和远山，并保留基于 Pygame 的经典 2D 版本。

玩家可以从六种外观不同的车型中选择赛车，在不断弯曲的三车道公路上躲避随机车流、持续超车并刷新本地最高分。所有车型使用相同的速度和碰撞规则。

## 游戏特色

- 车后方跟随视角与低多边形 3D 场景
- 六种玩家车型，赛道车辆也会随机采用不同车型
- 自动加速、手动加速与刹车
- 三点生命和两秒碰撞保护
- 随时间增加的车流密度与速度
- 暂停、全屏、静音设置和立即重试
- 本地保存最高分、静音状态和所选车型
- Windows、Apple Silicon Mac 和 Intel Mac 构建流程
- 游戏运行时无需联网，也不要求安装 Python

## 下载与安装

### macOS

打开 [Build macOS DMG 工作流](https://github.com/delta-SONG/car-racing/actions/workflows/macos-dmg.yml?query=branch%3Acodex%2Fmacos-dmg)，选择一次成功的构建，在页面底部的 **Artifacts** 中下载适合电脑的压缩包：

| Mac 类型 | Artifact | DMG |
| --- | --- | --- |
| Apple 芯片（M1、M2、M3、M4 等） | `SpeedHighway-macOS-arm64` | `SpeedHighway-macOS-arm64.dmg` |
| Intel 芯片 | `SpeedHighway-macOS-x86_64` | `SpeedHighway-macOS-x86_64.dmg` |

解压 Artifact，打开 DMG，将 **SpeedHighway** 拖入 **Applications** 文件夹。当前应用使用临时签名，未经过 Apple 公证；如果 macOS 阻止首次打开，请在“系统设置 → 隐私与安全性”中允许打开。

### Windows

已有构建文件时，双击 `SpeedHighway3D.exe` 启动 3D 版；经典版的文件名为 `SpeedHighway.exe`。两者都可离线运行，无需安装 Python。仓库目前没有单独发布 Windows 公共下载包，可按下文步骤从源码构建。

## 操作方法

| 按键 | 功能 |
| --- | --- |
| `←` / `→` 或 `A` / `D` | 左右转向 |
| `↑` 或 `W` | 加速，最高 220 km/h |
| `↓` 或 `S` | 刹车 |
| `Esc` | 暂停或继续 |
| `F11`（Mac 可用 `Fn+F11`）或 `F` | 切换全屏 |
| `M` | 切换静音设置 |
| `Enter` 或 `空格` | 开始、继续或重试 |

车辆会自动加速至 180 km/h，按住加速键可提高至 220 km/h。驶出公路会减速；每次碰撞扣除一点生命、降低车速，并提供两秒保护。三点生命耗尽后结算。

行驶距离每 5 米获得 1 分，成功超车获得 150 分。车流会在前三分钟逐渐加快并增多，每组生成的车辆至少留出一条可通行车道。

## 从源码运行

3D 版目前位于 `codex/macos-dmg` 分支，需要 Python 3.11。

```bash
git clone --branch codex/macos-dmg https://github.com/delta-SONG/car-racing.git
cd car-racing
python3.11 -m venv .venv
```

Windows PowerShell：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe macos\prepare_assets.py
.\.venv\Scripts\python.exe game3d.py
```

macOS 或 Linux：

```bash
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python macos/prepare_assets.py
./.venv/bin/python game3d.py
```

`macos/prepare_assets.py` 会下载固定版本的 Noto Sans CJK SC 字体并校验 SHA-256。该步骤和安装依赖需要网络，完成后的游戏不需要联网。

经典 2D 版使用同一环境运行：

```bash
python game.py
```

## 构建安装包

Windows 3D 版：

```powershell
.\build_3d.ps1
```

macOS 可在对应架构的 Mac 上运行：

```bash
bash build_macos.command
```

也可以在 GitHub Actions 中手动运行 **Build macOS DMG**。工作流分别使用 arm64 和 x86_64 Runner 构建、临时签名、验证并上传 DMG。

## 测试

运行自动化测试：

```bash
python -m unittest discover -s tests -v
```

3D 逻辑 smoke 使用无窗口模式，不创建 Cocoa 像素缓冲区：

```bash
python game3d.py --smoke 10 --report smoke-report.json
```

macOS 工作流还会单独启动 Cocoa 原生窗口并尝试保存截图。GitHub Runner 上的构建和启动检查用于发现依赖、打包与窗口初始化问题，不能代替在真实玩家设备上检查显示、声音、输入手感和长时间运行表现。

## 存档位置

游戏保存最高分、静音状态和所选车型。存档缺失或损坏时会恢复默认设置。

| 系统 | 存档路径 |
| --- | --- |
| Windows | `%LOCALAPPDATA%\SpeedHighway\save.json` |
| macOS | `~/Library/Application Support/SpeedHighway/save.json` |
| Linux | `$XDG_DATA_HOME/SpeedHighway/save.json`，未设置时使用 `~/.local/share/SpeedHighway/save.json` |

## 技术栈

- Python 3.11
- Panda3D：3D 场景、摄像机、光照和界面
- Pygame：经典 2D 版本及程序生成音效
- PyInstaller：Windows 与 macOS 独立程序打包
- GitHub Actions：Apple Silicon 与 Intel DMG 构建

## 字体与许可

项目打包使用 **Noto Sans CJK SC Regular**，字体许可见 [`assets/OFL.txt`](assets/OFL.txt)，遵循 SIL Open Font License 1.1。

仓库当前未提供项目源码许可证。除上述字体许可外，请勿默认将源码视为已授权复制、修改或再分发。
