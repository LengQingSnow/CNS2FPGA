param(
    [string]$Python = 'C:\Users\20474\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe',
    [string]$TargetPattern = '*',
    [string]$DevicePattern = '*xcku115*',
    [string]$AxisPattern = '*'
)

$ErrorActionPreference = 'Stop'
$output = Join-Path $PSScriptRoot 'outputs\courtship_song_robustness_v2'
$step9 = Join-Path (Split-Path $PSScriptRoot -Parent) '9_KU115 FPGA Validation'
$lock = Join-Path $output 'protocol_lock.json'
if (-not (Test-Path -LiteralPath $lock -PathType Leaf)) {
    throw 'Run run_robustness.py prepare first.'
}
$protocol = Get-Content -LiteralPath $lock -Raw | ConvertFrom-Json
if ($protocol.schema -ne 'cns2fpga.step11' -or $protocol.version -ne 2 -or $protocol.cases.Count -ne 65) {
    throw 'Unexpected Step 11 protocol lock.'
}
$captureScript = Join-Path $step9 'host\run_jtag_trial.ps1'
$hostScript = Join-Path $step9 'host\step9_host.py'
foreach ($level in @(5, 10, 20)) {
    $name = 'input_noise_{0:D2}_r0' -f $level
    $trial = Join-Path $output "trials\$name"
    $capture = Join-Path $output "captures\$name"
    $parsed = Join-Path $output "captures\${name}_parsed"
    if ((Test-Path -LiteralPath $capture) -or (Test-Path -LiteralPath $parsed)) {
        throw "Refusing to overwrite capture for $name."
    }
    $metadata = Get-Content -LiteralPath (Join-Path $trial 'metadata.json') -Raw | ConvertFrom-Json
    if ($metadata.timesteps -ne 4308 -or $metadata.details.seed -ne (20260925 + 30000 + $level * 100)) {
        throw "Unexpected trial metadata for $name"
    }
    Write-Host "Starting board noise trial: $name"
    & $captureScript -TrialDir $trial -CaptureDir $capture `
        -TargetPattern $TargetPattern -DevicePattern $DevicePattern -AxisPattern $AxisPattern
    if ($LASTEXITCODE -ne 0) { throw "JTAG trial failed: $name" }
    & $Python $hostScript parse-dump --summary-words (Join-Path $capture 'summary_words.hex') `
        --timesteps '4308' --period-cycles '200000' --output-dir $parsed
    if ($LASTEXITCODE -ne 0) { throw "Capture parse failed: $name" }
}
Write-Host 'Step 11 board noise captures complete.'
