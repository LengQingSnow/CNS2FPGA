param([switch]$SynthesisOnly)

$ErrorActionPreference = 'Stop'
$vivado = 'E:\Xilinx\Vivado\2021.2\bin\vivado.bat'
$license = 'E:\Xilinx\lic\2021.2\VivadoLicense2037.lic'
if (-not (Test-Path -LiteralPath $vivado -PathType Leaf)) { throw "Vivado not found: $vivado" }
if (-not (Test-Path -LiteralPath $license -PathType Leaf)) { throw "Vivado license not found: $license" }
$env:XILINXD_LICENSE_FILE = $license
if ($SynthesisOnly) { $env:CNS2FPGA_SYNTH_ONLY = '1' }
else { Remove-Item Env:CNS2FPGA_SYNTH_ONLY -ErrorAction SilentlyContinue }
& $vivado -mode batch -notrace -source (Join-Path $PSScriptRoot 'scripts\build_runtime_bitstream.tcl')
if ($LASTEXITCODE -ne 0) { throw "Runtime bitstream build failed: exit $LASTEXITCODE" }
