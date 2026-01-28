# OceanS Paper Generator

[English](README_EN.md)

这是一个 Windows 桌面应用：用户输入论文主题/方向，选择论文类型（英文 CS / 中文 CS / 非 CS），应用会调用用户自定义的 OpenAI-Compatible 接口生成论文，并把结果输出到固定的“输出目录”。

## Windows 可执行文件（已打包）

- 可执行文件：`dist/OceanS_Paper.exe`
- 分发用说明：`dist/README.zh-CN.md`、`dist/README.en.md`

## 主要功能

- 论文生成：输入主题 → 选择类型 → 生成论文（最终通常为 `paper_final.docx`）
- 三套 Prompt（随应用内置并自动引用）：
  - 英文 CS：`prompts/paper/英文CS论文_paper_generation_prompt.md`
  - 中文 CS：`prompts/paper/中文CS论文_paper_generation_prompt.md`
  - 非 CS：`prompts/paper/非CS论文_paper_generation_prompt.md`
- API 设置（在“设置”页保存）：
  - `API_KEY`：模型服务 Key
  - `BASE_URL`：默认 `https://0-0.pro/v1`
  - `MODEL`：模型名
  - 网页抓取 Key（ThorData）（可选）：用于联网搜索/网页抓取
  - 搜索模式（可选）：未填写“网页抓取 Key（ThorData）”但开启搜索模式时，`search_web` 会走 `BASE_URL` 同域的 `/v1/search?q=...`，并使用上方填写的 `API_KEY` 作为 `Authorization: Bearer ...`
- 运行日志与实时输出：运行中会持续同步可见产物到输出目录，并在输出目录生成 `_logs/`：
  - `_logs/run.log`：运行日志（用于 UI 实时显示）
  - `_logs/agent.log`：智能体内部日志
  - `_logs/conversation.json`：对话历史（已做敏感信息脱敏）

## 输出目录

输出根目录按当前 Windows 用户的“文档”目录计算：

- `%USERPROFILE%\\Documents\\OceanS_Paper_Output\\<run_id>\\`

每次任务会创建一个新的 `<run_id>` 子目录；运行中即可打开查看，最终论文通常为 `paper_final.docx`。

## 配置保存位置

配置会保存到本机用户目录（不在仓库内）：

- `%APPDATA%\\OceanS_Paper\\config.json`

## 下载说明（如果你在 GitHub 上分发 exe）

`dist/OceanS_Paper.exe` 文件较大（超过 GitHub 100MB 限制时），建议使用 **Git LFS** 存储：

- 安装：`git lfs install`
- 克隆：`git clone <repo_url>`

## API Key 安全

- 本项目/仓库不应包含任何真实 `API_KEY` 等敏感信息
- 应用仅把配置保存到本机：`%APPDATA%\\OceanS_Paper\\config.json`
