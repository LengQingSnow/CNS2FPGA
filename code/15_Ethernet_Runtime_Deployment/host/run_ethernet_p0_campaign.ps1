param(
    [string]$OutputRoot = (Join-Path $PSScriptRoot '..\build\p0_ethernet_campaign'),
    [string]$SourceIp = '192.168.1.10',
    [int]$Sessions = 2,
    [int[]]$IpiMs = @(15, 35, 65),
    [switch]$ValidateOnly
)

$ErrorActionPreference = 'Stop'
$step15 = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$code = Split-Path -Parent $step15
$step14 = Join-Path $code '14_Runtime Reconfigurable Deployment'
$step9 = Join-Path $code '9_KU115 FPGA Validation'
$python = 'python'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { $python = (Get-Command python -ErrorAction Stop).Source }
$bit = Join-Path $step15 'build\runtime_eth_portfilter_200mhz\cns2fpga_runtime_eth_portfilter_200mhz.bit'
$visualImage = Join-Path $code '12_Visual-to-Steering Circuit\outputs\visual_left_hw_ir_v0'
$visualTrial = Join-Path $code '12_Visual-to-Steering Circuit\outputs\visual_left_board_v0\trial'
$courtshipImage = Join-Path $code '6_Connectome Compiler\outputs\courtship_song_hw_ir_v1'
$smokeTrial = Join-Path $step9 'host\trials\smoke8'
$uploader = Join-Path $step15 'host\upload_image_udp.py'
$runner = Join-Path $step14 'host\run_runtime_trial.ps1'
$verifier = Join-Path $step14 'host\verify_runtime_capture.py'
$longVerifier = Join-Path $step15 'host\verify_long_runtime_capture.py'
$step9Host = Join-Path $step9 'host\step9_host.py'
$fault = Join-Path $step15 'host\test_udp_recovery.py'
$output = [System.IO.Path]::GetFullPath($OutputRoot)
$expectedBitHash = '581354A62C8C7AEB134F300E7EA1928D8B681B996807710C61E307B33530D8F8'

