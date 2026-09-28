param(
    [string]$Vivado = 'E:\Xilinx\Vivado\2021.2\bin\vivado.bat',
    [string]$License = 'E:\Xilinx\lic\2021.2\VivadoLicense2037.lic'
)
$ErrorActionPreference = 'Stop'
$vivado = $Vivado
$license = $License
$script = Join-Path $PSScriptRoot 'scripts\build_ethernet_bitstream.tcl'
foreach ($path in @($vivado, $license, $script)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing $path" }
}
$env:XILINXD_LICENSE_FILE = $license
Remove-Item Env:CNS2FPGA_SYNTH_ONLY -ErrorAction SilentlyContinue
& $vivado -mode batch -nolog -nojournal -notrace -source $script
if ($LASTEXITCODE -ne 0) { throw "Ethernet bitstream build failed: exit $LASTEXITCODE" }
