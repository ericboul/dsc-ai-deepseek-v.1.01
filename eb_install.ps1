<#
  DCS RYZEN Copilote - installation automatique (Windows PowerShell 5.1+)
  ---------------------------------------------------------------------
  Installe TOUT ce qu'il faut pour faire tourner le copilote :
    1. Python embarque (dossier python\)
    2. Librairies (dossier libs\) + Piper (dossier piper\)   [bootstrap.py]
    3. Voix Piper par defaut + voix de l'AWACS
    4. Modele Whisper (reconnaissance vocale) pre-telecharge
    5. Fournisseur IA : DeepSeek / OpenAI / Anthropic / Ollama / compatible
       -> ecrit config.json + fichier de cle (aucune saisie dans l'interface)
    6. Pont DCS : copie des .lua dans Saved Games\DCS\Scripts (+ Hooks)
    7. Test reel de la connexion a l'API
    8. Raccourci sur le Bureau

  Usage normal : double-clic sur INSTALLER-TOUT.bat
  Usage silencieux :
    powershell -ExecutionPolicy Bypass -File eb_install.ps1 -Provider deepseek -ApiKey sk-... -NoPrompt
  Options : -Model -BaseUrl -Whisper small|base|medium -SkipModels -SkipDcs -NoPrompt -NoShortcut
#>
param(
    [string]$Provider = "",
    [string]$ApiKey = "",
    [string]$Model = "",
    [string]$BaseUrl = "",
    [string]$Whisper = "small",
    [switch]$NoPrompt,
    [switch]$SkipModels,
    [switch]$SkipDcs,
    [switch]$NoShortcut
)

$ErrorActionPreference = "Continue"
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}
$env:PYTHONIOENCODING = "utf-8"
$env:HF_HUB_DISABLE_SYMLINKS = "1"
$env:HF_HUB_DISABLE_SYMLINKS_WARNING = "1"

$root   = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
Set-Location -LiteralPath $root
$PY     = Join-Path $root "python\python.exe"
$fwd    = ($root -replace '\\', '/')
$MODELS = Join-Path $root "models"
$LOG    = Join-Path $root "EB-INSTALLATION-LOG.txt"
$script:problems = @()

function Line($t)  { Write-Host $t }
function Step($n, $t) { Write-Host ""; Write-Host ("=== [$n] " + $t + " ===") -ForegroundColor Cyan }
function Ok($t)    { Write-Host ("  [OK]   " + $t) -ForegroundColor Green }
function Info($t)  { Write-Host ("         " + $t) -ForegroundColor Gray }
function Warn($t)  { Write-Host ("  [!!]   " + $t) -ForegroundColor Yellow; $script:problems += $t }
function Err($t)   { Write-Host ("  [XX]   " + $t) -ForegroundColor Red; $script:problems += $t }

function Ask($question, $default) {
    if ($NoPrompt) { return $default }
    $a = Read-Host ("  " + $question + " [" + $default + "]")
    if ([string]::IsNullOrWhiteSpace($a)) { return $default }
    return $a.Trim()
}

function Read-Secret($prompt) {
    if ($NoPrompt) { return "" }
    Line ""
    Line ("  " + $prompt)
    $sec = Read-Host "  Cle" -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
    try   { return [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr).Trim() }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
}

function Write-KeyFile($key) {
    $f = Join-Path $env:TEMP ("ebkey_" + [guid]::NewGuid().ToString("N") + ".txt")
    [IO.File]::WriteAllText($f, $key, (New-Object Text.UTF8Encoding($false)))
    return $f
}

function Run-Py($arguments, $label) {
    & $PY $arguments
    $code = $LASTEXITCODE
    if ($code -ne 0) { Warn ("$label : code de sortie $code") }
    return $code
}

Write-Host ""
Write-Host "  ==========================================================" -ForegroundColor Cyan
Write-Host "    DCS RYZEN Copilote - installation automatique complete"   -ForegroundColor Cyan
Write-Host "  ==========================================================" -ForegroundColor Cyan
Write-Host ("    Dossier : " + $root)
Write-Host ""

try { Start-Transcript -Path $LOG -Force | Out-Null; $script:transcript = $true } catch { $script:transcript = $false }