if ($Sessions -lt 1 -or $Sessions -gt 5) { throw 'Sessions must be 1..5.' }
if ($IpiMs.Count -lt 2 -or @($IpiMs | Select-Object -Unique).Count -ne $IpiMs.Count) {
    throw 'Specify at least two distinct locked IPI conditions.'
}
foreach ($ipi in $IpiMs) {
    if ($ipi -notin @(15,25,35,45,55,65,75,85,95)) { throw "Unsupported IPI: $ipi" }
}
foreach ($path in @($python,$bit,$visualImage,$visualTrial,$courtshipImage,$smokeTrial,
                    $uploader,$runner,$verifier,$longVerifier,$step9Host,$fault)) {
    if (-not (Test-Path -LiteralPath $path)) { throw "Required input missing: $path" }
}
if ((Get-FileHash -LiteralPath $bit -Algorithm SHA256).Hash -ne $expectedBitHash) {
    throw 'Signed-off Ethernet bitstream hash mismatch.'
}
if (Test-Path -LiteralPath $output) {
    if (@(Get-ChildItem -LiteralPath $output -Force).Count -ne 0) {
        throw "Output root must be absent or empty: $output"
    }
}
& $python $uploader $visualImage --dry-run
if ($LASTEXITCODE -ne 0) { throw 'Visual image preflight failed.' }
& $python $uploader $courtshipImage --dry-run
if ($LASTEXITCODE -ne 0) { throw 'Courtship image preflight failed.' }
& $runner -TrialDir $visualTrial -CaptureDir (Join-Path $output 'preflight_visual') -ValidateOnly
& $runner -TrialDir $smokeTrial -CaptureDir (Join-Path $output 'preflight_courtship') -ValidateOnly
foreach ($ipi in $IpiMs) {
    & $runner -TrialDir (Join-Path $step9 "host\trials\ipi_$ipi") `
        -CaptureDir (Join-Path $output "preflight_ipi_$ipi") -ValidateOnly
}
if ($ValidateOnly) {
    Write-Host 'ETHERNET_P0_PREFLIGHT_PASS; no board state changed.'
    return
}

# The physical link must be isolated. Verify the host address exists before
# programming; a failed bind is a safe, early stop.
& $python -c 'import socket,sys; s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.bind((sys.argv[1],0)); s.close()' $SourceIp
if ($LASTEXITCODE -ne 0) { throw "Host address unavailable: $SourceIp" }
New-Item -ItemType Directory -Path $output -Force | Out-Null
$results = [System.Collections.Generic.List[object]]::new()

for ($session = 1; $session -le $Sessions; $session++) {
    $sessionDir = Join-Path $output "session_$session"
    New-Item -ItemType Directory -Path $sessionDir -Force | Out-Null
    Write-Host "ETHERNET_P0_SESSION_START session=$session"
    # Exactly one program_hw_devices invocation per session. All subsequent
    # image changes in this session use the same programmed bitstream.
    & (Join-Path $step15 'program_ethernet_bitstream.ps1') -BitFile $bit
    & $python (Join-Path $step15 'host\probe_udp_status.py') `
        --source-ip $SourceIp --board-ip 192.168.1.128 --sequence 1 --attempts 5
    if ($LASTEXITCODE -ne 0) { throw "Session ${session}: initial UDP STATUS failed." }

    $timer = [System.Diagnostics.Stopwatch]::StartNew()
    & $python $uploader $visualImage --source-ip $SourceIp --board-ip 192.168.1.128 --timeout 2 --retries 10
    if ($LASTEXITCODE -ne 0) { throw "Session ${session}: visual upload failed." }
    $visualUploadSeconds = $timer.Elapsed.TotalSeconds
    $visualCapture = Join-Path $sessionDir 'visual_250'
    & $runner -TrialDir $visualTrial -CaptureDir $visualCapture -CaptureEvents
    & $python $verifier --capture-dir $visualCapture `
        --reference-summary (Join-Path $visualTrial 'expected_counts.csv') `
        --expected-checksum 6C233D31 --expected-epoch 1 `
        --expected-neurons 226 --expected-synapses 1730 `
        --expected-events (Join-Path $visualTrial 'expected_events.csv')
    if ($LASTEXITCODE -ne 0) { throw "Session ${session}: visual capture mismatch." }

    $timer.Restart()
    & $python $uploader $courtshipImage --source-ip $SourceIp --board-ip 192.168.1.128 --timeout 2 --retries 10
    if ($LASTEXITCODE -ne 0) { throw "Session ${session}: courtship upload failed." }
    $courtshipUploadSeconds = $timer.Elapsed.TotalSeconds
    $smokeCapture = Join-Path $sessionDir 'courtship_smoke8'
    & $runner -TrialDir $smokeTrial -CaptureDir $smokeCapture -CaptureEvents
    & $python $verifier --capture-dir $smokeCapture `
        --reference-summary (Join-Path $smokeTrial 'reference_summary.csv') `
        --expected-checksum 45AEAAAE --expected-epoch 2 `
        --expected-neurons 6279 --expected-synapses 350185 `
        --expected-spike-mem (Join-Path $smokeTrial 'expected_spike.mem')
    if ($LASTEXITCODE -ne 0) { throw "Session ${session}: courtship smoke capture mismatch." }

    foreach ($ipi in $IpiMs) {
        $trial = Join-Path $step9 "host\trials\ipi_$ipi"
        $capture = Join-Path $sessionDir "courtship_ipi_$ipi"
        $parsed = Join-Path $sessionDir "courtship_ipi_${ipi}_parsed"
        & $runner -TrialDir $trial -CaptureDir $capture
        & $python $step9Host parse-dump --summary-words (Join-Path $capture 'summary_words.hex') `
            --timesteps 4308 --period-cycles 200000 --output-dir $parsed
        if ($LASTEXITCODE -ne 0) { throw "Session $session IPI ${ipi}: parse failed." }
        & $python $step9Host compare-groups --counts (Join-Path $parsed 'counts.csv') --ipi-ms $ipi
        if ($LASTEXITCODE -ne 0) { throw "Session $session IPI ${ipi}: fixed-CPU group mismatch." }
        & $python $longVerifier --capture-dir $capture --counts (Join-Path $parsed 'counts.csv') `
            --reference-counts (Join-Path $step9 "host\captures\ipi_${ipi}_summary_parsed\counts.csv") `
            --expected-epoch 2
        if ($LASTEXITCODE -ne 0) { throw "Session $session IPI ${ipi}: per-step comparison failed." }
    }

    # Deliberate host interruption and invalid-image attempts happen only
    # after all positive trials. A fresh valid visual upload recovers state.
    & $python $fault interrupt --source-ip $SourceIp
    if ($LASTEXITCODE -ne 0) { throw "Session ${session}: UDP interruption phase failed." }
    & $python $fault reject --source-ip $SourceIp
    if ($LASTEXITCODE -ne 0) { throw "Session ${session}: UDP rejection phase failed." }
    & $python $uploader $visualImage --source-ip $SourceIp --board-ip 192.168.1.128 --timeout 2 --retries 10
    if ($LASTEXITCODE -ne 0) { throw "Session ${session}: visual recovery upload failed." }
    $recoveryCapture = Join-Path $sessionDir 'visual_recovered_250'
    & $runner -TrialDir $visualTrial -CaptureDir $recoveryCapture -CaptureEvents
    & $python $verifier --capture-dir $recoveryCapture `
        --reference-summary (Join-Path $visualTrial 'expected_counts.csv') `
        --expected-checksum 6C233D31 --expected-epoch 3 `
        --expected-neurons 226 --expected-synapses 1730 `
        --expected-events (Join-Path $visualTrial 'expected_events.csv')
    if ($LASTEXITCODE -ne 0) { throw "Session ${session}: recovery capture mismatch." }

    $results.Add([pscustomobject]@{
        session = $session
        bit_sha256 = $expectedBitHash
        program_operations = 1
        visual_upload_seconds = [math]::Round($visualUploadSeconds, 3)
        courtship_upload_seconds = [math]::Round($courtshipUploadSeconds, 3)
        visual_steps = 250
        courtship_smoke_steps = 8
        courtship_long_ipi_ms = @($IpiMs)
        courtship_long_steps_each = 4308
        recovery_visual_steps = 250
        image_epochs = @(1,2,3)
        status = 'PASS'
    })
    Write-Host "ETHERNET_P0_SESSION_PASS session=$session"
}
$results | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $output 'campaign_summary.json') -Encoding utf8
Write-Host "ETHERNET_P0_CAMPAIGN_PASS sessions=$Sessions output=$output"
