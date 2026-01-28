# OceanS Paper Generator

[中文](README.md)

A Windows desktop app that generates a paper from a user-provided topic. Users can choose the paper type (English CS / Chinese CS / Non-CS). The app calls a user-configured OpenAI-Compatible API and exports results to a fixed output directory.

## Bundled Windows executable

- Executable: `dist/OceanS_Paper.exe`
- Distribution readmes: `dist/README.zh-CN.md`, `dist/README.en.md`

## Features

- Paper generation: topic → type → paper (final output is usually `paper_final.docx`)
- Built-in prompts (automatically referenced):
  - English CS: `prompts/paper/英文CS论文_paper_generation_prompt.md`
  - Chinese CS: `prompts/paper/中文CS论文_paper_generation_prompt.md`
  - Non-CS: `prompts/paper/非CS论文_paper_generation_prompt.md`
- Auto retrieval & citations (optional): may search arXiv/web sources and write references into the output (depends on whether you provide the ThorData key or enable “Search mode”)
- Auto experiments / verification (optional): when the environment allows, the agent may generate/modify experiment code and commands, execute them, and write results to the output folder; if dependencies or permissions are missing, this step may be skipped or fail
- Auto polishing & formatting: iteratively refines structure and language; generates Docx and renders Mermaid/Graphviz diagrams when the toolchain is available
- API settings (saved in the “Settings” tab):
  - `API_KEY`
  - `BASE_URL` (default: `https://0-0.pro/v1`)
  - `MODEL`
  - Web crawling key (ThorData) (optional)
  - Search mode (optional): when enabled without the ThorData key, `search_web` will use `/v1/search?q=...` under the same `BASE_URL` domain and authorize with the user `API_KEY`.
- Live logs & incremental outputs: during execution, artifacts are synced to the output directory and logs are exported to `_logs/`:
  - `_logs/run.log`
  - `_logs/agent.log`
  - `_logs/conversation.json` (best-effort redaction applied)

## How to run (recommended: quick test with the exe first)

### Quick test with the exe (slower, but easiest)

Note: `dist/OceanS_Paper.exe` is built in onefile mode. It usually starts slower than running from source because it needs to unpack/load its runtime.

1. Get `dist/OceanS_Paper.exe` (if you cloned from GitHub, run `git lfs install` to fetch the full exe)
2. Double-click `dist/OceanS_Paper.exe`
3. Open the Settings tab and fill in `API_KEY` / `BASE_URL` / `MODEL`
   - For web retrieval: provide “Web crawling key (ThorData)”
   - If you don’t want a crawling key: enable “Search mode” (uses `/v1/search?q=...` under your `BASE_URL` domain and authorizes with your `API_KEY`)
4. Go back to Generate, enter your topic, select the type, and start
5. Check outputs at `%USERPROFILE%\\Documents\\OceanS_Paper_Output\\<run_id>\\`
   - Progress logs: `_logs/run.log`
   - Final paper: typically `paper_final.docx`

### Run from source (faster, but requires dependencies)

1. Install Python (recommended 3.11) and create a virtual environment
2. Install dependencies (this repo does not ship a pinned `requirements.txt`; reuse your packaging environment via `pip freeze > requirements.txt`, or install missing packages based on runtime errors)
3. Run: `python ocean_paper_desktop.py`

Note: to keep “Docx export / diagram rendering” working, you need Pandoc, Node+Mermaid CLI, Graphviz, etc. (bundled in the exe; for source runs you must install/provide them yourself or adjust resource paths).

## Output directory

The output root is computed from the current Windows user profile:

- `%USERPROFILE%\\Documents\\OceanS_Paper_Output\\<run_id>\\`

Each run creates a new `<run_id>` folder; the final paper is typically `paper_final.docx`.

## Config location

Settings are stored per user (not inside the repo):

- `%APPDATA%\\OceanS_Paper\\config.json`

## Download notes (if you distribute the exe on GitHub)

If `dist/OceanS_Paper.exe` exceeds GitHub’s 100MB file limit, store it with **Git LFS**:

- Install: `git lfs install`
- Clone: `git clone <repo_url>`

## API key safety

- Do not commit any secrets (e.g., `API_KEY`) into markdown/code
- The app stores settings locally at `%APPDATA%\\OceanS_Paper\\config.json`
