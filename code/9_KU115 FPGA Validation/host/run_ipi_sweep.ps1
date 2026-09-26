param(
    [int[]]$IpiMs = @(15, 25, 45, 55, 65, 75, 85, 95),
    [string]$CaptureTag = 'summary'
)

$ErrorActionPreference = 'Stop'
$python = 'C:\Users\20474\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$prepare = Join-Path $PSScriptRoot 'step9_host.py'
$runner = Join-Path $PSScriptRoot 'run_jtag_trial.ps1'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw "Python not found: $python" }
if ($CaptureTag -notmatch '^[A-Za-z0-9_-]+$') { throw 'CaptureTag must use only letters, digits, _ or -.' }
foreach ($ipi in $IpiMs) {
    if ($ipi -notin @(15, 25, 35, 45, 55, 65, 75, 85, 95)) {
        throw "Unsupported locked IPI condition: $ipi"
    }
    $trial = Join-Path $PSScriptRoot "trials\ipi_$ipi"
    $capture = Join-Path $PSScriptRoot "captures\ipi_${ipi}_${CaptureTag}"
    $parsed = Join-Path $PSScriptRoot "captures\ipi_${ipi}_${CaptureTag}_parsed"
    Write-Host "STEP9_IPI_START ipi_ms=$ipi"
    & $runner -TrialDir $trial -CaptureDir $capture
    & $python $prepare parse-dump --summary-words (Join-Path $capture 'summary_words.hex') `
        --timesteps 4308 --period-cycles 200000 --output-dir $parsed
    if ($LASTEXITCODE -ne 0) { throw "IPI $ipi parse-dump failed" }
    & $python $prepare compare-groups --counts (Join-Path $parsed 'counts.csv') --ipi-ms $ipi
    if ($LASTEXITCODE -ne 0) { throw "IPI $ipi group comparison failed" }
    Write-Host "STEP9_IPI_PASS ipi_ms=$ipi"
}
