# 安装与运行指南

[English](INSTALLATION.md) · 中文

本指南说明 Syllabloom 的本地安装、数据持久化、AI 提供方、Obsidian、更新、备份和排错。只想快速运行时，请阅读 [中文 README](../README.zh-CN.md)。

## 选择运行方式

| 方式 | 适用场景 | 访问地址 |
| --- | --- | --- |
| Docker Desktop | 想只启动一个服务，且不要求容器内直接调用 Codex CLI。 | http://localhost:8080 |
| 原生启动器 | 想调用本机已安装的 Codex CLI，或希望直接管理本地文件。 | http://127.0.0.1:8000 |

两种方式都会同时提供前端和 FastAPI 服务。正常使用时不需要另行启动 Vite。

## Docker Desktop

1. 安装 Docker Desktop，并确认 Docker 引擎已启动。
2. 克隆仓库：

       git clone https://github.com/athlonk8/syllabloom.git
       cd syllabloom

3. 启动：

       docker compose up --build

4. 打开 http://localhost:8080。

前台运行时终端会显示日志。后台运行：

    docker compose up --build -d

常用命令：

    docker compose logs -f
    docker compose down
    docker compose up

Docker 会把运行时数据保存在命名的 Syllabloom volume 中。以下命令具有破坏性：

    docker compose down --volumes

它会删除 SQLite 数据库、下载资料、提交快照和生成的证书。请在执行前备份重要数据。

### Docker 中使用 Obsidian

容器不能自动看到主机目录。请在 compose.yaml 的 app 服务中添加 Vault 挂载，并保留现有数据卷：

    volumes:
      - syllabloom-data:/data
      - "C:/Users/you/Documents/MyVault:/vault"

把路径替换为自己的绝对路径。重启 docker compose 后，在 Settings 中将 Obsidian Vault Path 设置为 /vault。Syllabloom 只会在 /vault/AI-Learning 中写入。

### Docker 连接本机 AI 服务

容器里的 localhost 指向容器自己。当 Ollama 或 LM Studio 运行在主机上时，Docker Desktop 通常通过以下地址访问它：

    http://host.docker.internal:11434/v1

在 Settings 中将该地址填为兼容 API 基础 URL，并填写服务实际提供的模型名。Docker 中不要填写 http://localhost:11434/v1。

标准镜像不安装或登录 Codex CLI。Docker 用户应连接兼容 API；需要 Codex CLI 时请使用原生启动。

## 原生启动

### 前置条件

- Python 3.11 或更新版本。
- Node.js：22 系列需 22.22.2 或更新，24 系列需 24.15.0 或更新，或更高的兼容版本。
- Git：克隆仓库或下载公开 GitHub 作业资源时需要。
- Codex CLI：仅在选择 Codex CLI 反馈时需要。

启动：

    git clone https://github.com/athlonk8/syllabloom.git
    cd syllabloom
    python scripts/run_local.py

Windows PowerShell：

    .\scripts\start-local.ps1

启动器会创建 .venv，在 requirements 或 package lock 发生变化时安装依赖，构建生产前端，执行数据库迁移，并启动 FastAPI。

可选参数：

    python scripts/run_local.py --no-browser
    python scripts/run_local.py --port 8090
    python scripts/run_local.py --reload
    python scripts/run_local.py --skip-install

只有在成功正常安装后才使用 --skip-install。--reload 用于开发贡献。按 Ctrl+C 停止原生服务。

## 配置

通常请在 Settings 中完成配置。密钥会保存在本地 SQLite 中，设置接口只显示密钥是否已配置。

如需环境变量方式，在仓库根目录复制 .env.example：

    Copy-Item .env.example .env

macOS 或 Linux：

    cp .env.example .env

.env 被 Git 忽略，请不要提交真实密钥。

| 变量 | 用途 | 示例 |
| --- | --- | --- |
| SYLLABLOOM_DATA_DIR | 原生模式数据目录。 | D:/SyllabloomData |
| SYLLABLOOM_DATABASE_URL | 高级 SQLAlchemy 地址覆盖。 | 通常留空。 |
| SYLLABLOOM_YOUTUBE_API_KEY | 官方 YouTube Data API 密钥。 | 可选。 |
| SYLLABLOOM_WATCH_COMPLETION_THRESHOLD | 判定完成所需的不重复观看比例。 | 0.85 |
| SYLLABLOOM_CRAWL_MAX_PAGES | 每次导入最多检查的公开页面数。 | 18 |
| SYLLABLOOM_CRAWL_MAX_DEPTH | 从输入网址跟随同域链接的最大深度。 | 1 |
| SYLLABLOOM_AI_PROVIDER | codex_cli、openai_compatible 或 disabled。 | codex_cli |
| SYLLABLOOM_AI_BASE_URL | 兼容 Chat Completions 的地址。 | http://localhost:11434/v1 |
| SYLLABLOOM_AI_MODEL | 兼容提供方的模型名称。 | 由提供方决定 |
| SYLLABLOOM_AI_API_KEY | 兼容提供方的可选密钥。 | 许多本地服务可留空 |

