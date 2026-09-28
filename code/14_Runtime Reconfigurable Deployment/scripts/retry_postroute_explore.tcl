# Revisit the timing-clean routed design with Vivado's supported Explore
# physical optimization; keep the original 5 ns constraint unchanged.
set script_dir [file dirname [file normalize [info script]]]
set root_dir [file normalize [file join $script_dir ..]]
set run_dir [file join $root_dir build runtime_jtag_200mhz]
set report_dir [file join $root_dir reports runtime_jtag_200mhz]
open_checkpoint [file join $run_dir post_route.dcp]

phys_opt_design -directive Explore
write_checkpoint -force [file join $run_dir post_route_explore.dcp]
report_route_status -file [file join $report_dir route_status_explore.rpt]
report_timing_summary -delay_type min_max -max_paths 50 -report_unconstrained \
    -file [file join $report_dir post_route_explore_timing_summary.rpt]
report_bus_skew -file [file join $report_dir post_route_explore_bus_skew.rpt]
report_drc -file [file join $report_dir drc_explore.rpt]

set wns [get_property SLACK [get_timing_paths -delay_type max -max_paths 1]]
set whs [get_property SLACK [get_timing_paths -delay_type min -max_paths 1]]
set unrouted [llength [get_nets -quiet -hierarchical -filter {ROUTE_STATUS == "UNROUTED"}]]
set partial [llength [get_nets -quiet -hierarchical -filter {ROUTE_STATUS == "PARTIAL"}]]
set drc_errors [get_drc_violations -quiet -filter {SEVERITY == "Error"}]
set status [open [file join $report_dir run_status_explore.txt] w]
puts $status "part=xcku115-flva1517-2-i"
puts $status "core_clock_mhz=200.000"
puts $status "directive=post_route_Explore"
puts $status "wns_ns=$wns"
puts $status "whs_ns=$whs"
puts $status "unrouted_nets=$unrouted"
puts $status "partially_routed_nets=$partial"
puts $status "drc_error_count=[llength $drc_errors]"
close $status
if {$wns < 0.0 || $whs < 0.0 || $unrouted != 0 || $partial != 0 ||
    [llength $drc_errors] != 0} {
    error "Explore did not sign off: WNS=$wns WHS=$whs unrouted=$unrouted partial=$partial DRC=[llength $drc_errors]"
}
set bit_file [file join $run_dir cns2fpga_runtime_jtag_200mhz.bit]
write_bitstream -force $bit_file
puts "RUNTIME_JTAG_BITSTREAM_PASS file=$bit_file WNS=$wns WHS=$whs directive=Explore"
exit 0
