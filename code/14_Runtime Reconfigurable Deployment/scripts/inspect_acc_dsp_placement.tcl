set script_dir [file dirname [file normalize [info script]]]
set root_dir [file normalize [file join $script_dir ..]]
open_checkpoint [file join $root_dir build runtime_jtag_200mhz post_route.dcp]
foreach cell [get_cells -hierarchical -filter {REF_NAME == DSP48E2}] {
    puts "DSP_CELL $cell LOC=[get_property LOC $cell]"
}
foreach y {24 28 30 32 34 36 38 40 42 44 46 48 50 52 54} {
    foreach x {5 6 7 8 9 10 11} {
        set name "DSP48E2_X${x}Y${y}"
        set site [get_sites -quiet $name]
        if {[llength $site] != 0} {
            puts "DSP_SITE $name occupied=[get_cells -quiet -of_objects $site]"
        }
    }
}
exit 0
