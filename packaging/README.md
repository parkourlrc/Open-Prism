## Open-Prism 打包（Windows）

本项目使用 `PyInstaller` 打包为 Windows 桌面应用，并将 Pandoc / Graphviz / Mermaid 相关依赖一并打入可执行文件。

### 一键打包

在项目根目录运行：

`powershell -ExecutionPolicy Bypass -File packaging/build_windows.ps1`

打包成功后输出文件为：`dist/OceanS_Paper.exe`

### 运行与输出

- 启动：双击 `dist/OceanS_Paper.exe`
- 结果输出固定在：`%USERPROFILE%\\Documents\\OceanS_Paper_Output\\<run_id>`
  - 最终论文通常为：`paper_final.docx`
