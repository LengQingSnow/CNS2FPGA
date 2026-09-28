# Continue a checked post-synthesis checkpoint in a fresh Vivado process.
set script_dir [file dirname [file normalize [info script]]]
set root_dir [file normalize [file join $script_dir ..]]
set run_dir [file join $root_dir build runtime_jtag_200mhz]
set report_dir [file join $root_dir reports runtime_jtag_200mhz]
set synth_dcp [file join $run_dir post_synth.dcp]
if {![file isfile $synth_dcp]} {error "Missing synthesis checkpoint: $synth_dcp"}
file mkdir $report_dir
open_checkpoint $synth_dcp
set accumulator_dsp [get_cells -quiet {experiment/core/accumulator_adder/sum__0}]
if {[llength $accumulator_dsp] == 1} {
    set accumulator_dsp_loc DSP48E2_X9Y36
    if {[info exists ::env(CNS2FPGA_ACC_DSP_LOC)]} {
        set accumulator_dsp_loc $::env(CNS2FPGA_ACC_DSP_LOC)
    }
    set_property LOC $accumulator_dsp_loc $accumulator_dsp
    puts "ACCUMULATOR_DSP_LOC=$accumulator_dsp_loc"
} else {
    puts "ACCUMULATOR_DSP_LOC=not_applicable"
}

opt_design
place_design
phys_opt_design
write_checkpoint -force [file join $run_dir post_place.dcp]
report_timing_summary -delay_type max -max_paths 20 \
    -file [file join $report_dir post_place_timing_summary.rpt]
if {[info exists ::env(CNS2FPGA_STOP_AFTER_PLACE)] &&
    $::env(CNS2FPGA_STOP_AFTER_PLACE) eq "1"} {
    puts "STOP_AFTER_PLACE=1"
    exit 0
}
route_design
phys_opt_design

write_checkpoint -force [file join $run_dir post_route.dcp]
report_route_status -file [file join $report_dir route_status.rpt]
report_utilization -file [file join $report_dir post_route_utilization.rpt]
report_timing_summary -delay_type min_max -max_paths 50 -report_unconstrained \
    -file [file join $report_dir post_route_timing_summary.rpt]
report_bus_skew -file [file join $report_dir post_route_bus_skew.rpt]
report_drc -file [file join $report_dir drc.rpt]

set wns [get_property SLACK [get_timing_paths -delay_type max -max_paths 1]]
set whs [get_property SLACK [get_timing_paths -delay_type min -max_paths 1]]
set unrouted [llength [get_nets -quiet -hierarchical -filter {ROUTE_STATUS == "UNROUTED"}]]
set partial [llength [get_nets -quiet -hierarchical -filter {ROUTE_STATUS == "PARTIAL"}]]
set drc_errors [get_drc_violations -quiet -filter {SEVERITY == "Error"}]
set status [open [file join $report_dir run_status.txt] w]
puts $status "part=xcku115-flva1517-2-i"
puts $status "core_clock_mhz=200.000"
puts $status "wns_ns=$wns"
puts $status "whs_ns=$whs"
puts $status "unrouted_nets=$unrouted"
puts $status "partially_routed_nets=$partial"
puts $status "drc_error_count=[llength $drc_errors]"
close $status
if {$wns < 0.0 || $whs < 0.0 || $unrouted != 0 || $partial != 0 ||
    [llength $drc_errors] != 0} {
    error "Runtime implementation did not sign off: WNS=$wns WHS=$whs unrouted=$unrouted partial=$partial DRC=[llength $drc_errors]"
}
set bit_file [file join $run_dir cns2fpga_runtime_jtag_200mhz.bit]
write_bitstream -force $bit_file
puts "RUNTIME_JTAG_BITSTREAM_PASS file=$bit_file WNS=$wns WHS=$whs"
exit 0
