param(
    [string]$Python = 'C:\Users\20474\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe',
    [string]$TargetPattern = '*',
    [string]$DevicePattern = '*xcku115*',
    [string]$AxisPattern = '*'
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$step9 = Join-Path (Split-Path $root -Parent) '9_KU115 FPGA Validation'
$output = Join-Path $root 'outputs\courtship_song_v1'
$lock = Join-Path $output 'protocol_lock.json'
if (-not (Test-Path -LiteralPath $lock -PathType Leaf)) {
    throw 'Run run_experiment.py prepare before hardware trials.'
}
$protocol = Get-Content -LiteralPath $lock -Raw | ConvertFrom-Json
if ($protocol.schema -ne 'cns2fpga.step10' -or $protocol.cases.Count -ne 13) {
    throw 'Unexpected Step 10 protocol lock.'
}
$hostScript = Join-Path $step9 'host\step9_host.py'
$captureScript = Join-Path $step9 'host\run_jtag_trial.ps1'
$cases = @('intensity_08', 'intensity_14', 'alternating_20_50', 'raster_35_short')
foreach ($name in $cases) {
    $trial = Join-Path $output "trials\$name"
    $capture = Join-Path $output "captures\$name"
    $parsed = Join-Path $output "captures\${name}_parsed"
    if ((Test-Path -LiteralPath $capture) -or (Test-Path -LiteralPath $parsed)) {
        throw "Refusing to overwrite capture for $name. Preserve the existing run or use a new experiment output directory."
    }
    $metadata = Get-Content -LiteralPath (Join-Path $trial 'metadata.json') -Raw | ConvertFrom-Json
    $event = $name -eq 'raster_35_short'
    Write-Host "Starting board trial: $name, steps=$($metadata.timesteps), events=$event"
    if ($event) {
        & $captureScript -TrialDir $trial -CaptureDir $capture -CaptureEvents `
            -TargetPattern $TargetPattern -DevicePattern $DevicePattern -AxisPattern $AxisPattern
    } else {
        & $captureScript -TrialDir $trial -CaptureDir $capture `
            -TargetPattern $TargetPattern -DevicePattern $DevicePattern -AxisPattern $AxisPattern
    }
    if ($LASTEXITCODE -ne 0) { throw "JTAG trial failed: $name" }
    $parseArgs = @('parse-dump', '--summary-words', (Join-Path $capture 'summary_words.hex'),
                   '--timesteps', [string]$metadata.timesteps, '--period-cycles', '200000',
                   '--output-dir', $parsed)
    if ($event) { $parseArgs += @('--event-words', (Join-Path $capture 'event_words.hex')) }
    & $Python $hostScript @parseArgs
    if ($LASTEXITCODE -ne 0) { throw "Capture parse failed: $name" }
}
Write-Host 'Step 10 new-condition board captures complete.'
