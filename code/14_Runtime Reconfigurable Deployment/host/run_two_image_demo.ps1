param(
    [string]$CaptureRoot = (Join-Path $PSScriptRoot '..\build\two_image_board_demo'),
    [switch]$ValidateOnly
)

$ErrorActionPreference = 'Stop'
$step15 = Split-Path -Parent $PSScriptRoot
$code = Split-Path -Parent $step15
$python = 'python'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    $python = (Get-Command python -ErrorAction Stop).Source
}
$visualImage = Join-Path $code '12_Visual-to-Steering Circuit\outputs\visual_left_hw_ir_v0'
$visualTrial = Join-Path $code '12_Visual-to-Steering Circuit\outputs\visual_left_board_v0\trial'
$visualReference = Join-Path $visualTrial 'expected_counts.csv'
$courtshipImage = Join-Path $code '6_Connectome Compiler\outputs\courtship_song_hw_ir_v1'
$courtshipTrial = Join-Path $code '9_KU115 FPGA Validation\host\trials\smoke8'
$captureRootPath = [System.IO.Path]::GetFullPath($CaptureRoot)
$visualCapture = Join-Path $captureRootPath 'visual'
$courtshipCapture = Join-Path $captureRootPath 'courtship'

foreach ($path in @($visualImage,$visualTrial,$visualReference,$courtshipImage,$courtshipTrial)) {
    if (-not (Test-Path -LiteralPath $path)) { throw "Required input missing: $path" }
}
if (Test-Path -LiteralPath $captureRootPath) {
    if (@(Get-ChildItem -LiteralPath $captureRootPath -Force).Count -ne 0) {
        throw "Capture root must be absent or empty: $captureRootPath"
    }
}

& $python (Join-Path $PSScriptRoot 'prepare_image.py') $visualImage | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Visual image preflight failed' }
& $python (Join-Path $PSScriptRoot 'prepare_image.py') $courtshipImage | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Courtship image preflight failed' }
& (Join-Path $PSScriptRoot 'run_runtime_trial.ps1') -TrialDir $visualTrial -CaptureDir $visualCapture -ValidateOnly
& (Join-Path $PSScriptRoot 'run_runtime_trial.ps1') -TrialDir $courtshipTrial -CaptureDir $courtshipCapture -ValidateOnly
if ($ValidateOnly) {
    Write-Host 'TWO_IMAGE_DEMO_PREFLIGHT_PASS; no board was programmed.'
    return
}

# This is the only FPGA programming operation in the demonstration.
& (Join-Path $step15 'program_runtime_bitstream.ps1')
& (Join-Path $PSScriptRoot 'load_runtime_image.ps1') -ImageDirectory $visualImage
& (Join-Path $PSScriptRoot 'run_runtime_trial.ps1') -TrialDir $visualTrial -CaptureDir $visualCapture -CaptureEvents
& $python (Join-Path $PSScriptRoot 'verify_runtime_capture.py') `
    --capture-dir $visualCapture --reference-summary $visualReference `
    --expected-checksum 6C233D31 --expected-epoch 1 `
    --expected-neurons 226 --expected-synapses 1730 `
    --expected-events (Join-Path $visualTrial 'expected_events.csv')
if ($LASTEXITCODE -ne 0) { throw 'Visual board capture verification failed' }

# No program_hw_devices call occurs between the two graph uploads.
& (Join-Path $PSScriptRoot 'load_runtime_image.ps1') -ImageDirectory $courtshipImage
& (Join-Path $PSScriptRoot 'run_runtime_trial.ps1') -TrialDir $courtshipTrial -CaptureDir $courtshipCapture -CaptureEvents
& $python (Join-Path $PSScriptRoot 'verify_runtime_capture.py') `
    --capture-dir $courtshipCapture `
    --reference-summary (Join-Path $courtshipTrial 'reference_summary.csv') `
    --expected-checksum 45AEAAAE --expected-epoch 2 `
    --expected-neurons 6279 --expected-synapses 350185 `
    --expected-spike-mem (Join-Path $courtshipTrial 'expected_spike.mem')
if ($LASTEXITCODE -ne 0) { throw 'Courtship board capture verification failed' }
Write-Host "TWO_IMAGE_BOARD_DEMO_PASS capture=$captureRootPath"
