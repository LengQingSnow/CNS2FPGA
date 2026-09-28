set script_dir [file dirname [file normalize [info script]]]
set root_dir [file normalize [file join $script_dir ..]]
set run_dir [file join $root_dir build runtime_eth_200mhz]
set report_dir [file join $root_dir reports runtime_eth_200mhz]
file mkdir $report_dir

# Reuse the fully routed 200 MHz placement. The subsequent full reroute did not
# preserve its core timing; these are only RGMII electrical/timing property ECOs.
set source_dcp [file join $run_dir post_route_initial.dcp]
if {![file isfile $source_dcp]} {error "Missing routed checkpoint: $source_dcp"}
open_checkpoint $source_dcp

set mmcm [get_cells clock_manager]
if {[llength $mmcm] != 1} {error "Expected one clock manager"}
set_property CLKOUT2_PHASE 95.625 $mmcm

set rxports [get_ports {phy_rxd[*] phy_rx_ctl}]
if {[llength $rxports] != 5} {error "Expected five RGMII RX data/control ports"}
set_input_delay -clock [get_clocks phy_rx_clk] -max -1.0 $rxports
set_input_delay -clock [get_clocks phy_rx_clk] -min 1.0 $rxports
set_input_delay -clock [get_clocks phy_rx_clk] -clock_fall -max -1.0 -add_delay $rxports
set_input_delay -clock [get_clocks phy_rx_clk] -clock_fall -min 1.0 -add_delay $rxports

set delays [get_cells -hier -filter {REF_NAME == IDELAYE3}]
if {[llength $delays] != 5} {error "Expected five RGMII RX IDELAYE3 cells"}
foreach cell $delays {
    if {[get_property DELAY_FORMAT $cell] ne "COUNT"} {
        error "Unexpected IDELAY format on $cell"
    }
}
set_property DELAY_VALUE 400 $delays

set txports [get_ports {phy_tx_clk phy_txd[*] phy_tx_ctl}]
if {[llength $txports] != 6} {error "Expected six RGMII TX ports"}
set_property SLEW FAST $txports
set_clock_uncertainty -setup 0.125 [get_clocks clk_200m_mmcm]

set waveform [get_property WAVEFORM [get_clocks phy_tx_clk_forwarded]]
if {$waveform ne "2.125 6.125"} {error "Unexpected TX clock waveform: $waveform"}

report_route_status -file [file join $report_dir eco_route_status.rpt]
report_timing_summary -delay_type min_max -max_paths 50 -report_unconstrained \
    -file [file join $report_dir eco_timing_summary.rpt]
report_drc -file [file join $report_dir eco_drc.rpt]

set wns [get_property SLACK [get_timing_paths -delay_type max -max_paths 1]]
set whs [get_property SLACK [get_timing_paths -delay_type min -max_paths 1]]
set rx_setup [get_property SLACK [get_timing_paths -from $rxports -delay_type max -max_paths 1]]
set rx_hold [get_property SLACK [get_timing_paths -from $rxports -delay_type min -max_paths 1]]
set tx_setup [get_property SLACK [get_timing_paths -to [get_ports {phy_txd[*] phy_tx_ctl}] -delay_type max -max_paths 1]]
set unrouted [llength [get_nets -quiet -hierarchical -filter {ROUTE_STATUS == "UNROUTED"}]]
set partial [llength [get_nets -quiet -hierarchical -filter {ROUTE_STATUS == "PARTIAL"}]]
set errors [get_drc_violations -quiet -filter {SEVERITY == "Error"}]
set critical [get_drc_violations -quiet -filter {SEVERITY == "Critical Warning"}]

set status_file [file join $report_dir eco_run_status.txt]
set status [open $status_file w]
puts $status "source_dcp=$source_dcp"
puts $status "board=ALINX_AXKU115_V1.0"
puts $status "part=xcku115-flva1517-2-i"
puts $status "core_clock_mhz=200.000"
puts $status "phy_clock_mhz=125.000"
puts $status "tx_clock_waveform_ns=$waveform"
puts $status "rx_idelay_count=5"
puts $status "rx_idelay_value_count=400"
puts $status "wns_ns=$wns"
puts $status "whs_ns=$whs"
puts $status "rx_setup_slack_ns=$rx_setup"
puts $status "rx_hold_slack_ns=$rx_hold"
puts $status "tx_setup_slack_ns=$tx_setup"
puts $status "unrouted_nets=$unrouted"
puts $status "partially_routed_nets=$partial"
puts $status "drc_error_count=[llength $errors]"
puts $status "drc_critical_count=[llength $critical]"
close $status

if {$wns < 0.0 || $whs < 0.0 || $rx_setup < 0.0 || $rx_hold < 0.0 || $tx_setup < 0.0 ||
    $unrouted != 0 || $partial != 0 || [llength $errors] != 0 || [llength $critical] != 0} {
    error "Ethernet ECO failed signoff: WNS=$wns WHS=$whs RX=$rx_setup/$rx_hold TX=$tx_setup route=$unrouted/$partial DRC=[llength $errors]/[llength $critical]"
}

set final_dcp [file join $run_dir post_route_ethernet_eco.dcp]
set bit_file [file join $run_dir cns2fpga_runtime_eth_200mhz.bit]
write_checkpoint -force $final_dcp
write_bitstream -force $bit_file
puts "RUNTIME_ETH_BITSTREAM_PASS file=$bit_file WNS=$wns WHS=$whs"
exit 0
