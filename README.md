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
- 自动检索/引用（可选）：根据需要自动检索 arXiv/网页内容，并把来源信息写入输出文件（是否启用取决于你是否配置“网页抓取 Key（ThorData）”或开启“搜索模式”）
- 自动实验/自动验证（可选）：在环境允许时，智能体可能会自动生成/修改实验代码与命令、执行并收集结果，再写入输出目录；若你的机器缺少依赖或权限受限，实验步骤可能会被跳过或失败（建议优先使用可复现的本地脚本/数据集）
- 自动润色与排版：会对论文内容进行多轮改写、结构优化与语言润色；并在可用工具链齐全时生成 Docx、渲染 Mermaid/Graphviz 图
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

## 如何使用（推荐先用 exe 快速测试）

### 使用 exe 快速测试（更慢但最省事）

说明：`dist/OceanS_Paper.exe` 是 onefile 打包版本，启动时需要解压/加载运行时，因此通常会比直接运行源码更慢。

1. 获取 `dist/OceanS_Paper.exe`（如果你是从 GitHub clone，需要先 `git lfs install` 才能拉到完整 exe）
2. 双击运行 `dist/OceanS_Paper.exe`
3. 打开“设置”页，填写 `API_KEY` / `BASE_URL` / `MODEL`
   - 如需联网搜索/网页抓取：填写“网页抓取 Key（ThorData）”
   - 如不想填写网页抓取 Key：可开启“搜索模式”（会使用 `BASE_URL` 同域的 `/v1/search?q=...` 并用你的 `API_KEY` 授权）
4. 回到“生成论文”页，输入主题，选择类型，点击开始
5. 在输出目录查看结果：`%USERPROFILE%\\Documents\\OceanS_Paper_Output\\<run_id>\\`
   - 运行过程：看 `_logs/run.log`
   - 最终论文：通常为 `paper_final.docx`

### 从源码运行（更快但需要准备依赖）

1. 安装 Python（建议 3.11）并创建虚拟环境
2. 安装项目依赖（本仓库未提供 pin 版 `requirements.txt`，建议在你的打包环境中 `pip freeze > requirements.txt` 后复用，或按报错逐个安装缺失依赖）
3. 运行：`python ocean_paper_desktop.py`

注意：如果你希望“生成 docx/渲染图”功能正常工作，需要确保 Pandoc、Node+Mermaid CLI、Graphviz 等工具链可用（exe 版本已内置；源码运行需要你自行安装或准备对应资源路径）。

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
