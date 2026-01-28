# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['ocean_paper_desktop.py'],
    pathex=['D:\\桌面\\OceanS\\vendor\\\\pydeps'],
    binaries=[('C:\\Users\\刘容川\\AppData\\Local\\Programs\\Python\\Python311\\DLLs\\\\tcl86t.dll', '.'), ('C:\\Users\\刘容川\\AppData\\Local\\Programs\\Python\\Python311\\DLLs\\\\tk86t.dll', '.')],
    datas=[('prompts', 'prompts'), ('custom_tools', 'custom_tools'), ('default_reference.docx', '.'), ('D:\\桌面\\OceanS\\build\\bin\\pandoc_mermaid_filter.exe', 'custom_tools/markdown_to_docx/md2doc_tools/filters/pandoc_mermaid_filter.exe'), ('D:\\nodejs\\node.exe', 'runtime/node/node.exe')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['playwright', 'gradio', 'lightning', 'pytorch_lightning', 'torch', 'torchvision', 'torchaudio', 'skimage', 'scipy', 'sympy', 'matplotlib', 'cv2', 'notebook', 'jupyter', 'ipykernel', 'IPython'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='OceanS_Paper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['D:\\桌面\\OceanS\\assets\\oceans_paper.ico'],
)
