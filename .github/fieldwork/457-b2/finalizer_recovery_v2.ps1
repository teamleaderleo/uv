param(
  [Parameter(Mandatory = $true)][string]$Helper,
  [Parameter(Mandatory = $true)][string]$ReceiptDirectory,
  [Parameter(Mandatory = $true)][string]$MatrixRoot
)

$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path $ReceiptDirectory | Out-Null
New-Item -ItemType Directory -Force -Path $MatrixRoot | Out-Null

function Write-Journal($path, $phase, $canonical, $staged, $backup) {
  @(
    'version=1'
    "phase=$phase"
    "canonical=$canonical"
    "staged=$staged"
    "backup=$backup"
  ) | Set-Content -LiteralPath $path -Encoding utf8
}

function Invoke-Recovery($name, $journal, $expectedExit = 0) {
  $stdout = Join-Path $ReceiptDirectory "$name-stdout.txt"
  $stderr = Join-Path $ReceiptDirectory "$name-stderr.txt"
  $process = Start-Process -FilePath $Helper -ArgumentList @('recover', $journal) `
    -Wait -PassThru -NoNewWindow `
    -RedirectStandardOutput $stdout -RedirectStandardError $stderr
  if ($process.ExitCode -ne $expectedExit) {
    throw "$name returned $($process.ExitCode), expected $expectedExit"
  }
}

function Wait-ForFile($path, $description) {
  $deadline = (Get-Date).AddSeconds(20)
  while (-not (Test-Path -LiteralPath $path)) {
    if ((Get-Date) -ge $deadline) {
      throw "Timed out waiting for $description at $path"
    }
    Start-Sleep -Milliseconds 100
  }
}

function Assert-Content($path, $expected, $message) {
  if (-not (Test-Path -LiteralPath $path)) { throw "$message - file is absent" }
  if ((Get-Content -Raw -LiteralPath $path) -ne $expected) {
    throw "$message - unexpected content"
  }
}

function Assert-Absent($path, $message) {
  if (Test-Path -LiteralPath $path) { throw "$message - $path still exists" }
}

function Assert-NoTransactionFiles($directory, $message) {
  $files = @(Get-ChildItem -LiteralPath $directory -Force |
    Where-Object Name -Match '\.update-(stage|backup|journal)\.')
  if ($files.Count -ne 0) {
    throw "$message - retained: $($files.Name -join ', ')"
  }
}

function Start-LiveFinalizer($name, $canonical, $replacement, [string[]]$extraArgs) {
  $ready = Join-Path $MatrixRoot "$name-ready.txt"
  $stdout = Join-Path $ReceiptDirectory "$name-finalizer-stdout.txt"
  $stderr = Join-Path $ReceiptDirectory "$name-finalizer-stderr.txt"
  $parent = Start-Process -FilePath 'powershell' -ArgumentList @(
    '-NoProfile', '-Command', 'Start-Sleep -Seconds 60'
  ) -PassThru -WindowStyle Hidden
  $arguments = @(
    "$($parent.Id)",
    $canonical,
    $replacement,
    '--ready-file',
    $ready
  ) + @($extraArgs)
  $finalizer = Start-Process -FilePath $Helper -ArgumentList $arguments `
    -PassThru -NoNewWindow `
    -RedirectStandardOutput $stdout -RedirectStandardError $stderr
  Wait-ForFile $ready "$name parent-handle readiness"
  $marker = Get-Content -Raw -LiteralPath $ready
  if ($marker -notmatch "parent_process_id=$($parent.Id)") {
    throw "$name readiness marker does not identify parent $($parent.Id): $marker"
  }
  if ($marker -notmatch "finalizer_process_id=$($finalizer.Id)") {
    throw "$name readiness marker does not identify finalizer $($finalizer.Id): $marker"
  }
  [pscustomobject]@{
    Parent = $parent
    Finalizer = $finalizer
    Ready = $ready
    Stdout = $stdout
    Stderr = $stderr
  }
}

function Finish-LiveFinalizer($state, $expectedExit) {
  Stop-Process -Id $state.Parent.Id -Force
  $state.Parent.WaitForExit(15000) | Out-Null
  if (-not $state.Parent.HasExited) {
    throw "parent process $($state.Parent.Id) did not exit"
  }
  $state.Finalizer.WaitForExit(15000) | Out-Null
  if (-not $state.Finalizer.HasExited -or $state.Finalizer.ExitCode -ne $expectedExit) {
    throw "finalizer returned unexpected result: exited=$($state.Finalizer.HasExited) code=$($state.Finalizer.ExitCode) expected=$expectedExit"
  }
}