# ------------------------------------------------------------------ 0. verifs
Step 0 "Verification du dossier"
if (-not (Test-Path (Join-Path $root "app.py"))) {
    Err "app.py introuvable : ce script doit rester dans le dossier du projet."
    exit 1
}
if (-not (Test-Path (Join-Path $root "bootstrap.py"))) {
    Err "bootstrap.py introuvable : dossier incomplet (re-clone le depot)."
    exit 1
}
Ok "projet complet"
$free = (Get-PSDrive -Name ((Get-Item $root).PSDrive.Name)).Free / 1GB
Info ("espace libre sur le disque : " + [math]::Round($free, 1) + " Go")
if ($free -lt 6) { Warn "moins de 6 Go libres : les modeles Whisper/Piper peuvent ne pas tenir" }

$net = $false
try {
    $r = Invoke-WebRequest -Uri "https://api.deepseek.com" -UseBasicParsing -TimeoutSec 20 -Method Head
    $net = $true
} catch {
    if ($_.Exception.Response) { $net = $true }   # reponse HTTP = reseau OK
}
if ($net) { Ok "connexion internet" } else { Err "pas de connexion internet : l'installation va echouer" }

# ------------------------------------------------------------------ 1. python
Step 1 "Python embarque"
if (Test-Path $PY) {
    Ok "deja installe"
} else {
    Info "telechargement de Python 3.11.9 (une fois, ~11 Mo)..."
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root "setup_python.ps1")
    if (-not (Test-Path $PY)) { Err "Python embarque absent apres setup_python.ps1"; }
}
if (Test-Path $PY) {
    $v = & $PY -c "import sys;print(sys.version.split()[0])" 2>$null
    if ($LASTEXITCODE -eq 0) { Ok ("python " + $v) } else { Err "python.exe ne repond pas" }
}

if (-not (Test-Path $PY)) {
    Line ""
    Err "Impossible de continuer sans Python. Relance INSTALLER-TOUT.bat une fois le reseau retabli."
    if ($script:transcript) { Stop-Transcript | Out-Null }
    exit 1
}

# ------------------------------------------------------------------ 2. libs + piper
Step 2 "Librairies Python et voix Piper"
$libsMarker = Join-Path $root "libs\.installed"
if (Test-Path $libsMarker) {
    Ok "librairies deja installees"
} else {
    Info "pip install (faster-whisper, flask, pygame, pywin32...) : quelques minutes, c'est normal."
    Run-Py (Join-Path $root "bootstrap.py") "bootstrap" | Out-Null
    if (Test-Path $libsMarker) { Ok "librairies installees" } else { Err "installation des librairies echouee" }
}
$piperExe = Join-Path $root "piper\piper\piper.exe"
if (Test-Path $piperExe) { Ok "Piper present" } else { Warn "Piper absent (voix Windows SAPI utilisee en repli)" }

# ------------------------------------------------------------------ 3. voix
Step 3 "Voix de synthese (une seule fois : ~60 Mo par voix)"
$voicesDir = Join-Path $root "piper\voices"
# voix francaises completes + 2 anglaises pour les personas qui parlent anglais
$voiceList = @("fr_FR-siwis-medium", "fr_FR-tom-medium", "fr_FR-upmc-medium",
               "fr_FR-mls-medium", "fr_FR-siwis-low", "fr_FR-mls_1840-low",
               "fr_FR-gilles-low", "en_US-lessac-medium", "en_GB-alan-medium")
foreach ($v in $voiceList) {
    $onnx = Join-Path $voicesDir ($v + ".onnx")
    if ((Test-Path $onnx) -and (Test-Path ($onnx + ".json"))) { Ok ($v + " deja presente"); continue }
    Info ("telechargement de la voix " + $v + " (~60 Mo)...")
    & $PY -c "import voices;print(voices.download('$v'))"
    if ($LASTEXITCODE -eq 0 -and (Test-Path $onnx)) { Ok ($v + " installee") } else { Warn ($v + " non installee") }
}

