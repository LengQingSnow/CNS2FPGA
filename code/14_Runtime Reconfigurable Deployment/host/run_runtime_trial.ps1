param(
    [Parameter(Mandatory = $true)]
    [string]$TrialDir,

    [Parameter(Mandatory = $true)]
    [string]$CaptureDir,

    [switch]$CaptureEvents,
    [ValidateSet(65536, 131072)][int]$EventCapacity = 65536,
    [string]$TargetPattern = '*',
    [string]$DevicePattern = '*xcku115*',
    [string]$AxisPattern = '*',
    [switch]$ValidateOnly
)

$ErrorActionPreference = 'Stop'
$vivado = 'E:\Xilinx\Vivado\2021.2\bin\vivado.bat'
$license = 'E:\Xilinx\lic\2021.2\VivadoLicense2037.lic'
$tcl = Join-Path $PSScriptRoot 'run_runtime_trial.tcl'

foreach ($required in @($vivado, $license, $tcl)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Required file not found: $required"
    }
}
$trial = (Resolve-Path -LiteralPath $TrialDir -ErrorAction Stop).Path
if (-not (Test-Path -LiteralPath $trial -PathType Container)) {
    throw "Trial directory not found: $TrialDir"
}
$stimulus = Join-Path $trial 'stimulus.mem'
$metadataPath = Join-Path $trial 'metadata.json'
foreach ($required in @($stimulus, $metadataPath)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Trial file not found: $required"
    }
}
$metadata = Get-Content -LiteralPath $metadataPath -Raw | ConvertFrom-Json
if ($metadata.schema -ne 'cns2fpga.step9.stimulus' -or
    $metadata.network_neurons -lt 1 -or
    $metadata.network_neurons -gt 6279 -or
    $metadata.input_current_encoding.bits -ne 34 -or
    $metadata.input_current_encoding.frac_bits -ne 24) {
    throw 'Trial metadata does not describe the compatible safe_wf24 input format.'
}
$actualHash = (Get-FileHash -LiteralPath $stimulus -Algorithm SHA256).Hash.ToLowerInvariant()
$expectedHash = [string]$metadata.artifact_sha256.'stimulus.mem'
if ($actualHash -ne $expectedHash.ToLowerInvariant()) {
    throw "Stimulus checksum mismatch: $stimulus"
}
$capture = [System.IO.Path]::GetFullPath($CaptureDir)
if (Test-Path -LiteralPath $capture) {
    if (-not (Test-Path -LiteralPath $capture -PathType Container)) {
        throw "Capture path is a file: $capture"
    }
    if (@(Get-ChildItem -LiteralPath $capture -Force).Count -ne 0) {
        throw "Capture directory must be empty: $capture"
    }
}
if ([string]::IsNullOrWhiteSpace($TargetPattern) -or
    [string]::IsNullOrWhiteSpace($DevicePattern) -or
    [string]::IsNullOrWhiteSpace($AxisPattern)) {
    throw 'Target, device and AXI patterns must be nonempty.'
}

$captureBit = if ($CaptureEvents.IsPresent) { '1' } else { '0' }
Write-Host "Trial: $trial"
Write-Host "Steps: $($metadata.timesteps), events: $captureBit, capacity: $EventCapacity"
Write-Host "Capture: $capture"
Write-Host "Vivado: $vivado"
if ($ValidateOnly) {
    Write-Host 'Validation passed. No hardware connection or trial was started.'
    return
}

$oldLicense = $env:XILINXD_LICENSE_FILE
try {
    $env:XILINXD_LICENSE_FILE = $license
    & $vivado -mode batch -nolog -nojournal -notrace -source $tcl -tclargs `
        $trial $capture $captureBit $metadata.network_neurons $TargetPattern $DevicePattern $AxisPattern $EventCapacity
    if ($LASTEXITCODE -ne 0) {
        throw "Vivado JTAG trial failed with exit code $LASTEXITCODE"
    }
} finally {
    $env:XILINXD_LICENSE_FILE = $oldLicense
}

$registers = Join-Path $capture 'registers.csv'
$summary = Join-Path $capture 'summary_words.hex'
if (-not (Test-Path -LiteralPath $registers -PathType Leaf) -or
    -not (Test-Path -LiteralPath $summary -PathType Leaf)) {
    throw "Vivado exited without complete capture files in $capture"
}
if ($CaptureEvents.IsPresent -and -not (Test-Path -LiteralPath (Join-Path $capture 'event_words.hex') -PathType Leaf)) {
    throw "Vivado exited without the requested event dump in $capture"
}
Write-Host 'JTAG capture completed.'
