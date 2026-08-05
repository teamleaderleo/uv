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

# Production launches the finalizer from the updater process. Keep that relationship exact:
# the parent below spawns the helper with its own PID, records the child identity, and then
# remains alive until the outer matrix terminates it.
$ParentScript = Join-Path $MatrixRoot 'launch-finalizer-parent.ps1'
@'
param([Parameter(Mandatory = $true)][string]$ConfigPath)
$ErrorActionPreference = 'Stop'
$config = Get-Content -Raw -LiteralPath $ConfigPath | ConvertFrom-Json
$arguments = @(
  "$PID",
  [string]$config.canonical,
  [string]$config.replacement,
  '--ready-file',
  [string]$config.readyPath
) + @($config.extraArgs)
$child = Start-Process -FilePath ([string]$config.helper) -ArgumentList $arguments `
  -PassThru -NoNewWindow `
  -RedirectStandardOutput ([string]$config.childStdout) `
  -RedirectStandardError ([string]$config.childStderr)
Set-Content -LiteralPath ([string]$config.childPidPath) -Value $child.Id
Set-Content -LiteralPath ([string]$config.parentReadyPath) -Value $PID
while ($true) {
  Start-Sleep -Milliseconds 100
}
'@ | Set-Content -LiteralPath $ParentScript -Encoding utf8

function Start-LiveFinalizer($name, $canonical, $replacement, [string[]]$extraArgs) {
  $parentReady = Join-Path $MatrixRoot "$name-parent-ready.txt"
  $childPidPath = Join-Path $MatrixRoot "$name-child-pid.txt"
  $ready = Join-Path $MatrixRoot "$name-finalizer-ready.txt"
  $configPath = Join-Path $MatrixRoot "$name-config.json"
  $parentStdout = Join-Path $ReceiptDirectory "$name-parent-stdout.txt"
  $parentStderr = Join-Path $ReceiptDirectory "$name-parent-stderr.txt"
  $childStdout = Join-Path $ReceiptDirectory "$name-finalizer-stdout.txt"
  $childStderr = Join-Path $ReceiptDirectory "$name-finalizer-stderr.txt"

  @{
    helper = $Helper
    canonical = $canonical
    replacement = $replacement
    extraArgs = @($extraArgs)
    readyPath = $ready
    childPidPath = $childPidPath
    parentReadyPath = $parentReady
    childStdout = $childStdout
    childStderr = $childStderr
  } | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $configPath

  $parent = Start-Process -FilePath 'powershell' -ArgumentList @(
    '-NoProfile', '-File', $ParentScript, $configPath
  ) -PassThru -WindowStyle Hidden `
    -RedirectStandardOutput $parentStdout -RedirectStandardError $parentStderr

  Wait-ForFile $parentReady "$name parent readiness"
  Wait-ForFile $childPidPath "$name finalizer pid"
  Wait-ForFile $ready "$name parent-handle readiness"

  $recordedParentId = [int](Get-Content -Raw -LiteralPath $parentReady)
  if ($recordedParentId -ne $parent.Id) {
    throw "$name parent identity mismatch: launched=$($parent.Id) recorded=$recordedParentId"
  }
  $childPid = [int](Get-Content -Raw -LiteralPath $childPidPath)
  $finalizer = Get-Process -Id $childPid -ErrorAction SilentlyContinue
  if ($null -eq $finalizer) {
    throw "$name finalizer exited before a live process handle was acquired"
  }

  $marker = Get-Content -Raw -LiteralPath $ready
  if ($marker -notmatch "parent_process_id=$($parent.Id)") {
    throw "$name readiness marker does not identify parent $($parent.Id): $marker"
  }
  if ($marker -notmatch "finalizer_process_id=$childPid") {
    throw "$name readiness marker does not identify finalizer ${childPid}: $marker"
  }

  [pscustomobject]@{
    Parent = $parent
    Finalizer = $finalizer
    Ready = $ready
    Stdout = $childStdout
    Stderr = $childStderr
  }
}

