$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

function Restore-AnyStaleDisabledPthFiles {
  param([string]$SitePackages)
  $stale = Get-ChildItem -Path $SitePackages -Filter "*.disabled_for_build" -ErrorAction SilentlyContinue
  foreach ($f in $stale) {
    $orig = $f.FullName -replace "\.disabled_for_build$", ""
    Move-Item -Force $f.FullName $orig
    Write-Host "Restored stale .pth: $orig"
  }
}

function Disable-ExtraPthFiles {
  param([string]$SitePackages)
  $names = @(
    "3dphoto.pth",
    "Hallo.pth",
    "VExpress.pth",
    "_uak.pth",
    "__editable__.physprop-0.1.0.pth"
  )
  $disabled = @()
  foreach ($n in $names) {
    $p = Join-Path $SitePackages $n
    if (Test-Path $p) {
      $bak = "$p.disabled_for_build"
      Move-Item -Force $p $bak
      $disabled += $bak
      Write-Host "Disabled .pth: $p"
    }
  }
  return $disabled
}

function Restore-ExtraPthFiles {
  param([string[]]$DisabledFiles)
  foreach ($bak in $DisabledFiles) {
    if (Test-Path $bak) {
      $orig = $bak -replace "\.disabled_for_build$", ""
      Move-Item -Force $bak $orig
      Write-Host "Restored .pth: $orig"
    }
  }
}

$SitePackages = (python -c "import site; print(site.getsitepackages()[-1])").Trim()
$null = Restore-AnyStaleDisabledPthFiles -SitePackages $SitePackages
$DisabledPth = Disable-ExtraPthFiles -SitePackages $SitePackages

