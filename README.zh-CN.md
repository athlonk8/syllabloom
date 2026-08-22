# Syllabloom

新版图文说明：[功能图文说明](docs/FEATURE_TOUR.zh-CN.md)。其中包含 B 站登录后回到同一课程并自动刷新页面内播放器的流程。

[English](README.md) · 中文

Syllabloom 是一个本地优先的学习工作台：它把公开课程、真实观看覆盖度、Obsidian 笔记、作业快照、可选 AI 反馈和独立学习记录组合在一起，供学习者在自己的设备上长期使用。

它不需要 Syllabloom 帐号，也没有默认的云端服务。

## 名称

Syllabloom 由 syllabus 和 bloom 组合而来，表达「把课程大纲变成持续练习和成长」。它是一个产品名，不是 OS 一类的技术架构名称。

## 主要能力

- 通过官方 YouTube Data API 导入公开视频和播放列表。
- 可在任一讲次下粘贴直接包含 BV 号的 B 站视频链接，并使用 B 站自身的 iframe 播放器播放。此类链接会明确标为学习者选择的第三方来源，不会被表述为课程官方材料。
- 在遵守 robots 规则、限制页面数量和深度的前提下导入公开 Stanford 课程页面。
- 通过 YouTube IFrame Player API 记录不重复的真实观看区间；拖动进度条不会被算作已观看。
- 将课程、下载内容、提交快照和证书保存在本地 SQLite 数据库与本地数据目录中。
- 向现有 Obsidian Vault 的 AI-Learning 子目录导出笔记；Answer.md 始终是学习者自己维护的答案来源。
- 有公开官方测试时优先运行测试，然后可选地请求 Codex CLI 或兼容 OpenAI 的端点提供反馈。
- 仅在满足完成条件后生成本地独立学习证书。
- 网页默认英语。侧边栏左下角的 English · 中文 链接可以切换界面语言，浏览器会记住选择。
- 首次使用会跟随系统的深浅色偏好；侧栏底部的主题控件可固定为浅色或深色，并会记住选择。

## 明确的边界

- 不绕过 Canvas、SSO、Gradescope、付费墙、登录或任何访问控制。
- 不抓取 YouTube 网页 HTML 来替代官方 API。
- 不复制 B 站内容、不推断其授权状态，也不绕过 B 站的任何访问限制。
- 不会把 AI 编造的内容标为官方作业。
- 不会静默上传你的笔记、答案或课程资料。
- 不会签发大学学位、官方成绩或暗示与 Stanford 等课程提供方有关联。

## 快速启动

### Docker Desktop

安装并启动 Docker Desktop 后，在终端运行：

    git clone https://github.com/athlonk8/syllabloom.git
    cd syllabloom
    docker compose up --build

然后打开 http://localhost:8080。首次构建会下载依赖；之后通常只需要：

    docker compose up

停止服务但保留学习数据：

    docker compose down

不要随意执行 docker compose down --volumes。该命令会移除 Docker 管理的数据库、下载内容、提交快照和证书。

### 原生一键启动

如果你想使用已安装在电脑上的 Codex CLI，推荐原生方式。请安装 Python 3.11 或更新版本，以及兼容的 Node.js：22 系列需 22.22.2 或更新版本，24 系列需 24.15.0 或更新版本，或更高的兼容版本。

    git clone https://github.com/athlonk8/syllabloom.git
    cd syllabloom
    python scripts/run_local.py

Windows PowerShell 也可以使用：

    .\scripts\start-local.ps1

启动器会创建虚拟环境、按需安装依赖、构建前端、执行安全的数据迁移，随后在 http://127.0.0.1:8000 启动应用。按 Ctrl+C 停止。

更完整的端口、Obsidian 挂载、更新和排错说明，请阅读 [中文安装指南](docs/INSTALLATION.zh-CN.md)。

## 第一次使用

