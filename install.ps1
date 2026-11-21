# One-command setup for the DistillPDF pipeline on Windows.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$venvPython = ".venv\Scripts\python.exe"
$hasUv = [bool](Get-Command uv -ErrorAction SilentlyContinue)

if (-not (Test-Path $venvPython)) {
    if ($hasUv) {
        Write-Host "Creating .venv with uv..."
        uv venv --python 3.12 .venv
    } else {
        Write-Host "Creating .venv with Python..."
        py -3 -m venv .venv
    }
}

Write-Host "Installing Python dependencies..."
if ($hasUv) {
    uv pip install --python $venvPython -e ".[dev]"
} else {
    & $venvPython -m pip install -e ".[dev]"
}

Write-Host "Registering the local PDF helper with Chrome..."
& $venvPython scripts\install_native_host.py

Write-Host "Building the extension and mobile packages..."
& $venvPython scripts\package_extension.py

Write-Host ""
Write-Host "Done. Next steps:"
Write-Host "  1. Chrome -> chrome://extensions -> Developer mode -> Load unpacked"
Write-Host "  2. Select this project's extension\ folder"
Write-Host "  3. Open a NotebookLM chat, pick answers, click Build PDF + HTML"
Write-Host "  4. Find study-notes.pdf and study-notes.html in your Downloads folder"
Write-Host ""
Write-Host "On a phone, open dist\DistillPDF-mobile-capture.zip\capture.html instead."
