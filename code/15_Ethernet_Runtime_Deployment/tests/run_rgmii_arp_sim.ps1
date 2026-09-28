$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$sim = Join-Path $root 'build\sim_rgmii_arp'
if (-not (Test-Path -LiteralPath $sim -PathType Container)) {
    & vlib $sim
    if ($LASTEXITCODE -ne 0) { throw 'vlib failed' }
}
$vendor = @(Get-ChildItem -LiteralPath (Join-Path $root 'vendor\rtl') -Filter '*.v' | ForEach-Object FullName)
& vlog -sv -work $sim @vendor `
    (Join-Path $root 'rtl\cns2fpga_udp_command.v') `
    (Join-Path $root 'rtl\cns2fpga_eth_stack.v') `
    (Join-Path $PSScriptRoot 'tb_rgmii_arp.sv')
if ($LASTEXITCODE -ne 0) { throw 'vlog failed' }
& vsim -c -onfinish exit -do 'run -all' -lib ($sim.Replace('\', '/')) tb_rgmii_arp
if ($LASTEXITCODE -ne 0) { throw 'RGMII ARP simulation failed' }
