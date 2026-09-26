param(
    [string]$Python = 'C:\Users\20474\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe',
    [string]$TargetPattern = '*',
    [string]$DevicePattern = '*xcku115*',
    [string]$AxisPattern = '*'
)
$ErrorActionPreference = 'Stop'
$output = Join-Path $PSScriptRoot 'outputs\visual_left_board_v0'
$trial = Join-Path $output 'trial'
$capture = Join-Path $output 'capture'
$parsed = Join-Path $output 'parsed'
$bitstream = Join-Path $PSScriptRoot 'build\visual_left_jtag_200mhz\cns2fpga_visual_left_jtag_200mhz.bit'
if (-not (Test-Path -LiteralPath $bitstream -PathType Leaf)) { throw "Missing visual bitstream: $bitstream" }
if (-not (Test-Path -LiteralPath (Join-Path $trial 'metadata.json') -PathType Leaf)) { throw 'Prepare the visual trial first.' }
if ((Test-Path -LiteralPath $capture) -or (Test-Path -LiteralPath $parsed)) { throw 'Refusing to overwrite a prior visual board capture.' }
& (Join-Path $PSScriptRoot 'program_visual_left_jtag.ps1')
if ($LASTEXITCODE -ne 0) { throw 'Board programming failed.' }
$step9 = Join-Path (Split-Path $PSScriptRoot -Parent) '9_KU115 FPGA Validation'
& (Join-Path $step9 'host\run_jtag_trial.ps1') -TrialDir $trial -CaptureDir $capture -CaptureEvents `
    -TargetPattern $TargetPattern -DevicePattern $DevicePattern -AxisPattern $AxisPattern
if ($LASTEXITCODE -ne 0) { throw 'Visual board trial failed.' }
& $Python (Join-Path $step9 'host\step9_host.py') parse-dump --summary-words (Join-Path $capture 'summary_words.hex') `
    --event-words (Join-Path $capture 'event_words.hex') --timesteps 250 --period-cycles 200000 --output-dir $parsed
if ($LASTEXITCODE -ne 0) { throw 'Visual board capture parsing failed.' }
& $Python (Join-Path $PSScriptRoot 'verify_visual_left_board.py')
if ($LASTEXITCODE -ne 0) { throw 'Visual board verification failed.' }
