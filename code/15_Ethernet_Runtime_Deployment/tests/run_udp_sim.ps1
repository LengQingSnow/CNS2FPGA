$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$sim = Join-Path $root 'build\sim_udp'
if (-not (Test-Path -LiteralPath $sim -PathType Container)) {
    & vlib $sim
    if ($LASTEXITCODE -ne 0) { throw 'vlib failed' }
}
& vlog -sv -work $sim `
    (Join-Path $root 'rtl\cns2fpga_udp_command.v') `
    (Join-Path $root 'rtl\cns2fpga_eth_bus_bridge.sv') `
    (Join-Path $PSScriptRoot 'tb_udp_command.sv')
if ($LASTEXITCODE -ne 0) { throw 'vlog failed' }
& vsim -c -onfinish exit -do 'run -all' -lib ($sim.Replace('\', '/')) tb_udp_command
if ($LASTEXITCODE -ne 0) { throw 'UDP protocol simulation failed' }
