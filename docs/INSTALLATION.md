# 安装与运行

## Docker Desktop（推荐）

前提：安装并启动 Docker Desktop，然后在项目根目录执行：

    docker compose up --build

访问 http://localhost:8080 。关闭终端会停止服务；需要后台运行时使用：

    docker compose up --build -d

查看日志：

    docker compose logs -f

停止服务但保留学习数据：

    docker compose down

Docker 数据存储在 palo-data volume。要连同所有 Docker 中的学习数据一起移除，请明确执行：

    docker compose down --volumes

这会删除容器内的 SQLite、下载内容、提交快照和证书，无法从该 volume 恢复。

### Docker 中使用 Obsidian

Docker 无法自动看到主机文件夹。先在 compose.yaml 的 app.volumes 下添加你的 Vault 挂载，例如 Windows：

    - "C:/Users/you/Documents/MyVault:/vault"

重启 docker compose 后，在网页 Settings 中将 Obsidian Vault Path 填为 /vault。应用仍只会创建 /vault/AI-Learning。

### Docker 中使用本机 Ollama 或 LM Studio

在 Settings 选择 OpenAI-compatible endpoint。Docker Desktop 通常可通过下列地址访问主机上的服务：

    http://host.docker.internal:11434/v1

填写服务实际暴露的模型名称。Ollama 和 LM Studio 的 OpenAI 兼容模式通常不需要 API key。不要把 localhost 写入 Docker 配置；容器中的 localhost 指向容器自身。

Codex CLI 需要由启动应用的操作系统直接执行，因此推荐在原生启动模式下使用。Docker 用户可选择兼容 API，或自行构建带有受控 Codex CLI 的镜像。

## 原生运行

前提：Python 3.11+、Node.js 22.22.2+（LTS）、24.15+ 或更新的兼容版本，以及 Git（只在使用 GitHub 作业资源时需要）。

在项目根目录执行：

    python scripts/run_local.py

Windows PowerShell 也可以执行：

    .\scripts\start-local.ps1

首次运行时脚本会创建 .venv、安装 Python 和 Node 依赖、构建网页并执行 Alembic migration。之后依赖文件未变更时会复用本地环境。

可选参数：

    python scripts/run_local.py --no-browser
    python scripts/run_local.py --port 8090
    python scripts/run_local.py --reload

按 Ctrl+C 停止原生服务。运行数据默认位于 data 目录；想把数据放到别处，可在启动前设置 PALO_DATA_DIR。

PowerShell 示例：

    $env:PALO_DATA_DIR = "D:\LearningOSData"
    python scripts/run_local.py

## 更新

拉取项目更新后重新运行相同启动命令：

    git pull
    docker compose up --build

或：

    git pull
    python scripts/run_local.py

启动器会检测 requirements.txt 与 package-lock.json 的变化；数据库 migration 会在每次启动时安全地执行。

## AI 提供方说明

Codex CLI 是本机命令行集成，不需要在应用中复制粘贴密钥。用户需要自己安装并登录 Codex，并在 Settings 确认其状态。

OpenAI-compatible 模式使用 POST 到 base URL 下的 chat/completions。它支持本地和远程提供方。远程提供方可能产生费用，并会在用户每次明确确认后收到必要的作业反馈材料；请先阅读该提供方的隐私政策。
