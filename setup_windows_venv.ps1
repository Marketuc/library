$ErrorActionPreference = "Stop"

Write-Host "Creating a local .venv. This requires Python 3.10, 3.11, or 3.12 to be installed."

$pythonCommand = $null
foreach ($candidate in @("py -3.12", "py -3.11", "py -3.10", "python")) {
    try {
        Invoke-Expression "$candidate --version" *> $null
        if ($LASTEXITCODE -eq 0) {
            $pythonCommand = $candidate
            break
        }
    } catch {}
}

if (-not $pythonCommand) {
    throw "No usable Python command found. Install Python 3.11 or use setup_windows_conda.ps1 instead."
}

if (Test-Path ".venv") {
    Remove-Item -Recurse -Force ".venv"
}

Invoke-Expression "$pythonCommand -m venv .venv"
$venvPython = ".\.venv\Scripts\python.exe"

& $venvPython -m pip install --upgrade pip setuptools wheel
& $venvPython -m pip install -r requirements.txt

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env" -Force
}

& $venvPython -m flask --app run.py init-db
& $venvPython -m flask --app run.py seed

Write-Host ""
Write-Host "Setup complete. Start the app with:"
Write-Host "$venvPython -m flask --app run.py run --debug"
