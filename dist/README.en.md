# OceanS Paper Generator (Windows)

[中文](README.zh-CN.md) | [English](README.en.md)

This repo is only for distributing the Windows executable: `OceanS_Paper.exe`.

## What it does

`OceanS_Paper.exe` is a Windows desktop app that generates a paper from your topic/idea. You can choose the paper type (English CS / Chinese CS / Non-CS). It uses an OpenAI-compatible API configured in the Settings page and writes all outputs into a fixed output folder.

## Key features

- Paper generation: input topic → choose paper type → generate (final output is typically `paper_final.docx`)
- Built-in prompts (bundled inside the app):
  - English CS: `prompts/paper/英文CS论文_paper_generation_prompt.md`
  - Chinese CS: `prompts/paper/中文CS论文_paper_generation_prompt.md`
  - Non-CS: `prompts/paper/非CS论文_paper_generation_prompt.md`
- API settings (stored locally on your machine, not in this repo):
  - `API_KEY`
  - `BASE_URL` (default `https://0-0.pro/v1`)
  - `MODEL`
  - Web scraping key (ThorData, optional)
  - Search mode (optional): if the ThorData key is empty, `search_web` uses `/v1/search` under your `BASE_URL`
- Live outputs and logs:
  - Outputs are synced to the output folder during runtime
  - The output folder contains `_logs/run.log`, `_logs/agent.log`, `_logs/conversation.json`

## Output folder

Default output root:

- `%USERPROFILE%\\Documents\\OceanS_Paper_Output\\<run_id>\\`

Each run creates a new `<run_id>` folder. The final paper is typically `paper_final.docx`.

## Download notes (Important)

This repo uses **Git LFS** to store `OceanS_Paper.exe` (because it exceeds GitHub’s 100MB limit).

- Download from GitHub web UI: open the `OceanS_Paper.exe` file page and download it.
- If you clone via git, install and enable Git LFS first:
  - Install: `git lfs install`
  - Clone: `git clone <repo_url>`

## API key safety

- Your settings are saved locally at `%APPDATA%\\OceanS_Paper\\config.json`
- This repo does not contain your API keys. Do not commit any secrets into markdown/code.

---

加我联系方式，拉您进用户群呐：
Telegram:@ryonliu
如需稳定便宜的API，查看：https://0-0.pro/

