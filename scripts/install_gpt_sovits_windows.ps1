Param(
    [string]$RepoPath = "",
    [string]$CondaRoot = "C:\tmp\aoao-gpt-sovits\miniforge3",
    [string]$EnvPath = "C:\tmp\aoao-gpt-sovits\envs\GPTSoVits",
    [ValidateSet("CU126", "CU128", "CPU")]
    [string]$Device = "CU128",
    [ValidateSet("HF", "HF-Mirror", "ModelScope")]
    [string]$Source = "ModelScope",
    [switch]$DownloadUVR5
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
if (-not $RepoPath) {
    $RepoPath = Join-Path $projectRoot "vendor\GPT-SoVITS"
}

$installerDir = Join-Path $projectRoot "installer"
$installerPath = Join-Path $installerDir "Miniforge3-Windows-x86_64.exe"
$condaExe = Join-Path $CondaRoot "Scripts\conda.exe"

New-Item -ItemType Directory -Force -Path $installerDir | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $EnvPath) | Out-Null

if (-not (Test-Path $RepoPath)) {
    throw "GPT-SoVITS repo not found: $RepoPath"
}

if (-not (Test-Path $condaExe)) {
    if (-not (Test-Path $installerPath)) {
        Write-Host "[GPT-SoVITS] Downloading Miniforge installer..."
        Invoke-WebRequest `
            -Uri "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Windows-x86_64.exe" `
            -OutFile $installerPath
    }

    Write-Host "[GPT-SoVITS] Installing Miniforge into $CondaRoot ..."
    $proc = Start-Process `
        -FilePath $installerPath `
        -ArgumentList @("/InstallationType=JustMe", "/RegisterPython=0", "/S", "/D=$CondaRoot") `
        -Wait `
        -PassThru `
        -WindowStyle Hidden
    if ($proc.ExitCode -ne 0) {
        throw "Miniforge installer failed with exit code $($proc.ExitCode)"
    }
}

if (-not (Test-Path $EnvPath)) {
    Write-Host "[GPT-SoVITS] Creating Python 3.10 conda environment..."
    & $condaExe create -y -p $EnvPath python=3.10
}

Write-Host "[GPT-SoVITS] Running official install.ps1 with Device=$Device Source=$Source ..."
Push-Location $RepoPath
try {
    $installArgs = @(
        "run", "-p", $EnvPath,
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", "install.ps1",
        "-Device", $Device,
        "-Source", $Source
    )
    if ($DownloadUVR5) {
        $installArgs += "-DownloadUVR5"
    }
    & $condaExe @installArgs
}
finally {
    Pop-Location
}

Write-Host "[GPT-SoVITS] Installation complete."
Write-Host "[GPT-SoVITS] Start API with:"
Write-Host "  powershell -ExecutionPolicy Bypass -File scripts\start_gpt_sovits_api.ps1 -PythonPath `"$EnvPath\python.exe`""
