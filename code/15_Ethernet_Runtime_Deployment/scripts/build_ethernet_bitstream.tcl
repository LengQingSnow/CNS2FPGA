set script_dir [file dirname [file normalize [info script]]]
set root_dir [file normalize [file join $script_dir ..]]
set run_name runtime_eth_200mhz
if {[info exists ::env(CNS2FPGA_BUILD_NAME)]} {
    set run_name $::env(CNS2FPGA_BUILD_NAME)
    if {![regexp {^[a-zA-Z0-9_]+$} $run_name]} {error "Invalid build name"}
}
set run_dir [file normalize [file join $root_dir build $run_name]]
set report_dir [file normalize [file join $root_dir reports $run_name]]
set ip_dir [file join $run_dir ip]
file mkdir $run_dir
file mkdir $report_dir
file mkdir $ip_dir

set part_name xcku115-flva1517-2-i
set top_name cns2fpga_axku115_eth_top
create_project -in_memory -part $part_name
set_property target_language Verilog [current_project]

set ip_xci [file join $ip_dir cns2fpga_jtag_axi cns2fpga_jtag_axi.xci]
if {[file exists $ip_xci]} {
    read_ip [list $ip_xci]
} else {
    create_ip -name jtag_axi -vendor xilinx.com -library ip -version 1.2 \
        -module_name cns2fpga_jtag_axi -dir $ip_dir
    set_property CONFIG.PROTOCOL 2 [get_ips cns2fpga_jtag_axi]
    set_property CONFIG.M_AXI_DATA_WIDTH 32 [get_ips cns2fpga_jtag_axi]
    set_property CONFIG.M_AXI_ADDR_WIDTH 32 [get_ips cns2fpga_jtag_axi]
}
generate_target all [get_ips cns2fpga_jtag_axi]
synth_ip [get_ips cns2fpga_jtag_axi]

set previous_root [file normalize [file join $root_dir .. 14_Runtime\ Reconfigurable\ Deployment]]
set rtl_core [file join $previous_root rtl cns2fpga_core_sync_runtime.sv]
set rtl_engine [file join $previous_root rtl cns2fpga_trial_engine_runtime.sv]
set rtl_axi [file join $previous_root rtl cns2fpga_axi_lite_slave.sv]
set rtl_top [file join $root_dir rtl cns2fpga_axku115_eth_top.sv]
set rtl_stack [file join $root_dir rtl cns2fpga_eth_stack.v]
set rtl_command [file join $root_dir rtl cns2fpga_udp_command.v]
set rtl_bridge [file join $root_dir rtl cns2fpga_eth_bus_bridge.sv]
set rtl_mdio [file join $root_dir rtl cns2fpga_mdio_diag.sv]
set vendor_rtl [glob -directory [file join $root_dir vendor rtl] *.v]
set xdc_file [file join $root_dir constraints axku115_eth_200mhz.xdc]
read_verilog -sv [concat [list $rtl_core $rtl_engine $rtl_axi $rtl_top $rtl_stack $rtl_command $rtl_bridge $rtl_mdio] $vendor_rtl]
read_xdc [list $xdc_file]

synth_design -top $top_name -part $part_name -flatten_hierarchy rebuilt
set rx_idelays [get_cells -hier -filter {REF_NAME == IDELAYE3}]
if {[llength $rx_idelays] != 5} {
    error "Expected five RGMII RX IDELAYE3 cells, got [llength $rx_idelays]"
}
foreach cell $rx_idelays {
    if {[get_property DELAY_FORMAT $cell] ne "COUNT"} {
        error "Unexpected RGMII RX delay format at $cell"
    }
}
set_property DELAY_VALUE 400 $rx_idelays
puts "RGMII_RX_IDELAY_COUNT=5 DELAY_VALUE=400"
write_checkpoint -force [file join $run_dir post_synth.dcp]
report_utilization -file [file join $report_dir post_synth_utilization.rpt]
report_timing_summary -delay_type max -max_paths 20 \
    -file [file join $report_dir post_synth_timing_summary.rpt]
report_drc -file [file join $report_dir post_synth_drc.rpt]
set synth_critical_drc [get_drc_violations -quiet -filter {SEVERITY == "Critical Warning"}]
if {[llength $synth_critical_drc] != 0} {
    error "Critical DRC violations after synthesis: $synth_critical_drc"
}

if {[info exists ::env(CNS2FPGA_SYNTH_ONLY)] && $::env(CNS2FPGA_SYNTH_ONLY) eq "1"} {
    puts "RUNTIME_ETH_SYNTH_PASS"
    exit 0
}

opt_design
if {[info exists ::env(CNS2FPGA_INCREMENTAL_DCP)]} {
    set reference_dcp [file normalize $::env(CNS2FPGA_INCREMENTAL_DCP)]
    if {![file isfile $reference_dcp]} {error "Missing incremental checkpoint: $reference_dcp"}
    read_checkpoint -incremental $reference_dcp
    puts "INCREMENTAL_REFERENCE=$reference_dcp"
}
place_design
phys_opt_design
route_design
phys_opt_design

write_checkpoint -force [file join $run_dir post_route.dcp]
report_route_status -file [file join $report_dir route_status.rpt]
report_utilization -file [file join $report_dir post_route_utilization.rpt]
report_timing_summary -delay_type min_max -max_paths 50 -report_unconstrained \
    -file [file join $report_dir post_route_timing_summary.rpt]
report_drc -file [file join $report_dir drc.rpt]

set worst_path [get_timing_paths -delay_type max -max_paths 1]
set wns [get_property SLACK $worst_path]
set timing_ok [expr {$wns >= 0.0}]
set worst_hold_path [get_timing_paths -delay_type min -max_paths 1]
set whs [get_property SLACK $worst_hold_path]
set hold_ok [expr {$whs >= 0.0}]
set unrouted [llength [get_nets -quiet -hierarchical -filter {ROUTE_STATUS == "UNROUTED"}]]
set partial [llength [get_nets -quiet -hierarchical -filter {ROUTE_STATUS == "PARTIAL"}]]
set drc_errors [get_drc_violations -quiet -filter {SEVERITY == "Error"}]
set drc_critical [get_drc_violations -quiet -filter {SEVERITY == "Critical Warning"}]

set status [open [file join $report_dir run_status.txt] w]
puts $status "board=ALINX_AXKU115_V1.0"
puts $status "network=KSZ9031RNX_RGMII_1000BASE_T"
puts $status "part=$part_name"
puts $status "core_clock_mhz=200.000"
puts $status "wns_ns=$wns"
puts $status "timing_met=$timing_ok"
puts $status "whs_ns=$whs"
puts $status "hold_met=$hold_ok"
puts $status "unrouted_nets=$unrouted"
puts $status "partially_routed_nets=$partial"
puts $status "drc_error_count=[llength $drc_errors]"
puts $status "drc_critical_count=[llength $drc_critical]"
close $status

if {!$timing_ok || !$hold_ok || $unrouted != 0 || $partial != 0 || [llength $drc_errors] != 0 || [llength $drc_critical] != 0} {
    puts "ERROR: AXKU115 Ethernet implementation did not pass: WNS=$wns WHS=$whs unrouted=$unrouted partial=$partial DRC=[llength $drc_errors] critical=[llength $drc_critical]"
    exit 2
}

set bit_file [file join $run_dir cns2fpga_${run_name}.bit]
write_bitstream -force $bit_file
puts "RUNTIME_ETH_BITSTREAM_PASS file=$bit_file WNS=$wns"
exit 0