# PREPARED: old canonical is authoritative; discard uncommitted stage.
$prepared = Join-Path $MatrixRoot 'prepared'
New-Item -ItemType Directory -Force -Path $prepared | Out-Null
$pCanonical = Join-Path $prepared 'uv.exe'
$pStaged = Join-Path $prepared '.uv.exe.stage'
$pBackup = Join-Path $prepared '.uv.exe.backup'
$pJournal = Join-Path $prepared '.uv.exe.journal'
Set-Content -NoNewline -LiteralPath $pCanonical -Value 'old-version'
Set-Content -NoNewline -LiteralPath $pStaged -Value 'new-version'
Write-Journal $pJournal 'prepared' $pCanonical $pStaged $pBackup
Invoke-Recovery 'prepared-first' $pJournal
Assert-Content $pCanonical 'old-version' 'prepared recovery did not preserve old canonical'
Assert-Absent $pStaged 'prepared recovery did not remove stage'
Assert-Absent $pJournal 'prepared recovery did not remove journal'
Invoke-Recovery 'prepared-repeat' $pJournal

# OLD BACKED UP: canonical is absent; restore backup and discard stage.
$backed = Join-Path $MatrixRoot 'old-backed-up'
New-Item -ItemType Directory -Force -Path $backed | Out-Null
$bCanonical = Join-Path $backed 'uv.exe'
$bStaged = Join-Path $backed '.uv.exe.stage'
$bBackup = Join-Path $backed '.uv.exe.backup'
$bJournal = Join-Path $backed '.uv.exe.journal'
Set-Content -NoNewline -LiteralPath $bBackup -Value 'old-version'
Set-Content -NoNewline -LiteralPath $bStaged -Value 'new-version'
Write-Journal $bJournal 'old-backed-up' $bCanonical $bStaged $bBackup
Invoke-Recovery 'old-backed-up-first' $bJournal
Assert-Content $bCanonical 'old-version' 'old-backed-up recovery did not restore old canonical'
Assert-Absent $bBackup 'old-backed-up recovery retained backup'
Assert-Absent $bStaged 'old-backed-up recovery retained stage'
Invoke-Recovery 'old-backed-up-repeat' $bJournal

# NEW LIVE BUT UNCOMMITTED: conservative policy restores old generation.
$newLive = Join-Path $MatrixRoot 'new-live'
New-Item -ItemType Directory -Force -Path $newLive | Out-Null
$nCanonical = Join-Path $newLive 'uv.exe'
$nStaged = Join-Path $newLive '.uv.exe.stage'
$nBackup = Join-Path $newLive '.uv.exe.backup'
$nJournal = Join-Path $newLive '.uv.exe.journal'
Set-Content -NoNewline -LiteralPath $nCanonical -Value 'new-version'
Set-Content -NoNewline -LiteralPath $nBackup -Value 'old-version'
Write-Journal $nJournal 'new-live' $nCanonical $nStaged $nBackup
Invoke-Recovery 'new-live-first' $nJournal
Assert-Content $nCanonical 'old-version' 'new-live recovery did not roll back old canonical'
Assert-Absent $nBackup 'new-live recovery retained backup'
Invoke-Recovery 'new-live-repeat' $nJournal

# COMMITTED: new canonical is authoritative; clean old backup and stale stage.
$committed = Join-Path $MatrixRoot 'committed'
New-Item -ItemType Directory -Force -Path $committed | Out-Null
$cCanonical = Join-Path $committed 'uv.exe'
$cStaged = Join-Path $committed '.uv.exe.stage'
$cBackup = Join-Path $committed '.uv.exe.backup'
$cJournal = Join-Path $committed '.uv.exe.journal'
Set-Content -NoNewline -LiteralPath $cCanonical -Value 'new-version'
Set-Content -NoNewline -LiteralPath $cBackup -Value 'old-version'
Set-Content -NoNewline -LiteralPath $cStaged -Value 'stale-stage'
Write-Journal $cJournal 'committed' $cCanonical $cStaged $cBackup
Invoke-Recovery 'committed-first' $cJournal
Assert-Content $cCanonical 'new-version' 'committed recovery changed new canonical'
Assert-Absent $cBackup 'committed recovery retained backup'
Assert-Absent $cStaged 'committed recovery retained stale stage'
Invoke-Recovery 'committed-repeat' $cJournal

# Missing authority is corruption and must preserve the journal.
$missing = Join-Path $MatrixRoot 'missing-authority'
New-Item -ItemType Directory -Force -Path $missing | Out-Null
$mCanonical = Join-Path $missing 'uv.exe'
$mStaged = Join-Path $missing '.uv.exe.stage'
$mBackup = Join-Path $missing '.uv.exe.backup'
$mJournal = Join-Path $missing '.uv.exe.journal'
Write-Journal $mJournal 'old-backed-up' $mCanonical $mStaged $mBackup
Invoke-Recovery 'missing-authority' $mJournal 42
if (-not (Test-Path -LiteralPath $mJournal)) {
  throw 'corrupt transaction journal was deleted despite failed recovery'
}

# A journal must not authorize mutation outside its transaction directory.
$escape = Join-Path $MatrixRoot 'escape'
New-Item -ItemType Directory -Force -Path $escape | Out-Null
$outside = Join-Path $MatrixRoot 'outside-uv.exe'
$eStaged = Join-Path $escape '.uv.exe.stage'
$eBackup = Join-Path $escape '.uv.exe.backup'
$eJournal = Join-Path $escape '.uv.exe.journal'
Set-Content -NoNewline -LiteralPath $outside -Value 'outside-old'
Set-Content -NoNewline -LiteralPath $eStaged -Value 'new-version'
Write-Journal $eJournal 'prepared' $outside $eStaged $eBackup
Invoke-Recovery 'escape' $eJournal 42
Assert-Content $outside 'outside-old' 'escaping journal mutated external canonical file'
if (-not (Test-Path -LiteralPath $eJournal)) {
  throw 'invalid escaping journal was deleted'
}

