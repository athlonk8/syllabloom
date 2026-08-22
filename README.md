# Personal AI Learning OS

一个可自行托管、优先在本机运行的学习工作台。它把公开课程资料、真实观看进度、Obsidian 笔记、作业快照、可选 AI 反馈和本地证书放在同一个长期可用的系统里。

项目不会绕过 Canvas、SSO、Gradescope、付费墙或任何访问控制；不会把 AI 生成内容伪装成官方作业；不会自动把你的资料上传到云端。

## 用一分钟启动

推荐 Docker 方式：只需 Docker Desktop，不需要分别安装 Python、Node.js 或启动两个终端。

    git clone https://github.com/YOUR_GITHUB_USERNAME/personal-ai-learning-os.git
    cd personal-ai-learning-os
    docker compose up --build

打开 http://localhost:8080 。首次构建会花几分钟，之后只需执行 docker compose up。

也可以原生启动（适合希望使用本机 Codex CLI 的用户）。需要 Python 3.11+ 与 Node.js 22.22.2+（LTS）、24.15+ 或更新的兼容版本：

    git clone https://github.com/YOUR_GITHUB_USERNAME/personal-ai-learning-os.git
    cd personal-ai-learning-os
    python scripts/run_local.py

脚本会创建本地虚拟环境、安装所需依赖、构建网页、执行数据库迁移，并在 http://127.0.0.1:8000 打开应用。Windows 用户也可运行 scripts/start-local.ps1。

详细的安装、停止、升级及 Docker + Obsidian 挂载说明见 [安装指南](docs/INSTALLATION.md)。

## 首次配置

打开 Settings 后按需配置：

1. YouTube Data API key：仅当需要从官方 YouTube Data API 导入播放列表或视频元数据时才需要。没有 key 时可以使用手动导入；系统绝不抓取 YouTube HTML 充当替代 API。
2. AI feedback provider：
   - Codex CLI：原生启动时使用已经安装并登录的 Codex CLI。每次提交都会创建快照，并以只读 sandbox 启动 CLI。
   - OpenAI-compatible endpoint：可连接 Ollama、LM Studio、vLLM、OpenAI 或其他兼容 Chat Completions 的服务。填写 base URL、模型名和可选 API key。
   - Disabled：只运行官方公开测试，不发送 AI 请求。
3. Obsidian Vault Path：选择已有 Vault。应用只会写入其中的 AI-Learning 子目录，并且不会覆盖你的 Answer.md。

所有 AI 反馈都要求用户在每次提交前显式勾选确认。Codex 会读取只读的作业快照；兼容接口只接收作业标题、公开描述、课程 AI 政策、官方测试摘要（如有）和拷贝出的 Answer.md。

## 已实现的功能

- React、TypeScript、FastAPI、SQLite、SQLAlchemy 和 Alembic 构成的本地网页应用。
- 官方 YouTube Data API 导入，以及使用 IFrame Player API 的视频播放、去重观看区间、断点恢复和完成度计算。
- 有页数/深度边界、遵守 robots 规则的 Stanford 公开课程导入；受保护资源会记录来源而不会绕过认证。
- 仅从官方课程页面直接链接的资源中解析作业；原件、个人工作区和提交快照彼此隔离。
- Obsidian 集成，Answer.md 是网页和笔记应用共享的答案源。
- 官方 pytest 优先的作业检查，加上可选的 Codex CLI 或 OpenAI-compatible AI 反馈。
- 本地生成 Independent Learning Certificate；不会使用 Stanford 标志或暗示 Stanford 授权。
- GitHub Actions CI、贡献指南、报告安全问题的流程和问题模板已包含在仓库中。

## 数据与隐私

原生运行时，数据库、下载内容、快照和证书默认放在项目下的 data 目录。Docker 运行时，它们放在名为 palo-data 的 Docker volume 中。二者均已被 Git 忽略。

YouTube key 和 AI API key 只保存在本机 SQLite 或由你自己提供的环境变量中。设置接口只显示“已配置”，不会返回密钥。

网络访问只有在以下用户动作后发生：

- 导入公开课程或下载其公开资源；
- 用户主动选择的 AI 反馈提交；
- 浏览器加载 YouTube 播放器。

完整边界见 [安全说明](docs/SECURITY.md)。

## 为贡献者准备

原生开发：

    python scripts/run_local.py --reload

后端测试：

    .venv/Scripts/python -m pytest -q

前端测试和构建：

    cd frontend
    npm test
    npm run build

Windows PowerShell 下后端 Python 路径为 .venv\Scripts\python.exe。更多约定见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 文档

- [安装指南](docs/INSTALLATION.md)
- [用户指南](docs/USER_GUIDE.md)
- [架构](docs/ARCHITECTURE.md)
- [测试记录](docs/TESTING.md)
- [安全说明](docs/SECURITY.md)

## 发布前的许可证

仓库已具备公开发布所需的工程文件，但许可证需要维护者明确选择后才会添加。公开创建 GitHub 仓库前，请在 MIT、Apache-2.0、GPL-3.0 或其他适合你的许可证之间做出选择。
