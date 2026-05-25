$ErrorActionPreference = "Stop"

$BundledPython = "C:\Users\12774\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$LocalPython = "python"

if (Test-Path $BundledPython) {
    & $BundledPython ".\src\aoao_live_console.py"
} else {
    & $LocalPython ".\src\aoao_live_console.py"
}
