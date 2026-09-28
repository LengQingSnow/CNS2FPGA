param(
    [Parameter(Mandatory = $true)][string]$RunRoot
)

$ErrorActionPreference = 'Stop'
$step15 = Split-Path -Parent $PSScriptRoot
$codeRoot = Split-Path -Parent $step15
$python = 'python'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    $python = (Get-Command python -ErrorAction Stop).Source
}
$runPath = [System.IO.Path]::GetFullPath($RunRoot)
$capture = Join-Path $runPath 'courtship'
$statusPath = Join-Path $runPath 'status.json'
$image = Join-Path $codeRoot '6_Connectome Compiler\outputs\courtship_song_hw_ir_v1'
$trial = Join-Path $codeRoot '9_KU115 FPGA Validation\host\trials\smoke8'

if (Test-Path -LiteralPath $statusPath) {
    throw "Run status already exists; refusing to reuse $runPath"
}
New-Item -ItemType Directory -Path $runPath -Force | Out-Null

function Write-RunStatus([string]$state, [string]$stage, [string]$detail) {
    [ordered]@{
        schema = 'cns2fpga.runtime_board_test.v1'
        state = $state
        stage = $stage
        timestamp = (Get-Date).ToString('o')
        capture = $capture
        detail = $detail
    } | ConvertTo-Json | Set-Content -LiteralPath $statusPath -Encoding utf8
}

Write-RunStatus 'RUNNING' 'IMAGE_UPLOAD' 'Re-loading courtship into the existing runtime bitstream.'
try {
    Write-Host 'COURTSHIP_STAGE=IMAGE_UPLOAD'
    & (Join-Path $PSScriptRoot 'load_runtime_image.ps1') -ImageDirectory $image
    Write-RunStatus 'RUNNING' 'TRIAL' 'Courtship image committed; running smoke8.'
    Write-Host 'COURTSHIP_STAGE=TRIAL'
    & (Join-Path $PSScriptRoot 'run_runtime_trial.ps1') -TrialDir $trial -CaptureDir $capture -CaptureEvents
    Write-RunStatus 'RUNNING' 'VERIFY' 'Board capture complete; comparing all counts and ordered events.'
    Write-Host 'COURTSHIP_STAGE=VERIFY'
    & $python (Join-Path $PSScriptRoot 'verify_runtime_capture.py') `
        --capture-dir $capture `
        --reference-summary (Join-Path $trial 'reference_summary.csv') `
        --expected-checksum 45AEAAAE --expected-epoch 2 `
        --expected-neurons 6279 --expected-synapses 350185 `
        --expected-spike-mem (Join-Path $trial 'expected_spike.mem')
    if ($LASTEXITCODE -ne 0) { throw "Capture verification exited $LASTEXITCODE" }
    Write-RunStatus 'PASS' 'COMPLETE' 'Courtship smoke8 counts and ordered events matched the CPU reference.'
    Write-Host 'COURTSHIP_BOARD_TEST_PASS'
} catch {
    Write-RunStatus 'FAIL' 'ERROR' $_.Exception.Message
    Write-Error $_
    exit 1
}
