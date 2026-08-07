# Current-main Windows recovery matrix for the source experiment.
# Carrier rerun after base-ref boundary repair.
param(
    [Parameter(Mandatory = $true)][string]$UvPath,
    [Parameter(Mandatory = $true)][string]$Root
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

Remove-Item -Recurse -Force $Root -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $Root | Out-Null

$env:UV_TOOL_DIR = Join-Path $Root 'tools'
$env:UV_TOOL_BIN_DIR = Join-Path $Root 'bin'
$env:UV_CACHE_DIR = Join-Path $Root 'cache'
$env:UV_NO_PROGRESS = '1'
New-Item -ItemType Directory -Force $env:UV_TOOL_BIN_DIR | Out-Null

$transcript = Join-Path $Root 'recovery-transcript.txt'
function Record([string]$Text) {
    $Text | Tee-Object -FilePath $transcript -Append | Write-Host
}

function Invoke-Uv([string[]]$Arguments) {
    $output = (& $UvPath @Arguments 2>&1 | Out-String).TrimEnd()
    $code = $LASTEXITCODE
    Record ("> uv " + ($Arguments -join ' '))
    Record ("exit=$code")
    Record $output
    return [pscustomobject]@{ Code = $code; Output = $output }
}

$install = Invoke-Uv @('tool', 'install', 'ruff==0.9.1')
if ($install.Code -ne 0) { throw 'initial ruff 0.9.1 install failed' }

$publicExe = Join-Path $env:UV_TOOL_BIN_DIR 'ruff.exe'
$toolExe = Join-Path $env:UV_TOOL_DIR 'ruff\Scripts\ruff.exe'
$receipt = Join-Path $env:UV_TOOL_DIR 'ruff\uv-receipt.toml'
$marker = Join-Path $env:UV_TOOL_DIR 'ruff\.uv-entrypoints-incomplete'
foreach ($path in @($publicExe, $toolExe, $receipt)) {
    if (-not (Test-Path $path)) { throw "expected path missing: $path" }
}

$before = (& $publicExe --version 2>&1 | Out-String).Trim()
Record "public-before=$before"
if ($before -notmatch '0\.9\.1') { throw "unexpected initial public ruff version: $before" }
$beforeHash = (Get-FileHash -Algorithm SHA256 $publicExe).Hash

# Healthy NoOp is a negative control: it must neither create a recovery marker nor rewrite the
# public executable.
$healthy = Invoke-Uv @('tool', 'upgrade', 'ruff')
if ($healthy.Code -ne 0) { throw 'healthy no-op upgrade failed' }
if ($healthy.Output -notmatch 'Nothing to upgrade') { throw 'healthy no-op did not remain a no-op' }
if (Test-Path $marker) { throw 'healthy no-op unexpectedly created a recovery marker' }
$healthyHash = (Get-FileHash -Algorithm SHA256 $publicExe).Hash
if ($healthyHash -ne $beforeHash) { throw 'healthy no-op rewrote the public executable' }
Record 'healthy-noop-preserved-entrypoint=true'

$receiptText = Get-Content -Raw $receipt
$updatedReceipt = $receiptText.Replace('==0.9.1', '==0.9.2')
if ($updatedReceipt -eq $receiptText) { throw 'receipt did not contain expected ==0.9.1 requirement' }
if (($updatedReceipt.Split('==0.9.2').Count - 1) -ne 1) { throw 'receipt version replacement was not unique' }
Set-Content -NoNewline -Encoding utf8 $receipt $updatedReceipt
Record 'receipt target changed to 0.9.2'

$lock = [System.IO.File]::Open(
    $publicExe,
    [System.IO.FileMode]::Open,
    [System.IO.FileAccess]::Read,
    [System.IO.FileShare]::None
)
try {
    $first = Invoke-Uv @('tool', 'upgrade', 'ruff')
    if ($first.Code -eq 0) { throw 'expected first upgrade to fail while public executable is locked' }
    if ($first.Output -notmatch 'Failed to install entrypoint|failed to copy file') {
        throw "first upgrade failed for unexpected reason: $($first.Output)"
    }
    if (-not (Test-Path $marker)) { throw 'publication failure did not leave recovery marker' }
    Record 'marker-after-failure=true'
}
finally {
    $lock.Dispose()
}

$envAfterFailure = (& $toolExe --version 2>&1 | Out-String).Trim()
$publicAfterFailure = (& $publicExe --version 2>&1 | Out-String).Trim()
Record "environment-after-failure=$envAfterFailure"
Record "public-after-failure=$publicAfterFailure"
if ($envAfterFailure -notmatch '0\.9\.2') { throw 'tool environment was not upgraded to 0.9.2' }
if ($publicAfterFailure -notmatch '0\.9\.1') { throw 'public executable did not remain stale after locked copy failure' }

$second = Invoke-Uv @('tool', 'upgrade', 'ruff')
if ($second.Code -ne 0) { throw 'recovery upgrade failed after releasing executable lock' }
if ($second.Output -match 'Nothing to upgrade') { throw 'marked no-op incorrectly reported Nothing to upgrade' }
if ($second.Output -notmatch 'Repaired tool entrypoints') {
    throw "recovery was not reported: $($second.Output)"
}
if (Test-Path $marker) { throw 'recovery marker remained after successful finalization' }

$publicAfterSecond = (& $publicExe --version 2>&1 | Out-String).Trim()
Record "public-after-recovery=$publicAfterSecond"
if ($publicAfterSecond -notmatch '0\.9\.2') { throw 'public executable was not repaired to 0.9.2' }

Record 'RECOVERED: marked publication failure self-healed on the next no-op upgrade'
