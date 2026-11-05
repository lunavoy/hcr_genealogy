[CmdletBinding()]
param(
    [switch]$SkipDocker,
    [switch]$StartEscriptorium,
    [switch]$SkipTests,
    [switch]$SkipFrontendBuild
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

# Keep package and model caches on the same drive as the project.
$cacheRoot = Join-Path $root ".cache"
$env:PIP_CACHE_DIR = Join-Path $cacheRoot "pip"
$env:npm_config_cache = Join-Path $cacheRoot "npm"
$env:HF_HOME = Join-Path $cacheRoot "huggingface"
$env:TORCH_HOME = Join-Path $cacheRoot "torch"
$env:XDG_CACHE_HOME = $cacheRoot
New-Item -ItemType Directory -Force -Path @(
    $env:PIP_CACHE_DIR,
    $env:npm_config_cache,
    $env:HF_HOME,
    $env:TORCH_HOME
) | Out-Null

function Require-Command([string]$Name, [string]$InstallHint) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Componente ausente: $Name. $InstallHint"
    }
}

function Invoke-Checked([string]$File, [string[]]$Arguments, [string]$WorkingDirectory = $root) {
    Push-Location $WorkingDirectory
    try {
        & $File @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "Falha ao executar $File $($Arguments -join ' ') (codigo $LASTEXITCODE)."
        }
    } finally {
        Pop-Location
    }
}

Require-Command "python" "Instale Python 3.10 ou superior e habilite-o no PATH."
Require-Command "node" "Instale Node.js 20.19 ou superior e habilite-o no PATH."
Require-Command "npm" "Instale Node.js, que inclui o npm."

$pythonVersion = (& python -c "import sys; print('%d.%d' % sys.version_info[:2])").Trim()
$versionParts = $pythonVersion.Split(".") | ForEach-Object { [int]$_ }
if (($versionParts[0] -lt 3) -or (($versionParts[0] -eq 3) -and ($versionParts[1] -lt 10))) {
    throw "Python 3.10 ou superior e necessario (encontrado $pythonVersion)."
}

$nodeMajor = [int]((& node --version).Trim().TrimStart("v").Split(".")[0])
if ($nodeMajor -lt 20) {
    throw "Node.js 20 ou superior e necessario (encontrado $((& node --version).Trim()))."
}

Write-Host "==> Criando ambiente Python"
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Invoke-Checked "python" @("-m", "venv", ".venv")
}
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
Invoke-Checked $venvPython @("-m", "pip", "install", "--upgrade", "pip")
Invoke-Checked $venvPython @("-m", "pip", "install", "-r", "requirements.txt")
Invoke-Checked $venvPython @("-m", "pip", "install", "-e", ".")

Write-Host "==> Instalando dependencias JavaScript"
Invoke-Checked "npm" @("ci") (Join-Path $root "app\frontend")
Invoke-Checked "npm" @("ci") (Join-Path $root "app\backend")

Write-Host "==> Preparando diretorios de dados e modelos"
$directories = @(
    "dataset\originals",
    "dataset\processed",
    "dataset\annotations",
    "dataset\splits",
    "models\segmentation",
    "models\recognition\base",
    "models\recognition\finetuned"
)
foreach ($directory in $directories) {
    New-Item -ItemType Directory -Force -Path (Join-Path $root $directory) | Out-Null
}

$escriptoriumAppRoot = Join-Path $root "app\escriptorium\app"
foreach ($customization in @("homepage", "contributors")) {
    $target = Join-Path $escriptoriumAppRoot $customization
    $example = Join-Path $escriptoriumAppRoot "${customization}_example"
    if (-not (Test-Path $target) -and (Test-Path $example)) {
        Copy-Item -Path $example -Destination $target -Recurse
        Write-Host "Configuracao eScriptorium criada a partir do exemplo: $target"
    }
}

$variablesFile = Join-Path $root "app\escriptorium\variables.env"
$variablesExample = Join-Path $root "app\escriptorium\variables.env_example"
if (-not (Test-Path $variablesFile)) {
    $random = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $secretBytes = New-Object byte[] 32
        $passwordBytes = New-Object byte[] 18
        $random.GetBytes($secretBytes)
        $random.GetBytes($passwordBytes)
    } finally {
        $random.Dispose()
    }
    $secret = [Convert]::ToBase64String($secretBytes)
    $password = [Convert]::ToBase64String($passwordBytes)
    $content = Get-Content $variablesExample -Raw
    $content = $content.Replace("SECRET_KEY=changeme", "SECRET_KEY=$secret")
    $content = $content.Replace("DJANGO_SU_PASSWORD=admin", "DJANGO_SU_PASSWORD=$password")
    Set-Content -Path $variablesFile -Value $content -Encoding utf8
    Write-Host "Arquivo eScriptorium criado: $variablesFile"
} else {
    Write-Host "Arquivo eScriptorium existente preservado: $variablesFile"
}

if (-not $SkipFrontendBuild) {
    Write-Host "==> Validando build do frontend"
    Invoke-Checked "npm" @("run", "build") (Join-Path $root "app\frontend")
}

if (-not $SkipTests) {
    Write-Host "==> Executando testes Python"
    Invoke-Checked $venvPython @("-m", "pytest")
}

if (-not $SkipDocker) {
    Require-Command "docker" "Instale e inicie o Docker Desktop, ou use -SkipDocker."
    $previousErrorAction = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & docker info *> $null
    $dockerExitCode = $LASTEXITCODE
    $ErrorActionPreference = $previousErrorAction
    if ($dockerExitCode -ne 0) {
        if ($StartEscriptorium) {
            throw "Docker Desktop nao esta iniciado. Inicie o engine Linux e execute novamente."
        }
        Write-Warning "Docker Desktop nao esta iniciado; componentes Docker serao iniciados depois com -StartEscriptorium."
    } else {
        $escriptoriumRoot = Join-Path $root "app\escriptorium"
        Push-Location $escriptoriumRoot
        try {
            Invoke-Checked "docker" @("compose", "config") $escriptoriumRoot
            if ($StartEscriptorium) {
                Write-Host "==> Iniciando eScriptorium"
                Invoke-Checked "docker" @("compose", "up", "-d", "--build") $escriptoriumRoot
                Invoke-Checked "docker" @("compose", "ps") $escriptoriumRoot
            }
        } finally {
            Pop-Location
        }
    }
}

Write-Host ""
Write-Host "Instalacao concluida. O projeto esta pronto para receber imagens."
Write-Host "Coloque as paginas em dataset\originals\<colecao>\."
Write-Host "Para rotular sem modelo: .\.venv\Scripts\python.exe -m recognition.htr.server --no-model"
if (-not $StartEscriptorium -and -not $SkipDocker) {
    Write-Host "eScriptorium nao foi iniciado; use -StartEscriptorium quando o Docker Desktop estiver pronto."
}
