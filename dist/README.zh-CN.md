# OceanS Paper Generator（Windows）

[中文](README.zh-CN.md) | [English](README.en.md)

本仓库仅用于分发可执行文件 `OceanS_Paper.exe`。

## 应用简介

`OceanS_Paper.exe` 是一个 Windows 桌面应用：输入论文主题/方向，选择论文类型（英文 CS / 中文 CS / 非 CS），应用会调用你在“设置”里填写的 OpenAI-Compatible 接口生成论文，并把结果输出到“输出目录”。

## 主要功能

- 生成论文：输入主题/方向 → 选择论文类型 → 开始生成（通常输出 `paper_final.docx`）
- 三套内置 Prompt（应用内置并自动引用）：
  - 英文 CS：`prompts/paper/英文CS论文_paper_generation_prompt.md`
  - 中文 CS：`prompts/paper/中文CS论文_paper_generation_prompt.md`
  - 非 CS：`prompts/paper/非CS论文_paper_generation_prompt.md`
- API 设置（保存在本机，不会上传到 GitHub）：
  - `API_KEY`
  - `BASE_URL`（默认 `https://0-0.pro/v1`）
  - `MODEL`
  - 网页抓取 Key（ThorData，可选）
  - 搜索模式（可选）：未填网页抓取 Key 时走 `BASE_URL` 同域 `/v1/search`
- 运行中可见输出：
  - 运行中会持续同步产物到输出目录
  - 输出目录会生成 `_logs/run.log`、`_logs/agent.log`、`_logs/conversation.json` 方便排查进度

## 输出目录

默认输出根目录：

- `%USERPROFILE%\\Documents\\OceanS_Paper_Output\\<run_id>\\`

每次运行会创建新的 `<run_id>` 子目录；最终论文通常为 `paper_final.docx`。

## 下载说明（重要）

本仓库使用 **Git LFS** 存储 `OceanS_Paper.exe`（因为文件大于 GitHub 100MB 限制）。

- 直接在 GitHub 网页下载：打开 `OceanS_Paper.exe` 文件页面后下载即可
- 如果使用 `git clone`，请先安装并启用 Git LFS：
  - 安装：`git lfs install`
  - 克隆：`git clone <repo_url>`

## API Key 安全

- 应用会把你的配置保存到本机用户目录：`%APPDATA%\\OceanS_Paper\\config.json`
- 本仓库不包含你的 `API_KEY` 等敏感信息；请不要把密钥写入任何源码/文档后再提交

---

加我联系方式，拉您进用户群呐：
Telegram:@ryonliu
如需稳定便宜的API，查看：https://0-0.pro/

