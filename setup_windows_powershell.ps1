$ErrorActionPreference = "Stop"

Write-Host "Setting up Flask Library Face Login project..."

if (Test-Path ".venv") {
    Write-Host "Existing .venv found. Using it. Delete it first if you want a clean reinstall."
} else {
    $pythonCommand = $null

    if (Get-Command py -ErrorAction SilentlyContinue) {
        py -3.11 --version *> $null
        if ($LASTEXITCODE -eq 0) {
            $pythonCommand = "py -3.11"
        } else {
            py -3.12 --version *> $null
            if ($LASTEXITCODE -eq 0) {
                $pythonCommand = "py -3.12"
            }
        }
    }

    if (-not $pythonCommand) {
        $pythonCommand = "python"
    }

    Write-Host "Creating virtual environment with: $pythonCommand"
    Invoke-Expression "$pythonCommand -m venv .venv"
}

$venvPython = ".\.venv\Scripts\python.exe"

& $venvPython -m pip install --upgrade pip setuptools wheel
& $venvPython -m pip install -r requirements.txt

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
}

& $venvPython -m flask --app run.py init-db
& $venvPython -m flask --app run.py seed

Write-Host ""
Write-Host "Setup complete. Start the app with:"
Write-Host "$venvPython -m flask --app run.py run --debug"