# ------------------------------------------------------------------ 4. whisper
Step 4 ("Modele Whisper : " + $Whisper)
if ($SkipModels) {
    Warn "telechargement des modeles ignore (-SkipModels)"
} else {
    New-Item -ItemType Directory -Force -Path $MODELS | Out-Null
    $wdir = ($MODELS -replace '\\', '/')
    Info "pre-telechargement (~150-500 Mo selon le modele) : la 1re dictee sera immediate."
    & $PY -c "from faster_whisper import WhisperModel; WhisperModel('$Whisper', device='cpu', compute_type='int8', download_root=r'$wdir');print('whisper pret')"
    if ($LASTEXITCODE -eq 0) { Ok "modele Whisper pret" } else { Warn "modele Whisper non pre-telecharge (il le sera au 1er usage)" }
}

# ------------------------------------------------------------------ 5. fournisseur IA
Step 5 "Cerveau (IA)"
$providers = @{
    "1" = @{ id = "deepseek";  label = "DeepSeek (recommande, cle sur platform.deepseek.com)" }
    "2" = @{ id = "openai";    label = "OpenAI (api.openai.com)" }
    "3" = @{ id = "anthropic"; label = "Anthropic Claude" }
    "4" = @{ id = "ollama";    label = "Ollama (100% local, aucune cle)" }
    "5" = @{ id = "custom";    label = "Autre API compatible OpenAI (Mistral, Groq, OpenRouter...)" }
}

if ([string]::IsNullOrWhiteSpace($Provider)) {
    if ($NoPrompt) {
        $Provider = "deepseek"
    } else {
        Line ""
        Line "  Choisis le fournisseur d'IA :"
        foreach ($k in @("1","2","3","4","5")) { Line ("   " + $k + ") " + $providers[$k].label) }
        $c = Ask "Ton choix" "1"
        if ($providers.ContainsKey($c)) { $Provider = $providers[$c].id } else { $Provider = "deepseek" }
    }
}
$Provider = $Provider.ToLower()
if (@("deepseek","openai","anthropic","ollama","custom") -notcontains $Provider) {
    Err ("fournisseur inconnu : " + $Provider); $Provider = "deepseek"
}
Ok ("fournisseur : " + $Provider)

$needsKey = ($Provider -ne "ollama")
if ($needsKey -and [string]::IsNullOrWhiteSpace($ApiKey)) {
    $existing = @{ deepseek = "deepseek_key.txt"; openai = "openai_key.txt"; anthropic = "apikey.txt"; custom = "openai_key.txt" }
    $ef = Join-Path $root $existing[$Provider]
    if ((Test-Path $ef) -and ((Get-Content -Raw $ef).Trim().Length -gt 8)) {
        Ok "cle API deja enregistree"
        $ApiKey = (Get-Content -Raw $ef).Trim()
    } elseif ($NoPrompt) {
        Warn "aucune cle API fournie : le copilote attendra une cle dans l'interface"
    } else {
        Info "Colle ta cle API (la saisie est masquee, rien ne s'affiche)."
        if ($Provider -eq "deepseek") { Info "Pas encore de cle ? https://platform.deepseek.com/api_keys" }
        $ApiKey = Read-Secret "Cle API :"
        if ([string]::IsNullOrWhiteSpace($ApiKey)) { Warn "cle vide : tu pourras la saisir dans l'interface web" }
    }
}

if ($Provider -eq "custom" -and [string]::IsNullOrWhiteSpace($BaseUrl) -and -not $NoPrompt) {
    $BaseUrl = Ask "URL de base de l'API (ex: https://api.mistral.ai/v1)" ""
}
if ([string]::IsNullOrWhiteSpace($Model) -and $Provider -eq "custom" -and -not $NoPrompt) {
    $Model = Ask "Nom du modele (ex: mistral-large-latest)" ""
}

$cfgArgs = @((Join-Path $root "eb_configure.py"), "--provider", $Provider)
if ($Model)    { $cfgArgs += @("--model", $Model) }
if ($BaseUrl)  { $cfgArgs += @("--base-url", $BaseUrl) }
$keyFile = $null
if ($ApiKey) { $keyFile = Write-KeyFile $ApiKey; $cfgArgs += @("--key-file", $keyFile) }
& $PY @cfgArgs
if ($keyFile -and (Test-Path $keyFile)) { Remove-Item $keyFile -Force -ErrorAction SilentlyContinue }
if ($LASTEXITCODE -eq 0) { Ok "config.json mis a jour" } else { Err "ecriture de config.json impossible" }