Docker Compose 同样会从环境变量或根目录 .env 读取这些 SYLLABLOOM 变量。

## 在 Settings 中配置服务

### YouTube

自动导入播放列表和视频元数据仅使用官方 YouTube Data API。请在自己的 Google Cloud 项目创建并合理限制 API key，再粘贴到 Settings。已知公开视频也可以使用 Manual fallback，不需要 key。

### Obsidian

选择一个已存在的 Vault。应用会创建类似 AI-Learning/课程名/Assignments/作业标识 的目录，并以 Answer.md 为可编辑答案。它不会覆盖已有 Answer.md，也不会写到配置 Vault 之外。

### Codex CLI

原生模式可以使用主机上已安装并登录的 Codex CLI。请在同一终端环境检查：

    codex --version

Settings 会显示是否发现可执行文件。每次你明确确认提交后，Syllabloom 会创建暂存副本，并以只读 sandbox 请求 Codex 反馈；Codex 没有写入本地作业工作区的权限。

### 兼容 OpenAI 的端点

支持 Ollama、LM Studio、vLLM、OpenAI 及其他兼容 Chat Completions 的服务。填写基础 URL、模型名和必要的密钥。

原生本地服务的常见地址：

    http://localhost:11434/v1

Docker 到主机时请使用前述 host.docker.internal 地址。远程端点属于外部服务，可能有费用和自己的数据保留政策。Syllabloom 会在每一次请求前要求新的勾选确认。

### Disabled

Disabled 会关闭 AI 反馈；当导入的作业有公开官方测试时，测试仍可运行。

## 语言

首次打开的界面为英文。用侧栏底部 English 或 中文 链接切换。链接会写入 lang 查询参数，因此本身就是普通超链接；浏览器可用本地存储时会记住选择。

## 数据、备份与更新

原生模式在配置的数据目录下保留数据库和 LearningVault，包括来源下载、工作区、快照、反馈和证书。停止 Syllabloom 后复制整个数据目录是最直接的备份方式。

Docker 模式把等价数据放在命名 volume 中。请使用常规 Docker volume 备份流程，并在升级前验证备份。Git 克隆不是备份：运行时数据和密钥本来就不会提交。

迁移原生数据：

1. 停止 Syllabloom。
2. 复制整个数据目录。
3. 在新设备首次启动前，将 SYLLABLOOM_DATA_DIR 指向该副本。
4. 启动后检查概览和作业历史。

Docker 更新：

    git pull
    docker compose up --build

原生更新：

    git pull
    python scripts/run_local.py

数据库迁移会在启动时执行。拥有完整旧结构但无 Alembic 版本记录的数据库会经过验证后安全标记；不完整的数据库不会被静默当作最新版本。

## 常见问题

| 现象 | 排查 |
| --- | --- |
| 端口被占用 | 原生使用 --port 8090；Docker 将 compose.yaml 的 8080:8000 改为可用端口。 |
| Docker 页面打不开 | 运行 docker compose logs -f，确认 Docker Desktop 正在运行。 |
| Codex CLI 不可用 | 用原生方式，在同一 shell 运行 codex --version，安装或登录后重启。 |
| Docker 连接不到 Ollama | 使用 host.docker.internal 而不是 localhost，并确认主机服务允许容器连接。 |
| 播放列表导入要求 API key | 添加 YouTube Data API key，或用 Manual fallback 导入公开视频。 |
| Stanford 来源被标为 protected | 这是预期行为：需要登录的资源会保留溯源，但应用绝不绕过认证。 |
| Docker 中导出 Obsidian 失败 | 检查主机目录已挂载、Settings 使用容器路径，且目录可写。 |
| 迁移失败 | 先备份数据目录，检查错误，再报告问题时不要附上私有数据。不要首先删除数据库。 |

## 卸载

原生：停止服务后可删除仓库；只有明确要清空学习记录时才删除数据目录。

Docker：docker compose down 会删除服务但保留数据。只有明确要清空全部数据时才删除命名 volume。