1. 启动后打开 Settings。
2. 若要自动导入 YouTube 播放列表元数据，填写 YouTube Data API 密钥；没有密钥时可用 Manual fallback 手动创建公开视频课程。
3. 如需 Obsidian，设置一个已存在的 Vault 路径。应用只会写入其中的 AI-Learning 目录，且绝不会覆盖已有 Answer.md。
4. 导入公开 YouTube 视频、播放列表或公开 Stanford 课程网址；也可在任一讲次下展开「使用 B 站来源」，粘贴直接的 BV 视频链接。
5. 在应用中观看可嵌入视频。进度按不重复观看区间计算，而不是点击「完成」。
6. 对公开官方作业，下载原始资料、创建笔记、编辑 Answer.md；只有你主动勾选确认后，才会请求 AI 反馈。

## AI 提供方与隐私

AI 反馈是可选的。只有你配置提供方并在每一次提交中明确确认后，应用才会发起外部 AI 请求。

| 提供方 | 适用情况 | 接收的数据 |
| --- | --- | --- |
| Codex CLI | 原生启动，且本机已安装并登录 Codex | 只读的暂存作业工作区。 |
| 兼容 OpenAI 的端点 | Ollama、LM Studio、vLLM、OpenAI 或其他 Chat Completions 兼容服务 | 仅暂存的 Answer.md、有限的公开作业上下文和官方测试摘要。 |
| Disabled | 仅希望运行确定性公开测试 | 不发送 AI 请求。 |

远程兼容端点可能有费用与自己的数据保留规则，请先阅读该服务的政策。API 密钥仅本地保存，设置接口不会返回密钥。

标准 Docker 镜像不会内置或登录 Codex CLI。需要 Codex CLI 时请使用原生启动；Docker 用户可连接例如 Ollama 或 LM Studio 的兼容端点。

## 数据、备份与更新

原生启动默认把数据保存在仓库的 data 目录；如需换位置，请在启动前设置 SYLLABLOOM_DATA_DIR。Docker 使用名为 Syllabloom 的数据卷。二者均不会被提交到 Git。

长期使用前，请备份原生数据目录或 Docker 数据卷。更新时运行：

    git pull
    docker compose up --build

或者：

    git pull
    python scripts/run_local.py

应用会在启动时执行数据库迁移。已有的旧版本地数据库会被安全识别；不完整或不一致的数据库不会被静默标记为最新版本。

## 作业工作台与 B 站账号

每个已导入作业都会显示在课程页面中。点击 **打开作业工作区** 后，可以在网页内查看公开题目说明和关联资料、用 Markdown 撰写答案、保存本地草稿，并创建不可变的本地提交版本。只有选中某个已保存版本并明确确认后，才会调用用户配置好的 Codex CLI 或兼容 AI 提供方。评分页会保留总分、分项能力、逐项解释、优点、待改进点和复习建议；这些均是学习反馈，不是课程官方成绩。

未配置 Obsidian 时，答案保存在 Syllabloom 的 `LearningVault`；配置 Obsidian 后，网页编辑器与 Vault 中的 `Answer.md` 使用同一份文件。提交版本和评分记录仍保存在本地数据目录，后续修改答案不会覆盖历史版本。

B 站播放器提供“登录后返回播放器”“重新加载页面内播放器”和页面内全屏按钮，不再提供跳到 B 站站外播放的按钮。登录会在 B 站自己的页面中完成，Syllabloom 不会读取、保存或代理密码和 Cookie；登录成功后会回到同一课程并重新加载嵌入播放器。播放器 iframe 使用沙箱限制，不能导航外层学习页面或打开新标签页。可选清晰度仍由 B 站、视频和账号权限决定；B 站播放器自身的清晰度提示仍可能可见，但不能带走外层课程页面。

## 文档

- [English README](README.md)
- [Installation guide](docs/INSTALLATION.md)
- [中文安装指南](docs/INSTALLATION.zh-CN.md)
- [User guide](docs/USER_GUIDE.md)
- [用户指南（中文）](docs/USER_GUIDE.zh-CN.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Testing record](docs/TESTING.md)
- [贡献指南](CONTRIBUTING.md)
- [安全政策](SECURITY.md)

## 许可证

Syllabloom 使用 [MIT License](LICENSE) 发布。