# ------------------------------------------------------------------ 6. ollama
Step 6 "Fournisseur local / Ollama"
if ($Provider -ne "ollama") {
    Ok ("non requis (fournisseur " + $Provider + ")")
} else {
    $ollamaUp = $false
    try { Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -UseBasicParsing -TimeoutSec 5 | Out-Null; $ollamaUp = $true } catch {}
    if ($ollamaUp) {
        Ok "Ollama repond deja sur localhost:11434"
    } else {
        $winget = Get-Command winget -ErrorAction SilentlyContinue
        if ($winget) {
            Info "installation d'Ollama via winget (peut demander une confirmation Windows)..."
            & winget install --id Ollama.Ollama -e --silent --accept-package-agreements --accept-source-agreements
            Start-Sleep -Seconds 5
        } else {
            Warn "winget indisponible : installe Ollama depuis https://ollama.com/download"
        }
        # relance le service si besoin (Ollama s'installe en app de session)
        for ($i = 0; $i -lt 6 -and -not $ollamaUp; $i++) {
            try { Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -UseBasicParsing -TimeoutSec 4 | Out-Null; $ollamaUp = $true } catch {}
            if (-not $ollamaUp) {
                $appExe = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama app.exe"
                if ((Test-Path $appExe) -and $i -eq 0) { Start-Process -FilePath $appExe -ErrorAction SilentlyContinue }
                Start-Sleep -Seconds 5
            }
        }
        if ($ollamaUp) { Ok "Ollama demarre" } else { Warn "Ollama ne repond pas encore : lance l'app Ollama puis relance ce script" }
    }
    if ($ollamaUp) {
        $ollamaExe = $null
        $cmdInfo = Get-Command ollama -ErrorAction SilentlyContinue
        if ($cmdInfo) { $ollamaExe = $cmdInfo.Source }
        if (-not $ollamaExe) {
            $candidate = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
            if (Test-Path $candidate) { $ollamaExe = $candidate }
        }
        $mdl = if ($Model) { $Model } else { "llama3.1" }
        if ($ollamaExe) {
            Info ("telechargement du modele " + $mdl + " (plusieurs Go selon le modele)...")
            & $ollamaExe pull $mdl
            if ($LASTEXITCODE -eq 0) { Ok ($mdl + " pret") } else { Warn ("ollama pull " + $mdl + " a echoue") }
        } else {
            Warn ("commande ollama introuvable : lance 'ollama pull " + $mdl + "' apres installation")
        }
    }
}

# ------------------------------------------------------------------ 7. pont DCS
Step 7 "Pont DCS (fichiers .lua dans Saved Games)"
if ($SkipDcs) {
    Warn "installation du pont DCS ignoree (-SkipDcs)"
} else {
    $sgRoot = Join-Path $env:USERPROFILE "Saved Games"
    $variants = @()
    foreach ($n in @("DCS", "DCS.openbeta", "DCS.dcs_serverrelease")) {
        $p = Join-Path $sgRoot $n
        if (Test-Path $p) { $variants += $p }
    }
    if ($variants.Count -eq 0) {
        Warn "aucun dossier DCS dans Saved Games : lance DCS une fois, puis relance l'installateur"
    }
    foreach ($v in $variants) {
        $scripts = Join-Path $v "Scripts"
        $hooks   = Join-Path $scripts "Hooks"
        $bak     = Join-Path $scripts "eb_backup"
        New-Item -ItemType Directory -Force -Path $scripts, $hooks, $bak | Out-Null

        $expLua = Join-Path $scripts "Export.lua"
        if (Test-Path $expLua) {
            if (-not (Test-Path (Join-Path $bak "Export.lua.bak"))) {
                Copy-Item $expLua (Join-Path $bak "Export.lua.bak") -Force
            }
            $content = Get-Content -Raw -LiteralPath $expLua
            if ($content -notmatch "dcs_claude_export") {
                Add-Content -LiteralPath $expLua -Value "`r`ndofile(lfs.writedir()..[[Scripts\dcs_claude_export.lua]])" -Encoding ASCII
                Ok ("Export.lua complete (" + $v + ")")
            } else {
                Ok ("Export.lua deja pret (" + $v + ")")
            }
        } else {
            $hdr = "-- Export.lua cree par l'installateur DCS RYZEN Copilote`r`ndofile(lfs.writedir()..[[Scripts\dcs_claude_export.lua]])`r`n"
            [IO.File]::WriteAllText($expLua, $hdr, (New-Object Text.ASCIIEncoding))
            Ok ("Export.lua cree (" + $v + ")")
        }

        Copy-Item (Join-Path $root "dcs_claude_export.lua") (Join-Path $scripts "dcs_claude_export.lua") -Force
        $ctlDst = Join-Path $hooks "dcs_claude_control.lua"
        if (Test-Path $ctlDst) { Copy-Item $ctlDst (Join-Path $bak "dcs_claude_control.lua.bak") -Force }
        Copy-Item (Join-Path $root "dcs_claude_control.lua") $ctlDst -Force
        Ok ("telemetrie + hook installes (" + (Split-Path $v -Leaf) + ")")
    }
}

