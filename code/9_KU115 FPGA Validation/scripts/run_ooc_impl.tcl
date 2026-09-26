set script_dir [file dirname [file normalize [info script]]]
set root_dir [file normalize [file join $script_dir ..]]
set target_mhz 250
if {$argc > 0} { set target_mhz [lindex $argv 0] }
if {$target_mhz ni {195 200 250}} { error "target_mhz must be 195, 200, or 250" }
set target_period [expr {1000.0 / double($target_mhz)}]
set run_tag "ooc_${target_mhz}mhz"
set code_root [file normalize [file join $root_dir ..]]
set rtl_file [file normalize [file join $root_dir rtl cns2fpga_core_sync_250mhz.sv]]
set wrapper_file [file normalize [file join $root_dir rtl cns2fpga_ku115_ooc_top.sv]]
set xdc_file [file normalize [file join $root_dir constraints "core_${target_mhz}mhz_ooc.xdc"]]
set run_dir [file normalize [file join $root_dir build $run_tag]]
set report_dir [file normalize [file join $root_dir reports $run_tag]]
file mkdir $run_dir
file mkdir $report_dir

set part_name "xcku115-flva1517-2-e"
set top_name "cns2fpga_ku115_ooc_top"

read_verilog -sv [list $rtl_file $wrapper_file]
read_xdc [list $xdc_file]

synth_design -top $top_name -part $part_name -mode out_of_context -flatten_hierarchy rebuilt
write_checkpoint -force [file join $run_dir post_synth.dcp]
report_utilization -file [file join $report_dir post_synth_utilization.rpt]
report_timing_summary -delay_type max -max_paths 20 -file [file join $report_dir post_synth_timing_summary.rpt]

opt_design
place_design
phys_opt_design
route_design
phys_opt_design

write_checkpoint -force [file join $run_dir post_route.dcp]
report_utilization -file [file join $report_dir post_route_utilization.rpt]
report_timing_summary -delay_type min_max -max_paths 50 -report_unconstrained -file [file join $report_dir post_route_timing_summary.rpt]
report_clock_utilization -file [file join $report_dir clock_utilization.rpt]
report_methodology -file [file join $report_dir methodology.rpt]

set worst_path [get_timing_paths -delay_type max -max_paths 1]
set wns [get_property SLACK $worst_path]
set timing_ok [expr {$wns >= 0.0}]
set summary [open [file join $report_dir run_status.txt] w]
puts $summary "part=$part_name"
puts $summary [format "target_clock_mhz=%.3f" $target_mhz]
puts $summary [format "target_period_ns=%.3f" $target_period]
puts $summary "wns_ns=$wns"
puts $summary "timing_met=$timing_ok"
puts $summary "bitstream_generated=false"
puts $summary "bitstream_blocker=board_pin_constraints_required"
close $summary

if {!$timing_ok} {
    puts "ERROR: $target_mhz MHz timing did not close"
    exit 2
}
puts "OOC_IMPLEMENTATION_PASS target_mhz=$target_mhz"
exit
