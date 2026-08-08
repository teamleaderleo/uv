param(
    [Parameter(Mandatory = $true)][string]$UvPath,
    [Parameter(Mandatory = $true)][string]$Root
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
Remove-Item -Recurse -Force $Root -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $Root | Out-Null
$Transcript = Join-Path $Root 'recovery-transcript.txt'
[System.IO.File]::WriteAllText($Transcript, '')

function Record([string]$Text) {
    $Text | Tee-Object -FilePath $Transcript -Append | Write-Host
}

function Set-Scenario([string]$Name) {
    $scenario = Join-Path $Root $Name
    Remove-Item -Recurse -Force $scenario -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force $scenario | Out-Null
    $env:UV_TOOL_DIR = Join-Path $scenario 'tools'
    $env:UV_TOOL_BIN_DIR = Join-Path $scenario 'bin'
    $env:UV_CACHE_DIR = Join-Path $scenario 'cache'
    $env:UV_NO_PROGRESS = '1'
    New-Item -ItemType Directory -Force $env:UV_TOOL_BIN_DIR | Out-Null
    Record "===== scenario=$Name ====="
    return $scenario
}

function Invoke-Uv([string[]]$Arguments) {
    $output = (& $UvPath @Arguments 2>&1 | Out-String).TrimEnd()
    $code = $LASTEXITCODE
    Record ("> uv " + ($Arguments -join ' '))
    Record ("exit=$code")
    Record $output
    return [pscustomobject]@{ Code = $code; Output = $output }
}

function Paths() {
    return [pscustomobject]@{
        PublicExe = Join-Path $env:UV_TOOL_BIN_DIR 'ruff.exe'
        ToolExe = Join-Path $env:UV_TOOL_DIR 'ruff\Scripts\ruff.exe'
        PythonExe = Join-Path $env:UV_TOOL_DIR 'ruff\Scripts\python.exe'
        Receipt = Join-Path $env:UV_TOOL_DIR 'ruff\uv-receipt.toml'
        Lock = Join-Path $env:UV_TOOL_DIR 'ruff\uv.lock'
        Marker = Join-Path $env:UV_TOOL_DIR 'ruff\.uv-entrypoints-incomplete'
    }
}

function Move-ReceiptTarget([string]$Receipt) {
    $receiptText = Get-Content -Raw $Receipt
    $updatedReceipt = $receiptText.Replace('==0.9.1', '==0.9.2')
    if ($updatedReceipt -eq $receiptText) { throw 'receipt did not contain expected ==0.9.1 requirement' }
    if (($updatedReceipt.Split('==0.9.2').Count - 1) -ne 1) { throw 'receipt version replacement was not unique' }
    Set-Content -NoNewline -Encoding utf8 $Receipt $updatedReceipt
}

function Cause-Locked-PublicationFailure($Paths, [string[]]$GlobalArgs = @()) {
    $lock = [System.IO.File]::Open(
        $Paths.PublicExe,
        [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read,
        [System.IO.FileShare]::None
    )
    try {
        $first = Invoke-Uv ($GlobalArgs + @('tool', 'upgrade', 'ruff'))
        if ($first.Code -eq 0) { throw 'expected upgrade to fail while public executable is locked' }
        if ($first.Output -notmatch 'Failed to install entrypoint|failed to copy file') {
            throw "upgrade failed for unexpected reason: $($first.Output)"
        }
        if (-not (Test-Path $Paths.Marker)) { throw 'publication failure did not leave recovery marker' }
    }
    finally {
        $lock.Dispose()
    }

    $envVersion = (& $Paths.ToolExe --version 2>&1 | Out-String).Trim()
    $publicVersion = (& $Paths.PublicExe --version 2>&1 | Out-String).Trim()
    Record "environment-after-failure=$envVersion"
    Record "public-after-failure=$publicVersion"
    if ($envVersion -notmatch '0\.9\.2') { throw 'tool environment was not upgraded to 0.9.2' }
    if ($publicVersion -notmatch '0\.9\.1') { throw 'public executable did not remain stale at 0.9.1' }
}

# Scenario 1: healthy no-op remains untouched; a marked no-op repairs the public native executable.
$scenario = Set-Scenario 'noop'
$install = Invoke-Uv @('tool', 'install', 'ruff==0.9.1')
if ($install.Code -ne 0) { throw 'noop scenario install failed' }
$p = Paths
$beforeHash = (Get-FileHash -Algorithm SHA256 $p.PublicExe).Hash
$healthy = Invoke-Uv @('tool', 'upgrade', 'ruff')
if ($healthy.Code -ne 0 -or $healthy.Output -notmatch 'Nothing to upgrade') { throw 'healthy no-op changed behavior' }
if (Test-Path $p.Marker) { throw 'healthy no-op unexpectedly created recovery marker' }
if ((Get-FileHash -Algorithm SHA256 $p.PublicExe).Hash -ne $beforeHash) { throw 'healthy no-op rewrote public executable' }
Move-ReceiptTarget $p.Receipt
Cause-Locked-PublicationFailure $p
$repair = Invoke-Uv @('tool', 'upgrade', 'ruff')
if ($repair.Code -ne 0) { throw 'marked no-op recovery failed' }
if ($repair.Output -match 'Nothing to upgrade') { throw 'marked no-op incorrectly reported Nothing to upgrade' }
if ($repair.Output -notmatch 'Repaired tool entrypoints') { throw 'marked no-op did not report repair' }
if (Test-Path $p.Marker) { throw 'marker remained after no-op repair' }
if ((& $p.PublicExe --version 2>&1 | Out-String) -notmatch '0\.9\.2') { throw 'no-op repair did not publish Ruff 0.9.2' }
Record 'noop-recovery=true'

# Scenario 2: a pending repair must not wait merely because the next invocation also upgrades a
# dependency. Ruff is native and supplies the stale public executable; click is an explicit tool
# dependency that we downgrade after the failed publication to force UpgradeDependencies.
$scenario = Set-Scenario 'dependency'
$install = Invoke-Uv @('tool', 'install', 'ruff==0.9.1', '--with', 'click<8.2')
if ($install.Code -ne 0) { throw 'dependency scenario install failed' }
$p = Paths
Move-ReceiptTarget $p.Receipt
Cause-Locked-PublicationFailure $p

$downgrade = Invoke-Uv @('pip', 'install', '--python', $p.PythonExe, 'click==8.1.7')
if ($downgrade.Code -ne 0) { throw 'failed to downgrade click inside tool environment' }
$clickBefore = (& $p.PythonExe -c 'import click; print(click.__version__)' 2>&1 | Out-String).Trim()
Record "click-before-recovery=$clickBefore"
if ($clickBefore -notmatch '^8\.1\.7') { throw "click downgrade did not take effect: $clickBefore" }

$repairWithDependency = Invoke-Uv @('tool', 'upgrade', 'ruff')
if ($repairWithDependency.Code -ne 0) { throw 'dependency-upgrade recovery invocation failed' }
if ($repairWithDependency.Output -notmatch 'Repaired tool entrypoints') {
    throw 'dependency-upgrade path did not report entrypoint repair'
}
if ($repairWithDependency.Output -match 'Nothing to upgrade') {
    throw 'dependency-upgrade recovery incorrectly reported Nothing to upgrade'
}
if (Test-Path $p.Marker) { throw 'marker remained after dependency-upgrade repair' }
$publicAfter = (& $p.PublicExe --version 2>&1 | Out-String).Trim()
$clickAfter = (& $p.PythonExe -c 'import click; print(click.__version__)' 2>&1 | Out-String).Trim()
Record "public-after-dependency-recovery=$publicAfter"
Record "click-after-recovery=$clickAfter"
if ($publicAfter -notmatch '0\.9\.2') { throw 'dependency-upgrade path did not repair Ruff public executable' }
if ($clickAfter -notmatch '^8\.1\.8') { throw "dependency-upgrade path did not upgrade click to 8.1.8: $clickAfter" }
Record 'dependency-upgrade-and-recovery=true'

# Scenario 3: the same late-publication failure must recover while tool-install locks are enabled,
# and the recovered metadata generation must contain the upgraded root version.
$scenario = Set-Scenario 'tool-lock'
$previewArgs = @('--preview-features', 'tool-install-locks')
$install = Invoke-Uv ($previewArgs + @('tool', 'install', 'ruff==0.9.1'))
if ($install.Code -ne 0) { throw 'tool-lock scenario install failed' }
$p = Paths
if (-not (Test-Path $p.Lock)) { throw 'tool-lock install did not create uv.lock' }
Move-ReceiptTarget $p.Receipt
Cause-Locked-PublicationFailure $p $previewArgs
$repairWithLock = Invoke-Uv ($previewArgs + @('tool', 'upgrade', 'ruff'))
if ($repairWithLock.Code -ne 0) { throw 'tool-lock recovery failed' }
if ($repairWithLock.Output -notmatch 'Repaired tool entrypoints') { throw 'tool-lock recovery did not report repair' }
if ($repairWithLock.Output -match 'Nothing to upgrade') { throw 'tool-lock recovery incorrectly reported Nothing to upgrade' }
if (Test-Path $p.Marker) { throw 'marker remained after tool-lock recovery' }
if ((& $p.PublicExe --version 2>&1 | Out-String) -notmatch '0\.9\.2') { throw 'tool-lock recovery did not publish Ruff 0.9.2' }
$lockText = Get-Content -Raw $p.Lock
if ($lockText -notmatch 'version = "0\.9\.2"') { throw 'tool lock did not record Ruff 0.9.2 after recovery' }
Record 'tool-lock-recovery=true'

# Scenario 4: a failure after one of two public entrypoints was already replaced must leave the
# marker authoritative for the whole entrypoint set. Corrupt the second path after releasing the
# sharing-denied handle, then require recovery to restore both public files from the current tool
# environment.
$scenario = Set-Scenario 'multi-entrypoint'
$install = Invoke-Uv @('tool', 'install', 'black==24.2.0')
if ($install.Code -ne 0) { throw 'multi-entrypoint scenario install failed' }
$blackDir = Join-Path $env:UV_TOOL_DIR 'black'
$blackReceipt = Join-Path $blackDir 'uv-receipt.toml'
$blackMarker = Join-Path $blackDir '.uv-entrypoints-incomplete'
$publicBlack = Join-Path $env:UV_TOOL_BIN_DIR 'black.exe'
$publicBlackd = Join-Path $env:UV_TOOL_BIN_DIR 'blackd.exe'
$toolBlack = Join-Path $blackDir 'Scripts\black.exe'
$toolBlackd = Join-Path $blackDir 'Scripts\blackd.exe'
$receiptText = Get-Content -Raw $blackReceipt
$updatedReceipt = $receiptText.Replace('==24.2.0', '==24.3.0')
if ($updatedReceipt -eq $receiptText) { throw 'black receipt did not contain expected ==24.2.0 requirement' }
if (($updatedReceipt.Split('==24.3.0').Count - 1) -ne 1) { throw 'black receipt version replacement was not unique' }
Set-Content -NoNewline -Encoding utf8 $blackReceipt $updatedReceipt

$blackdLock = [System.IO.File]::Open(
    $publicBlackd,
    [System.IO.FileMode]::Open,
    [System.IO.FileAccess]::Read,
    [System.IO.FileShare]::None
)
try {
    $first = Invoke-Uv @('tool', 'upgrade', 'black')
    if ($first.Code -eq 0) { throw 'expected multi-entrypoint upgrade to fail while blackd is locked' }
    if ($first.Output -notmatch 'Failed to install entrypoint|failed to copy file') {
        throw "multi-entrypoint upgrade failed for unexpected reason: $($first.Output)"
    }
    if (-not (Test-Path $blackMarker)) { throw 'multi-entrypoint failure did not leave recovery marker' }
}
finally {
    $blackdLock.Dispose()
}

$environmentBlackVersion = (& $toolBlack --version 2>&1 | Out-String).Trim()
Record "black-environment-after-failure=$environmentBlackVersion"
if ($environmentBlackVersion -notmatch '24\.3\.0') { throw 'black environment was not upgraded to 24.3.0' }
if (-not (Test-Path $publicBlack)) { throw 'first public Black entrypoint disappeared after partial publication' }
if (-not (Test-Path $publicBlackd)) { throw 'locked Blackd entrypoint disappeared unexpectedly' }
[System.IO.File]::WriteAllBytes($publicBlackd, [System.Text.Encoding]::ASCII.GetBytes('FIELDWORK-STALE'))
$staleHash = (Get-FileHash -Algorithm SHA256 $publicBlackd).Hash

$multiRepair = Invoke-Uv @('tool', 'upgrade', 'black')
if ($multiRepair.Code -ne 0) { throw 'multi-entrypoint recovery failed' }
if ($multiRepair.Output -notmatch 'Repaired tool entrypoints') { throw 'multi-entrypoint recovery did not report repair' }
if ($multiRepair.Output -match 'Nothing to upgrade') { throw 'multi-entrypoint recovery incorrectly reported Nothing to upgrade' }
if (Test-Path $blackMarker) { throw 'marker remained after multi-entrypoint recovery' }
$publicBlackHash = (Get-FileHash -Algorithm SHA256 $publicBlack).Hash
$publicBlackdHash = (Get-FileHash -Algorithm SHA256 $publicBlackd).Hash
$toolBlackHash = (Get-FileHash -Algorithm SHA256 $toolBlack).Hash
$toolBlackdHash = (Get-FileHash -Algorithm SHA256 $toolBlackd).Hash
if ($publicBlackHash -ne $toolBlackHash) { throw 'recovery did not restore black.exe from current environment' }
if ($publicBlackdHash -eq $staleHash) { throw 'recovery left the deliberately stale blackd.exe in place' }
if ($publicBlackdHash -ne $toolBlackdHash) { throw 'recovery did not restore blackd.exe from current environment' }
Record 'multi-entrypoint-recovery=true'

Record 'VALIDATED: recovery covers NoOp, UpgradeDependencies, tool locks, and partial multi-entrypoint publication'
