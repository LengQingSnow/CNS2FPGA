param(
    [Parameter(Mandatory)][string]$OutputRoot,
    [Parameter(Mandatory)][string]$StatusPath,
    [Parameter(Mandatory)][string]$LogPath,
    [int]$Sessions = 2
)

$ErrorActionPreference = 'Stop'
$campaign = Join-Path $PSScriptRoot 'run_ethernet_p0_campaign.ps1'

function Write-Status([string]$state, [string]$detail) {
    $payload = [ordered]@{
        state = $state
        detail = $detail
        updated_at = (Get-Date).ToString('o')
        output_root = $OutputRoot
        log_path = $LogPath
    } | ConvertTo-Json -Depth 5
    $temporary = "$StatusPath.tmp"
    Set-Content -LiteralPath $temporary -Value $payload -Encoding utf8
    Move-Item -LiteralPath $temporary -Destination $StatusPath -Force
}

try {
    Write-Status 'RUNNING' 'Started detached Ethernet P0 campaign'
    & $campaign -OutputRoot $OutputRoot -SourceIp '192.168.1.10' `
        -Sessions $Sessions -IpiMs @(15,35,65) *>&1 | Tee-Object -FilePath $LogPath
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath (Join-Path $OutputRoot 'campaign_summary.json'))) {
        throw 'Campaign did not write a complete summary.'
    }
    Write-Status 'PASS' 'All physical sessions completed and campaign summary exists'
} catch {
    Write-Status 'FAIL' $_.Exception.Message
    throw
}