# ------------------------------------------------------------------ 8. test API
Step 8 "Test de la connexion a l'IA"
if ($Provider -ne "ollama" -and [string]::IsNullOrWhiteSpace($ApiKey)) {
    Warn "test ignore : aucune cle API"
} else {
    Info "envoi d'un mini message au modele..."
    & $PY (Join-Path $root "eb_check_llm.py")
    if ($LASTEXITCODE -eq 0) { Ok "l'IA repond" } else { Warn "l'IA ne repond pas encore (cle/credit/reseau) - tu peux retester dans l'interface" }
}

# ------------------------------------------------------------------ 9. raccourci
Step 9 "Raccourci sur le Bureau"
if ($NoShortcut) {
    Info "ignore (-NoShortcut)"
} else {
    try {
        $ws = New-Object -ComObject WScript.Shell
        $desktop = [Environment]::GetFolderPath("Desktop")
        $lnk = Join-Path $desktop "DCS RYZEN Copilote.lnk"
        $s = $ws.CreateShortcut($lnk)
        $exe = Join-Path $root "DCS-RYZEN-Copilote.exe"
        $s.TargetPath = if (Test-Path $exe) { $exe } else { Join-Path $root "DCS-RYZEN-Copilote.bat" }
        $s.WorkingDirectory = $root
        $ico = if (Test-Path $exe) { $exe } else { Join-Path $root "python\python.exe" }
        if (Test-Path $ico) { $s.IconLocation = $ico + ",0" }
        $s.Description = "Copilote vocal IA pour DCS World"
        $s.Save()
        Ok ("raccourci cree : " + $lnk)

        # raccourci direct vers la page de configuration (aucune fenetre noire)
        $urlFile = Join-Path $desktop "EB DCS RYZEN Copilote - Configuration.url"
        $content = "[InternetShortcut]`r`nURL=http://127.0.0.1:5001`r`nIconIndex=0`r`n"
        [IO.File]::WriteAllText($urlFile, $content, (New-Object Text.ASCIIEncoding))
        Ok ("raccourci configuration cree : " + $urlFile)
    } catch { Warn ("raccourci non cree : " + $_.Exception.Message) }
}

# ------------------------------------------------------------------ resume
Write-Host ""
Write-Host "  ==========================================================" -ForegroundColor Cyan
if ($script:problems.Count -eq 0) {
    Write-Host "    INSTALLATION TERMINEE - tout est pret" -ForegroundColor Green
} else {
    Write-Host ("    INSTALLATION TERMINEE avec " + $script:problems.Count + " avertissement(s)") -ForegroundColor Yellow
    foreach ($p in $script:problems) { Write-Host ("      - " + $p) -ForegroundColor Yellow }
}
Write-Host "  ==========================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Pour voler : double-clic sur DCS-RYZEN-Copilote.bat (ou le raccourci du Bureau)."
Write-Host "  L'interface s'ouvre sur http://127.0.0.1:5001 - le copilote demarre en meme temps."
Write-Host ""
Info ("journal complet : " + $LOG)

if ($script:transcript) { try { Stop-Transcript | Out-Null } catch {} }

if (-not $NoPrompt) {
    Line ""
    $go = Read-Host "  Lancer maintenant ? (O/n)"
    if ($go -eq "" -or $go -match "^[oOyY]") {
        & (Join-Path $root "DCS-RYZEN-Copilote.bat")
    }
}
if ($script:problems.Count -gt 0) { exit 2 }
exit 0
