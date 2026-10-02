param(
    [string]$CaptureDir = (Join-Path $PSScriptRoot '..\build\p0_jtag_recovery'),
    [int]$ExpectedEpoch = 2,
    [switch]$ValidateOnly
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$code = Split-Path -Parent $root
$vivado = 'E:\Xilinx\Vivado\2021.2\bin\vivado.bat'
$license = 'E:\Xilinx\lic\2021.2\VivadoLicense2037.lic'
$python = 'python'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { $python = (Get-Command python -ErrorAction Stop).Source }
$fault = Join-Path $PSScriptRoot 'test_jtag_fault_recovery.tcl'
$visualImage = Join-Path $code '12_Visual-to-Steering Circuit\outputs\visual_left_hw_ir_v0'
$visualTrial = Join-Path $code '12_Visual-to-Steering Circuit\outputs\visual_left_board_v0\trial'
$capture = [System.IO.Path]::GetFullPath($CaptureDir)
foreach ($path in @($vivado,$license,$python,$fault,$visualImage,$visualTrial)) {
    if (-not (Test-Path -LiteralPath $path)) { throw "Required file missing: $path" }
}
if ($ExpectedEpoch -lt 1) { throw 'ExpectedEpoch must be positive.' }
if (Test-Path -LiteralPath $capture) {
    if (@(Get-ChildItem -LiteralPath $capture -Force).Count -ne 0) {
        throw "Capture directory must be absent or empty: $capture"
    }
}
& $python (Join-Path $PSScriptRoot 'prepare_image.py') $visualImage | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Visual image preflight failed.' }
& (Join-Path $PSScriptRoot 'run_runtime_trial.ps1') -TrialDir $visualTrial `
    -CaptureDir (Join-Path $capture 'visual_recovered') -ValidateOnly
if ($ValidateOnly) {
    Write-Host 'JTAG_FAULT_RECOVERY_PREFLIGHT_PASS; no board state changed.'
    return
}

New-Item -ItemType Directory -Path $capture -Force | Out-Null
$oldLicense = $env:XILINXD_LICENSE_FILE
try {
    $env:XILINXD_LICENSE_FILE = $license
    # Separate Vivado processes model loss of the host transport after one
    # accepted graph word. The FPGA itself is never reprogrammed here.
    & $vivado -mode batch -nolog -nojournal -notrace -source $fault -tclargs interrupt $ExpectedEpoch |
        Tee-Object -FilePath (Join-Path $capture 'interrupt.log')
    if ($LASTEXITCODE -ne 0) { throw 'JTAG interruption phase failed.' }
    & $vivado -mode batch -nolog -nojournal -notrace -source $fault -tclargs reject $ExpectedEpoch |
        Tee-Object -FilePath (Join-Path $capture 'reject.log')
    if ($LASTEXITCODE -ne 0) { throw 'JTAG rejection phase failed.' }
} finally {
    $env:XILINXD_LICENSE_FILE = $oldLicense
}
& (Join-Path $PSScriptRoot 'load_runtime_image.ps1') -ImageDirectory $visualImage
$recoveryCapture = Join-Path $capture 'visual_recovered'
& (Join-Path $PSScriptRoot 'run_runtime_trial.ps1') -TrialDir $visualTrial `
    -CaptureDir $recoveryCapture -CaptureEvents
& $python (Join-Path $PSScriptRoot 'verify_runtime_capture.py') `
    --capture-dir $recoveryCapture `
    --reference-summary (Join-Path $visualTrial 'expected_counts.csv') `
    --expected-checksum 6C233D31 --expected-epoch ($ExpectedEpoch + 1) `
    --expected-neurons 226 --expected-synapses 1730 `
    --expected-events (Join-Path $visualTrial 'expected_events.csv')
if ($LASTEXITCODE -ne 0) { throw 'Recovered image capture mismatch.' }
Write-Host "JTAG_FAULT_RECOVERY_PASS epoch=$($ExpectedEpoch + 1) capture=$capture"
