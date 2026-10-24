[CmdletBinding()]
param(
    [string]$Python,
    [switch]$SkipDependencyInstall
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$buildEnvironment = Join-Path $projectRoot ".build-env"
$buildPython = Join-Path $buildEnvironment "Scripts\python.exe"

function Resolve-BasePython {
    if ($Python) {
        $resolved = Resolve-Path -LiteralPath $Python -ErrorAction Stop
        return [PSCustomObject]@{
            Executable = $resolved.Path
            Arguments = @()
        }
    }

    $localBuildPython = Join-Path $projectRoot ".build-python\python.exe"
    if (Test-Path -LiteralPath $localBuildPython) {
        return [PSCustomObject]@{
            Executable = $localBuildPython
            Arguments = @()
        }
    }

    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($launcher) {
        return [PSCustomObject]@{
            Executable = $launcher.Source
            Arguments = @("-3")
        }
    }

    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        return [PSCustomObject]@{
            Executable = $pythonCommand.Source
            Arguments = @()
        }
    }

    throw "Nie znaleziono Pythona. Zainstaluj Python 3.11 lub nowszy i uruchom skrypt ponownie."
}

function Invoke-Checked {
    param(
        [string]$Executable,
        [string[]]$Arguments
    )
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Polecenie zakonczylo sie kodem ${LASTEXITCODE}: $Executable $Arguments"
    }
}

Push-Location $projectRoot
try {
    if (-not (Test-Path -LiteralPath $buildPython)) {
        $basePython = Resolve-BasePython
        Invoke-Checked `
            -Executable $basePython.Executable `
            -Arguments ($basePython.Arguments + @("-m", "venv", $buildEnvironment))
    }

    if (-not $SkipDependencyInstall) {
        Invoke-Checked `
            -Executable $buildPython `
            -Arguments @("-m", "pip", "install", "--upgrade", "pip")
        Invoke-Checked `
            -Executable $buildPython `
            -Arguments @("-m", "pip", "install", "-r", "requirements-build.txt")
    }

    Invoke-Checked `
        -Executable $buildPython `
        -Arguments @(
            "-m", "PyInstaller",
            "--clean",
            "--noconfirm",
            "AudioOpus.spec"
        )

    $exePath = Join-Path $projectRoot "dist\Audio Opus.exe"
    if (-not (Test-Path -LiteralPath $exePath)) {
        throw "Budowanie zakonczone, ale nie znaleziono pliku: $exePath"
    }

    Write-Host ""
    Write-Host "Gotowe: $exePath" -ForegroundColor Green
    Write-Host "Dane aplikacji po pierwszym uruchomieniu: $env:APPDATA\Audio Opus"
}
finally {
    Pop-Location
}
