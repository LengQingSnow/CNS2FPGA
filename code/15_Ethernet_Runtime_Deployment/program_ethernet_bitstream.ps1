param(
    [string]$Vivado = 'E:\Xilinx\Vivado\2021.2\bin\vivado.bat',
    [string]$License = 'E:\Xilinx\lic\2021.2\VivadoLicense2037.lic',
    [string]$BitFile = ''
)
$ErrorActionPreference = 'Stop'
$vivado = $Vivado
$license = $License
$script = Join-Path $PSScriptRoot 'scripts\program_ethernet_bitstream.tcl'
$bit = if ($BitFile) { $BitFile } else {
    $developmentBit = Join-Path $PSScriptRoot 'build\runtime_eth_portfilter_200mhz\cns2fpga_runtime_eth_portfilter_200mhz.bit'
    if (Test-Path -LiteralPath $developmentBit -PathType Leaf) { $developmentBit } else {
        Join-Path $PSScriptRoot '..\..\hardware\bitstreams\cns2fpga_runtime_eth_200mhz.bit'
    }
}
foreach ($path in @($vivado, $license, $script, $bit)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing $path" }
}
$env:XILINXD_LICENSE_FILE = $license
$env:CNS2FPGA_BIT_FILE = $bit
& $vivado -mode batch -nolog -nojournal -notrace -source $script
if ($LASTEXITCODE -ne 0) { throw "Ethernet bitstream programming failed: exit $LASTEXITCODE" }
