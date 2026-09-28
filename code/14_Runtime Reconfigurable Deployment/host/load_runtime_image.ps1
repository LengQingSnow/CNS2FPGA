param(
    [Parameter(Mandatory = $true)][string]$ImageDirectory,
    [string]$Vivado = 'E:\Xilinx\Vivado\2021.2\bin\vivado.bat',
    [string]$TargetPattern = '*',
    [string]$DevicePattern = '*xcku115*',
    [string]$AxiPattern = '*'
)

$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$imagePath = (Resolve-Path -LiteralPath $ImageDirectory).Path
$python = 'python'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    $python = (Get-Command python -ErrorAction Stop).Source
}
if (-not (Test-Path -LiteralPath $Vivado -PathType Leaf)) {
    throw "Vivado executable not found: $Vivado"
}

# The preflight validates the entire graph, including CSR bounds and every
# postsynaptic index, before any FPGA memory is changed.
$manifestText = & $python (Join-Path $scriptDir 'prepare_image.py') $imagePath
if ($LASTEXITCODE -ne 0) { throw 'Runtime image preflight failed' }
$image = ($manifestText | Out-String | ConvertFrom-Json)
Write-Host "Validated $($image.name): $($image.neurons) neurons, $($image.synapses) synapses, checksum $($image.checksum_hex)"

$env:XILINXD_LICENSE_FILE = 'E:\Xilinx\lic\2021.2\VivadoLicense2037.lic'
& $Vivado -mode batch -source (Join-Path $scriptDir 'load_runtime_image.tcl') -tclargs `
    $imagePath $image.neurons $image.synapses $image.checksum_hex `
    $TargetPattern $DevicePattern $AxiPattern
if ($LASTEXITCODE -ne 0) { throw "Vivado loader failed: exit $LASTEXITCODE" }
