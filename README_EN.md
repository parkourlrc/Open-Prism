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
