$ErrorActionPreference = "Stop"

Write-Host "Creating/using Conda environment: library-face"

if (-not (Get-Command conda -ErrorAction SilentlyContinue)) {
    throw "Conda was not found. Open Anaconda Prompt or a PowerShell where Miniconda is initialized."
}

conda create -n library-face python=3.11 -y
conda activate library-face

python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env" -Force
}

python -m flask --app run.py init-db
python -m flask --app run.py seed

Write-Host ""
Write-Host "Setup complete. Start the app with:"
Write-Host "conda activate library-face"
Write-Host "python -m flask --app run.py run --debug"
