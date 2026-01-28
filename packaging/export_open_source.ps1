param(
    [string]$DestinationRoot = "open_source_export",
    [string]$DestinationName = "OceanS_Paper_source",
    [switch]$Timestamped
)

$ErrorActionPreference = "Stop"

function Ensure-Dir([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path | Out-Null
    }
}

function Copy-File([string]$Src, [string]$DstDir) {
    Ensure-Dir $DstDir
    Copy-Item -LiteralPath $Src -Destination $DstDir -Force
}

function Robo-Copy([string]$SrcDir, [string]$DstDir, [string[]]$Patterns, [string[]]$ExcludeDirs) {
    Ensure-Dir $DstDir
    $args = @(
        $SrcDir,
        $DstDir
    ) + $Patterns + @(
        "/S",
        "/XO",
        "/R:1",
        "/W:1",
        "/NFL",
        "/NDL",
        "/NJH",
        "/NJS",
        "/NP"
    )
    if ($ExcludeDirs -and $ExcludeDirs.Count -gt 0) {
        $args += @("/XD") + $ExcludeDirs
    }
    & robocopy @args | Out-Null
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$dstRoot = Join-Path $repoRoot $DestinationRoot
if ($Timestamped) {
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $DestinationName = $DestinationName + "_" + $timestamp
}
$dst = Join-Path $dstRoot $DestinationName

Ensure-Dir $dst

# Top-level entrypoints / build specs
Copy-File (Join-Path $repoRoot "ocean_paper_desktop.py") $dst
Copy-File (Join-Path $repoRoot "OceanS_Paper.spec") $dst

# Repo readmes (for GitHub homepage)
$rootReadmes = @("README.md", "README_EN.md")
foreach ($name in $rootReadmes) {
    $p = Join-Path $repoRoot $name
    if (Test-Path -LiteralPath $p) {
        Copy-Item -LiteralPath $p -Destination $dst -Force
    }
}
if (Test-Path -LiteralPath (Join-Path $repoRoot "LICENSE")) {
    Copy-File (Join-Path $repoRoot "LICENSE") $dst
}

# UI/runner package
Robo-Copy (Join-Path $repoRoot "paper_app") (Join-Path $dst "paper_app") @("*.py", "*.md") @("__pycache__")

# Prompts (Markdown only)
Robo-Copy (Join-Path $repoRoot "prompts") (Join-Path $dst "prompts") @("*.md") @("__pycache__", ".git")

# Core framework (Python-first)
Robo-Copy (Join-Path $repoRoot "beswarm") (Join-Path $dst "beswarm") @("*.py", "*.md", "*.json", "*.yml", "*.yaml", "*.toml") @("__pycache__", ".beswarm")

# Custom tools (copy source/docs, exclude heavy third-party runtimes)
$excludeHeavy = @(
    "__pycache__",
    "node_modules",
    "pandoc",
    "graphviz",
    ".venv",
    "dist",
    "build"
)
Robo-Copy (Join-Path $repoRoot "custom_tools") (Join-Path $dst "custom_tools") @("*.py", "*.md", "*.json", "*.txt", "*.yml", "*.yaml", "*.toml") $excludeHeavy

# Packaging scripts
Robo-Copy (Join-Path $repoRoot "packaging") (Join-Path $dst "packaging") @("*.ps1", "*.md") @("__pycache__")

# Assets
Robo-Copy (Join-Path $repoRoot "assets") (Join-Path $dst "assets") @("*.ico", "*.png", "*.svg", "*.md") @("__pycache__")

# Bundled Windows executable + its distribution readmes (large file).
$distSrcDir = Join-Path $repoRoot "dist"
$distDstDir = Join-Path $dst "dist"
if (Test-Path -LiteralPath $distSrcDir) {
    Ensure-Dir $distDstDir
    $exe = Join-Path $distSrcDir "OceanS_Paper.exe"
    if (Test-Path -LiteralPath $exe) {
        Copy-Item -LiteralPath $exe -Destination $distDstDir -Force
    }
    $distReadmes = @("README.zh-CN.md", "README.en.md")
    foreach ($name in $distReadmes) {
        $p = Join-Path $distSrcDir $name
        if (Test-Path -LiteralPath $p) {
            Copy-Item -LiteralPath $p -Destination $distDstDir -Force
        }
    }
}

# Optional: include default_reference.docx only if you have redistribution rights.
Copy-File (Join-Path $repoRoot "default_reference.docx") $dst

$readme = @"
OceanS Paper Generator - Open Source Export

Exported folder:
  $dst

Included:
  - ocean_paper_desktop.py
  - paper_app/
  - beswarm/
  - custom_tools/ (source/docs only; excludes node_modules/pandoc/graphviz heavy runtimes)
  - prompts/ (*.md)
  - packaging/ (*.ps1/*.md)
  - assets/ (icons)
  - dist/OceanS_Paper.exe (Windows executable)
  - dist/README.zh-CN.md, dist/README.en.md
  - default_reference.docx (only if you have redistribution rights)

Excluded (build artifacts / caches / large third-party runtimes):
  - build/ results/ dataset/ node_modules/ vendor/pydeps
  - pandoc/ graphviz/ mermaid-cli node_modules
"@

$readmePath = Join-Path $dst "OPEN_SOURCE_EXPORT_README.txt"
$readme | Out-File -FilePath $readmePath -Encoding utf8

Write-Host ("OK: exported to " + $dst)
