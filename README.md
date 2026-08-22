# Personal AI Learning OS

一个本地优先的学习系统，用于把公开可访问的 YouTube、Stanford 课程页以及由课程页直接链接的官方教学资源，组织为可观看、可追踪、可作答、可复盘的个人学习工作区。

它不会绕过 Canvas、Stanford SSO、Gradescope、付费墙或其他访问限制；不会把 AI 生成题冒充为官方作业；不会自动上传课程资料、作答或笔记到云端。

## 已实现的 MVP 闭环

- React + TypeScript + Vite 本地 Web UI，FastAPI + SQLAlchemy + SQLite 后端，Alembic 初始迁移。
- 数据库驱动的 Course、Module、Lecture、Video、Resource、Assignment、Submission、Grade、GradingRun、WatchSession、WatchSegment、LearningNote、Certificate、ImportJob、AppSetting、ObsidianConfig 等实体。
- YouTube IFrame Player API 播放器；保存观看区间、合并重叠区间、跨刷新恢复位置，默认以 85% unique coverage 判定讲座完成。
- 官方 YouTube Data API playlist / 单视频导入。没有 API key 时会明确引导到手动导入，绝不抓取 YouTube HTML 伪造 API。
- 有边界的 Stanford 通用导入器：从一个用户给定的 `.stanford.edu` URL 开始，检查 robots.txt、限速、限制页面数和深度，只抓同主机相关课程页；外部 GitHub/PDF 只在官方课程页直接链接时才视为有来源证据的官方外部资源。
- 官方 Assignment 解析与下载：原件保存到 `LearningVault/.../original/`，GitHub 使用只读式浅克隆，记录 commit hash；用户工作区与提交快照互不覆盖。
- Obsidian Vault 集成：只写入用户选择 Vault 中的 `AI-Learning/` 子目录，生成课程、讲座、作业、Answer 和 Feedback 笔记；系统从同一份 `Answer.md` 读取最新内容。
- Codex CLI 发现、只读 sandbox 评分工作区、官方 pytest 优先、Pydantic JSON schema 校验、版本化 Submission / GradingRun。真正调用 Codex 前需要用户在 UI 显式确认可能的云端提交。
- Completion Certificate / Mastery Certificate 资格检查和本地 PDF 生成。证书明确是 independent learning credential，不使用 Stanford 标志或暗示 Stanford 认证。

## 快速启动（Windows PowerShell）

第一次运行：

```powershell
Set-Location D:\AI\personal-ai-learning-os
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Set-Location backend
..\.venv\Scripts\alembic.exe -c alembic.ini upgrade head
Set-Location ..\frontend
npm install
```

终端一：

```powershell
Set-Location D:\AI\personal-ai-learning-os\backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

终端二：

```powershell
Set-Location D:\AI\personal-ai-learning-os\frontend
npm run dev
```

打开 `http://localhost:5173`。也可以使用 [start-backend.ps1](D:/AI/personal-ai-learning-os/scripts/start-backend.ps1) 和 [start-frontend.ps1](D:/AI/personal-ai-learning-os/scripts/start-frontend.ps1)。

## 首次使用流程

1. 打开 **Settings**，可选地保存本地 `YOUTUBE_API_KEY`，并设置一个已存在的 Obsidian Vault 路径。
2. 点击 **Add course**，粘贴 YouTube playlist / video URL 或 Stanford 课程 URL。
3. 在应用内播放 YouTube 视频。暂停、跳转、倍速、重看和刷新都不会把播放时长重复计数。
4. 在作业卡片中下载公开的官方原件，再创建 Obsidian 工作区。在 `Answer.md` 中作答。
5. 勾选显式确认后点击 **Submit to Codex**。应用创建不可变快照；官方测试优先于 Codex 定性反馈。
6. 修订同一份 `Answer.md` 后重新提交，历史版本和成绩会保留。
7. 达到资格条件后生成本地 Personal Learning Certificate PDF。

详细说明见 [用户指南](D:/AI/personal-ai-learning-os/docs/USER_GUIDE.md)，架构见 [ARCHITECTURE.md](D:/AI/personal-ai-learning-os/docs/ARCHITECTURE.md)，验证记录见 [TESTING.md](D:/AI/personal-ai-learning-os/docs/TESTING.md)。

## 本地数据与安全

- SQLite 和下载资料默认为 `data/`，均被 `.gitignore` 排除。
- `YOUTUBE_API_KEY` 仅存本地 SQLite 的 secret setting，绝不写入源代码。
- 不支持删除课程、原始作业或用户文件的 API。
- 作业下载和工作区路径都经过目录边界校验。详见 [SECURITY.md](D:/AI/personal-ai-learning-os/docs/SECURITY.md)。

## 已知限制

- Stanford 页面结构会变化；导入器保存 partial 状态和错误，而不是猜测遗漏内容。
- 被 Stanford 验证页、Canvas、SSO 或 Gradescope 保护的资源只记录来源和 `Requires Stanford authentication`，不会访问。
- Codex CLI 的实际评分需要用户明确点击和确认；自动测试仅验证 CLI 检测、只读命令构造与 JSON 解析，不会擅自把作业上传给外部服务。
- Mastery Certificate 的 `Final Review` 扩展尚未实现；若课程策略要求它，系统会拒绝发证而不会假装完成。
