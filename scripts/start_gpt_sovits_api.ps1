Param(
    [string]$RepoPath = "",
    [string]$PythonPath = "C:\tmp\aoao-gpt-sovits\envs\GPTSoVits\python.exe",
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 9880,
    [string]$ConfigPath = "GPT_SoVITS/configs/tts_infer.yaml"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
if (-not $RepoPath) {
    $RepoPath = Join-Path $projectRoot "vendor\GPT-SoVITS"
}

if (-not (Test-Path $RepoPath)) {
    throw "GPT-SoVITS repo not found: $RepoPath"
}
if (-not (Test-Path $PythonPath)) {
    throw "GPT-SoVITS Python not found: $PythonPath. Run scripts\install_gpt_sovits_windows.ps1 first."
}

Push-Location $RepoPath
try {
    & $PythonPath "api_v2.py" "-a" $HostAddress "-p" $Port "-c" $ConfigPath
}
finally {
    Pop-Location
}
