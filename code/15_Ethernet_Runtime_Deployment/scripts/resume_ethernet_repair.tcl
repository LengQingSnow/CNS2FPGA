set script_dir [file dirname [file normalize [info script]]]
set root_dir [file normalize [file join $script_dir ..]]
set run_name runtime_eth_repair_200mhz
set run_dir [file join $root_dir build $run_name]
set report_dir [file join $root_dir reports $run_name]
set synth_dcp [file join $run_dir post_synth.dcp]
set reference_dcp [file join $root_dir build runtime_eth_200mhz post_route_ethernet_eco.dcp]
if {![file isfile $synth_dcp] || ![file isfile $reference_dcp]} {error "Missing checkpoint"}
file mkdir $report_dir
open_checkpoint $synth_dcp
opt_design
read_checkpoint -incremental $reference_dcp
place_design
phys_opt_design
route_design
phys_opt_design
write_checkpoint -force [file join $run_dir post_route.dcp]
report_route_status -file [file join $report_dir route_status.rpt]
report_timing_summary -delay_type min_max -max_paths 50 -report_unconstrained \
    -file [file join $report_dir post_route_timing_summary.rpt]
report_drc -file [file join $report_dir drc.rpt]
set wns [get_property SLACK [get_timing_paths -delay_type max -max_paths 1]]
set whs [get_property SLACK [get_timing_paths -delay_type min -max_paths 1]]
set unrouted [llength [get_nets -quiet -hierarchical -filter {ROUTE_STATUS == "UNROUTED"}]]
set partial [llength [get_nets -quiet -hierarchical -filter {ROUTE_STATUS == "PARTIAL"}]]
set drc_errors [get_drc_violations -quiet -filter {SEVERITY == "Error"}]
set drc_critical [get_drc_violations -quiet -filter {SEVERITY == "Critical Warning"}]
set status [open [file join $report_dir run_status.txt] w]
puts $status "wns_ns=$wns"
puts $status "whs_ns=$whs"
puts $status "unrouted_nets=$unrouted"
puts $status "partially_routed_nets=$partial"
puts $status "drc_error_count=[llength $drc_errors]"
puts $status "drc_critical_count=[llength $drc_critical]"
close $status
if {$wns < 0 || $whs < 0 || $unrouted != 0 || $partial != 0 ||
    [llength $drc_errors] != 0 || [llength $drc_critical] != 0} {
    error "Repair implementation failed signoff: WNS=$wns WHS=$whs route=$unrouted/$partial DRC=[llength $drc_errors]/[llength $drc_critical]"
}
set bit_file [file join $run_dir cns2fpga_${run_name}.bit]
write_bitstream -force $bit_file
puts "RUNTIME_ETH_REPAIR_BITSTREAM_PASS file=$bit_file WNS=$wns WHS=$whs"