function Finish-LiveFinalizer($state, $expectedExit) {
  Stop-Process -Id $state.Parent.Id -Force
  $state.Parent.WaitForExit(15000) | Out-Null
  if (-not $state.Parent.HasExited) {
    throw "parent process $($state.Parent.Id) did not exit"
  }
  $state.Finalizer.WaitForExit(15000) | Out-Null
  if (-not $state.Finalizer.HasExited) {
    throw 'finalizer did not exit after its parent'
  }
  if ($state.Finalizer.ExitCode -ne $expectedExit) {
    throw "finalizer returned $($state.Finalizer.ExitCode), expected $expectedExit"
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

# If the first atomic publication never acquired the destination name, the complete write-side
# journal still provides enough information to discard the stage and keep the old canonical.
$writeOnly = Join-Path $MatrixRoot 'write-side-only'
New-Item -ItemType Directory -Force -Path $writeOnly | Out-Null
$wCanonical = Join-Path $writeOnly 'uv.exe'
$wStaged = Join-Path $writeOnly '.uv.exe.stage'
$wBackup = Join-Path $writeOnly '.uv.exe.backup'
$wJournal = Join-Path $writeOnly '.uv.exe.journal'
$wWriteJournal = "$wJournal.write"
Set-Content -NoNewline -LiteralPath $wCanonical -Value 'old-version'
Set-Content -NoNewline -LiteralPath $wStaged -Value 'new-version'
Write-Journal $wWriteJournal 'prepared' $wCanonical $wStaged $wBackup
Invoke-Recovery 'write-side-only' $wJournal
Assert-Content $wCanonical 'old-version' 'write-side recovery did not preserve old canonical'
Assert-Absent $wStaged 'write-side recovery retained stage'
Assert-Absent $wWriteJournal 'write-side recovery retained temporary journal'

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

# The next phase is written and synced under a temporary name. If publication fails and rollback
# also fails, the prior complete `prepared` journal must remain parseable and authoritative.
$failedPublish = Join-Path $MatrixRoot 'failed-journal-publish'
New-Item -ItemType Directory -Force -Path $failedPublish | Out-Null
$jCanonical = Join-Path $failedPublish 'uv.exe'
$jReplacement = Join-Path $MatrixRoot 'failed-journal-publish-new.exe'
Set-Content -NoNewline -LiteralPath $jCanonical -Value 'old-version'
Set-Content -NoNewline -LiteralPath $jReplacement -Value 'new-version'
$jState = Start-LiveFinalizer 'failed-journal-publish' $jCanonical $jReplacement @(
  '--fail-journal-publish-after-backup', '--fail-rollback-after-backup'
)
Assert-Content $jCanonical 'old-version' 'journal publish failure changed canonical before parent exit'
Finish-LiveFinalizer $jState 42
Assert-Absent $jCanonical 'journal publish plus rollback failure unexpectedly restored canonical'
$jJournal = @(Get-ChildItem -LiteralPath $failedPublish -Force |
  Where-Object Name -Like '*.update-journal.*' |
  Where-Object Name -NotLike '*.write')
$jWriteJournal = @(Get-ChildItem -LiteralPath $failedPublish -Force |
  Where-Object Name -Like '*.update-journal.*.write')
$jBackup = @(Get-ChildItem -LiteralPath $failedPublish -Force |
  Where-Object Name -Like '*.update-backup.*')
$jStage = @(Get-ChildItem -LiteralPath $failedPublish -Force |
  Where-Object Name -Like '*.update-stage.*')
if ($jJournal.Count -ne 1 -or $jWriteJournal.Count -ne 0 -or $jBackup.Count -ne 1 -or $jStage.Count -ne 1) {
  throw "failed atomic publication did not retain exactly the prior journal, backup, and stage: journal=$($jJournal.Count) write=$($jWriteJournal.Count) backup=$($jBackup.Count) stage=$($jStage.Count)"
}
if ((Get-Content -Raw -LiteralPath $jJournal[0].FullName) -notmatch '(?m)^phase=prepared$') {
  throw 'failed atomic publication did not preserve the prior complete prepared journal'
}
$jError = Get-Content -Raw -LiteralPath $jState.Stderr
if ($jError -notmatch 'injected failure before atomic journal publication' -or
    $jError -notmatch 'recovery journal preserved') {
  throw 'journal publication failure did not report both publication and recovery status'
}
Invoke-Recovery 'failed-journal-publish-recovery' $jJournal[0].FullName
Assert-Content $jCanonical 'old-version' 'recovery did not restore canonical from prior journal generation'
Assert-Absent $jJournal[0].FullName 'publication-failure recovery retained journal'
Assert-Absent $jBackup[0].FullName 'publication-failure recovery retained backup'
Assert-Absent $jStage[0].FullName 'publication-failure recovery retained stage'

@{
  parentAuthority = 'actual updater parent spawns finalizer and publishes readiness only after child owns parent handle'
  preparedRollback = 'pass'
  writeSideOnlyJournalRecovery = 'pass'
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
  atomicJournalPublishFailurePreservesPriorGeneration = 'pass'
  laterRecoveryAfterJournalPublishFailure = 'pass'
} | ConvertTo-Json | Set-Content (Join-Path $ReceiptDirectory 'recovery-matrix.json')