try {

# Make beswarm imports lightweight during analysis (prevents pulling optional heavy deps).
$env:OCEANS_MINIMAL_PLUGINS = "1"
$env:PYTHONNOUSERSITE = "1"
$VendorPyDeps = Join-Path $RepoRoot "vendor\\pydeps"

Write-Host "[1/3] Build pandoc mermaid filter exe..."
$FilterSrc = Join-Path $RepoRoot "custom_tools/markdown_to_docx/md2doc_tools/filters/pandoc_mermaid_filter.py"
$FilterDist = Join-Path $RepoRoot "build/bin"
$FilterWork = Join-Path $RepoRoot "build/pyinstaller_filter"
$FilterSpec = Join-Path $RepoRoot "build/spec"
$FilterExe = Join-Path $FilterDist "pandoc_mermaid_filter.exe"

New-Item -ItemType Directory -Force -Path $FilterDist, $FilterWork, $FilterSpec | Out-Null

if ((Test-Path $FilterExe) -and ((Get-Item $FilterExe).LastWriteTime -ge (Get-Item $FilterSrc).LastWriteTime)) {
  Write-Host "Filter exe is up-to-date: $FilterExe"
} else {
  python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --name pandoc_mermaid_filter `
    --distpath $FilterDist `
    --workpath $FilterWork `
    --specpath $FilterSpec `
    $FilterSrc
}

if (-not (Test-Path $FilterExe)) {
  throw "Filter exe not found at: $FilterExe"
}

Write-Host "[2/3] Resolve node.exe for bundling..."
$NodeExe = $null
try {
  $NodeExe = (Get-Command node -ErrorAction Stop).Path
} catch {
  Write-Warning "node.exe not found in PATH; app will rely on user's Node installation."
}

Write-Host "[3/3] Build main desktop app..."
$env:PYTHONPATH = $VendorPyDeps
$AppDist = Join-Path $RepoRoot "dist"
$AppWork = Join-Path $RepoRoot "build/pyinstaller_app"
New-Item -ItemType Directory -Force -Path $AppWork | Out-Null

# Executable icon (quill/feather pen).
$IconPath = Join-Path $RepoRoot "assets\\oceans_paper.ico"
if (-not (Test-Path $IconPath)) {
  Write-Warning "Icon not found at $IconPath; build will use default icon."
  $IconPath = $null
}

# Clean legacy onedir output to avoid confusing users (onefile should produce a single exe).
$LegacyDir = Join-Path $AppDist "OceanS_Paper"
if (Test-Path $LegacyDir) {
  # Ensure the old app is not running and locking files in the onedir folder.
  Get-Process OceanS_Paper -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
  Start-Sleep -Milliseconds 300

  for ($i = 0; $i -lt 5; $i++) {
    try {
      Remove-Item -Recurse -Force $LegacyDir -ErrorAction Stop
      break
    } catch {
      if ($i -eq 4) { throw }
      Start-Sleep -Milliseconds 800
    }
  }
}

$LegacyExe = Join-Path $AppDist "OceanS_Paper.exe"
if (Test-Path $LegacyExe) {
  # Ensure the old onefile exe is not running and locking itself.
  Get-Process OceanS_Paper -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
  Start-Sleep -Milliseconds 300

  for ($i = 0; $i -lt 5; $i++) {
    try {
      Remove-Item -Force $LegacyExe -ErrorAction Stop
      break
    } catch {
      if ($i -eq 4) { throw }
      Start-Sleep -Milliseconds 800
    }
  }
}

# Resolve Python install root in a locale-safe way (avoid unicode decoding issues in subprocess output).
$PyExe = (Get-Command python -ErrorAction Stop).Path
$PyBase = Split-Path $PyExe -Parent
$TclDll = Join-Path $PyBase "DLLs\\tcl86t.dll"
$TkDll = Join-Path $PyBase "DLLs\\tk86t.dll"
if (-not (Test-Path $TclDll)) { Write-Warning "tcl86t.dll not found at $TclDll (tkinter may fail on target machines)" }
if (-not (Test-Path $TkDll)) { Write-Warning "tk86t.dll not found at $TkDll (tkinter may fail on target machines)" }

$ExcludeModules = @(
  # Optional/heavy deps that are not needed for the paper generator desktop app.
  "playwright",
  "gradio",
  "lightning",
  "pytorch_lightning",
  "torch",
  "torchvision",
  "torchaudio",
  "skimage",
  "scipy",
  "sympy",
  "matplotlib",
  "cv2",
  "notebook",
  "jupyter",
  "ipykernel",
  "IPython"
)

$AddData = @(
  "prompts;prompts",
  "custom_tools;custom_tools",
  "default_reference.docx;.",
  "$FilterExe;custom_tools/markdown_to_docx/md2doc_tools/filters/pandoc_mermaid_filter.exe"
)

if ($NodeExe) {
  $AddData += "$NodeExe;runtime/node/node.exe"
}

$AddDataArgs = @()
foreach ($item in $AddData) {
  $AddDataArgs += @("--add-data", $item)
}

$AddBinaryArgs = @()
if (Test-Path $TclDll) { $AddBinaryArgs += @("--add-binary", "$TclDll;.") }
if (Test-Path $TkDll) { $AddBinaryArgs += @("--add-binary", "$TkDll;.") }

$ExcludeArgs = @()
foreach ($m in $ExcludeModules) {
  $ExcludeArgs += @("--exclude-module", $m)
}

$IconArgs = @()
if ($IconPath) {
  $IconArgs += @("--icon", $IconPath)
}

python -m PyInstaller `
  --noconfirm `
  --clean `
  --paths $VendorPyDeps `
  --onefile `
  --windowed `
  --name OceanS_Paper `
  --distpath $AppDist `
  --workpath $AppWork `
  @IconArgs `
  @AddDataArgs `
  @AddBinaryArgs `
  @ExcludeArgs `
  ocean_paper_desktop.py

Write-Host "Done. Output: dist/OceanS_Paper.exe"

} finally {
  Restore-ExtraPthFiles -DisabledFiles $DisabledPth
}
