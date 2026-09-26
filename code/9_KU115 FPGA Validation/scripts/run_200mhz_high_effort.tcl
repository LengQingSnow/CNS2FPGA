set script_dir [file dirname [file normalize [info script]]]
set root_dir [file normalize [file join $script_dir ..]]
set input_dcp [file normalize [file join $root_dir build ooc_200mhz post_synth.dcp]]
set run_dir [file normalize [file join $root_dir build ooc_200mhz_high_effort]]
set report_dir [file normalize [file join $root_dir reports ooc_200mhz_high_effort]]
file mkdir $run_dir
file mkdir $report_dir

open_checkpoint $input_dcp
opt_design -directive ExploreWithRemap
place_design -directive ExtraNetDelay_high
phys_opt_design -directive AggressiveExplore
route_design -directive AggressiveExplore
phys_opt_design -directive AggressiveExplore

write_checkpoint -force [file join $run_dir post_route.dcp]
report_utilization -file [file join $report_dir post_route_utilization.rpt]
report_timing_summary -delay_type min_max -max_paths 50 -report_unconstrained \
    -file [file join $report_dir post_route_timing_summary.rpt]
report_clock_utilization -file [file join $report_dir clock_utilization.rpt]
report_methodology -file [file join $report_dir methodology.rpt]

set worst_path [get_timing_paths -delay_type max -max_paths 1]
set wns [get_property SLACK $worst_path]
set timing_ok [expr {$wns >= 0.0}]
set summary [open [file join $report_dir run_status.txt] w]
puts $summary "part=xcku115-flva1517-2-e"
puts $summary "target_clock_mhz=200.000"
puts $summary "target_period_ns=5.000"
puts $summary "strategy=high_effort"
puts $summary "wns_ns=$wns"
puts $summary "timing_met=$timing_ok"
puts $summary "bitstream_generated=false"
puts $summary "bitstream_blocker=board_pin_constraints_required"
close $summary

if {!$timing_ok} {
    puts "ERROR: 200 MHz high-effort timing did not close; WNS=$wns"
    exit 2
}
puts "OOC_IMPLEMENTATION_PASS target_mhz=200 strategy=high_effort WNS=$wns"
exit
