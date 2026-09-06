# macOS 打包

## 当前状态

源码已适配 macOS，并提供本地及 GitHub Actions 构建脚本。Windows 环境不能直接运行这套原生打包流程；在 macOS 构建完成前，不应将源码 ZIP 当成 DMG 安装包。

## 在 Mac 上构建

1. 安装 Python 3.11，解压完整源码。
2. 在项目目录打开终端，运行 `bash build_macos.command`。
3. 脚本安装依赖、运行逻辑与字体测试、创建 `.app`、启动打包后的游戏测试 10 秒，再生成和挂载验证 DMG。
4. 输出位于 `dist/macos/arm64/`（Apple 芯片）或 `dist/macos/x86_64/`（Intel）。

构建首次需要网络安装 Python 依赖并获取已固定版本、校验 SHA-256 的开源字体；生成的游戏不需要网络或 Python。DMG 内有可拖入 Applications 的应用、中文说明及字体许可。脚本使用本机 Python 架构，分别在对应架构的 Mac 上构建。

## GitHub Actions

将项目文件上传到指定仓库后，在 Actions 中选择 **Build macOS DMG → Run workflow**。也可以推送到 `codex/macos-dmg` 分支触发。工作流分别在 `macos-14` ARM 和 `macos-15-intel` Intel 机器上打包两个 DMG，下载成功运行的 Artifacts 即可取得。

云端 smoke test 使用 SDL dummy 驱动，不代替真实 Mac 的窗口、声音和输入体验验收。没有实际执行工作流前，不能保证 runner 配额、账户权限或原生依赖安装成功。

## 适配

- 存档：`~/Library/Application Support/SpeedHighway/save.json`。
- 字体：内置 Noto Sans SC（SIL OFL 1.1），不依赖 Windows 字体。
- 全屏：按 F，或 F11 / Fn+F11。
- 签名：PyInstaller 默认 ad-hoc 签名，不含 Apple 开发者证书或 Apple 公证。

如需面向其他用户正式分发，可在具备 Apple Developer ID 证书后增加签名与公证流程；当前未配置这类账户或证书。

参考：[PyInstaller 平台限制](https://www.pyinstaller.org/en/stable/)、[GitHub macOS runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)、[Apple 应用打开说明](https://support.apple.com/en-us/102445)。
