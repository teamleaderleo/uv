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

$transcript = Join-Path $Root 'probe-transcript.txt'
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
foreach ($path in @($publicExe, $toolExe, $receipt)) {
    if (-not (Test-Path $path)) { throw "expected path missing: $path" }
}

$before = (& $publicExe --version 2>&1 | Out-String).Trim()
Record "public-before=$before"
if ($before -notmatch '0\.9\.1') { throw "unexpected initial public ruff version: $before" }

$receiptText = Get-Content -Raw $receipt
$updatedReceipt = $receiptText.Replace('==0.9.1', '==0.9.2')
if ($updatedReceipt -eq $receiptText) { throw 'receipt did not contain the expected ==0.9.1 requirement' }
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
    if ($first.Code -eq 0) { throw 'expected first upgrade to fail while the public executable is locked' }
    if ($first.Output -notmatch 'Failed to install entrypoint|failed to copy file') {
        throw "first upgrade failed for an unexpected reason: $($first.Output)"
    }
}
finally {
    $lock.Dispose()
}

$envAfterFailure = (& $toolExe --version 2>&1 | Out-String).Trim()
$publicAfterFailure = (& $publicExe --version 2>&1 | Out-String).Trim()
Record "environment-after-failure=$envAfterFailure"
Record "public-after-failure=$publicAfterFailure"
if ($envAfterFailure -notmatch '0\.9\.2') { throw 'tool environment was not upgraded to 0.9.2 before publication failed' }
if ($publicAfterFailure -notmatch '0\.9\.1') { throw 'public executable did not remain on 0.9.1 after the copy failure' }

$second = Invoke-Uv @('tool', 'upgrade', 'ruff')
if ($second.Code -ne 0) { throw 'second upgrade unexpectedly failed after releasing the executable lock' }
if ($second.Output -notmatch 'Nothing to upgrade') {
    throw "expected second upgrade to take the NoOp path: $($second.Output)"
}

$publicAfterSecond = (& $publicExe --version 2>&1 | Out-String).Trim()
Record "public-after-second=$publicAfterSecond"
if ($publicAfterSecond -notmatch '0\.9\.1') {
    throw 'current source repaired the public executable; the reported defect is no longer reproduced'
}

Record 'REPRODUCED: environment=0.9.2, public entrypoint=0.9.1, second upgrade=NoOp'
