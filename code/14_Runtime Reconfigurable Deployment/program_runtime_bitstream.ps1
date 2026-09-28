$ErrorActionPreference = 'Stop'
$vivado = 'E:\Xilinx\Vivado\2021.2\bin\vivado.bat'
$license = 'E:\Xilinx\lic\2021.2\VivadoLicense2037.lic'
$script = Join-Path $PSScriptRoot 'scripts\program_runtime_bitstream.tcl'
$bit = Join-Path $PSScriptRoot 'build\runtime_jtag_200mhz\cns2fpga_runtime_jtag_200mhz.bit'
if (-not (Test-Path -LiteralPath $bit -PathType Leaf)) {
    $bit = Join-Path $PSScriptRoot '..\..\hardware\bitstreams\cns2fpga_runtime_jtag_200mhz.bit'
}
if (-not (Test-Path -LiteralPath $vivado -PathType Leaf)) { throw "Vivado not found: $vivado" }
if (-not (Test-Path -LiteralPath $license -PathType Leaf)) { throw "Vivado license not found: $license" }
if (-not (Test-Path -LiteralPath $bit -PathType Leaf)) { throw "Runtime bitstream not found: $bit" }
$env:XILINXD_LICENSE_FILE = $license
& $vivado -mode batch -nolog -nojournal -notrace -source $script
if ($LASTEXITCODE -ne 0) { throw "AXKU115 runtime programming failed: exit $LASTEXITCODE" }
