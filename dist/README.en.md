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
- Auto retrieval & citations (optional): may search arXiv/web sources and write references into the output (depends on the ThorData key or “Search mode”)
- Auto experiments / verification (optional): when the environment allows, the agent may generate/modify experiment code and commands, execute them, and write results to the output folder; if dependencies/permissions are missing, this step may be skipped or fail
- Auto polishing & formatting: iteratively refines structure and language; generates Docx and renders Mermaid/Graphviz diagrams when the toolchain is available
- API settings (stored locally on your machine, not in this repo):
  - `API_KEY`
  - `BASE_URL` (default `https://0-0.pro/v1`)
  - `MODEL`
  - Web scraping key (ThorData, optional)
  - Search mode (optional): if the ThorData key is empty, `search_web` uses `/v1/search` under your `BASE_URL`
- Live outputs and logs:
  - Outputs are synced to the output folder during runtime
  - The output folder contains `_logs/run.log`, `_logs/agent.log`, `_logs/conversation.json`

## How to use (quick test)

Note: `OceanS_Paper.exe` is built in onefile mode. It usually starts slower than running from source because it needs to unpack/load its runtime.

1. Double-click `OceanS_Paper.exe`
2. Open Settings and fill in `API_KEY` / `BASE_URL` / `MODEL`
   - For web retrieval: provide “Web scraping key (ThorData)”
   - If you don’t want a crawling key: enable “Search mode” (uses `/v1/search?q=...` under your `BASE_URL` domain and authorizes with your `API_KEY`)
3. Go back to Generate, enter your topic, select the type, and start
4. Check outputs at `%USERPROFILE%\\Documents\\OceanS_Paper_Output\\<run_id>\\`
   - Progress logs: `_logs/run.log`
   - Final paper: typically `paper_final.docx`

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