# Normal live commit still keeps canonical old until parent exit, then installs new.
$success = Join-Path $MatrixRoot 'live-success'
New-Item -ItemType Directory -Force -Path $success | Out-Null
$sCanonical = Join-Path $success 'uv.exe'
$sReplacement = Join-Path $MatrixRoot 'live-success-new.exe'
Set-Content -NoNewline -LiteralPath $sCanonical -Value 'old-version'
Set-Content -NoNewline -LiteralPath $sReplacement -Value 'new-version'
$sState = Start-LiveFinalizer 'live-success' $sCanonical $sReplacement @()
Assert-Content $sCanonical 'old-version' 'live success changed canonical before parent exit'
Finish-LiveFinalizer $sState 0
Assert-Content $sCanonical 'new-version' 'live success did not install new canonical'
Assert-NoTransactionFiles $success 'live success retained transaction files'

# Ordinary post-backup error restores canonical and cleans transaction files immediately.
$ordinary = Join-Path $MatrixRoot 'ordinary-rollback'
New-Item -ItemType Directory -Force -Path $ordinary | Out-Null
$oCanonical = Join-Path $ordinary 'uv.exe'
$oReplacement = Join-Path $MatrixRoot 'ordinary-rollback-new.exe'
Set-Content -NoNewline -LiteralPath $oCanonical -Value 'old-version'
Set-Content -NoNewline -LiteralPath $oReplacement -Value 'new-version'
$oState = Start-LiveFinalizer 'ordinary-rollback' $oCanonical $oReplacement @('--fail-after-backup')
Assert-Content $oCanonical 'old-version' 'ordinary rollback changed canonical before parent exit'
Finish-LiveFinalizer $oState 42
Assert-Content $oCanonical 'old-version' 'ordinary rollback did not restore canonical'
Assert-NoTransactionFiles $ordinary 'ordinary rollback retained transaction files'

# Update error plus rollback error must preserve enough evidence for later recovery.
$failedRollback = Join-Path $MatrixRoot 'failed-rollback'
New-Item -ItemType Directory -Force -Path $failedRollback | Out-Null
$fCanonical = Join-Path $failedRollback 'uv.exe'
$fReplacement = Join-Path $MatrixRoot 'failed-rollback-new.exe'
Set-Content -NoNewline -LiteralPath $fCanonical -Value 'old-version'
Set-Content -NoNewline -LiteralPath $fReplacement -Value 'new-version'
$fState = Start-LiveFinalizer 'failed-rollback' $fCanonical $fReplacement @(
  '--fail-after-backup', '--fail-rollback-after-backup'
)
Assert-Content $fCanonical 'old-version' 'failed rollback changed canonical before parent exit'
Finish-LiveFinalizer $fState 42
Assert-Absent $fCanonical 'injected rollback failure unexpectedly restored canonical'
$fJournal = @(Get-ChildItem -LiteralPath $failedRollback -Force |
  Where-Object Name -Like '*.update-journal.*')
$fBackup = @(Get-ChildItem -LiteralPath $failedRollback -Force |
  Where-Object Name -Like '*.update-backup.*')
$fStage = @(Get-ChildItem -LiteralPath $failedRollback -Force |
  Where-Object Name -Like '*.update-stage.*')
if ($fJournal.Count -ne 1 -or $fBackup.Count -ne 1 -or $fStage.Count -ne 1) {
  throw "rollback failure did not preserve one journal, backup, and stage: journal=$($fJournal.Count) backup=$($fBackup.Count) stage=$($fStage.Count)"
}
if ((Get-Content -Raw -LiteralPath $fState.Stderr) -notmatch 'recovery journal preserved') {
  throw 'rollback failure error did not report preserved recovery journal'
}
Invoke-Recovery 'failed-rollback-recovery' $fJournal[0].FullName
Assert-Content $fCanonical 'old-version' 'later recovery did not restore canonical after rollback failure'
Assert-Absent $fJournal[0].FullName 'later recovery retained journal'
Assert-Absent $fBackup[0].FullName 'later recovery retained backup'
Assert-Absent $fStage[0].FullName 'later recovery retained stage'

@{
  preparedRollback = 'pass'
  oldBackedUpRollback = 'pass'
  newLiveRollback = 'pass'
  committedCleanup = 'pass'
  repeatedRecovery = 'pass'
  missingAuthorityFailsAndPreservesJournal = 'pass'
  pathEscapeRejected = 'pass'
  liveSuccess = 'pass'
  ordinaryRollback = 'pass'
  rollbackFailurePreservesEvidence = 'pass'
  laterRecoveryAfterRollbackFailure = 'pass'
} | ConvertTo-Json | Set-Content (Join-Path $ReceiptDirectory 'recovery-matrix.json')
