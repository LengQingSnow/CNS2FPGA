set script_dir [file dirname [file normalize [info script]]]
set root_dir [file normalize [file join $script_dir ..]]
set bit_file [file normalize [file join $root_dir build runtime_jtag_200mhz cns2fpga_runtime_jtag_200mhz.bit]]
if {![file isfile $bit_file]} {
    set bit_file [file normalize [file join $root_dir .. .. hardware bitstreams cns2fpga_runtime_jtag_200mhz.bit]]
}
if {![file isfile $bit_file]} {error "Missing bitstream: $bit_file"}

open_hw_manager
connect_hw_server -url localhost:3121
refresh_hw_server [get_hw_servers]
set targets [get_hw_targets -quiet]
if {[llength $targets] != 1} {error "Expected exactly one JTAG target, got $targets"}
set target [lindex $targets 0]
open_hw_target $target
set devices {}
foreach item [get_hw_devices -of_objects $target] {
    if {[string match -nocase *xcku115* $item]} {lappend devices $item}
}
if {[llength $devices] != 1} {error "Expected one xcku115 device, got $devices"}
set device [lindex $devices 0]
current_hw_device $device
set_property PROGRAM.FILE $bit_file $device
program_hw_devices $device
refresh_hw_device $device
set axes [get_hw_axis -of_objects $device]
if {[llength $axes] != 1} {
    error "Expected one JTAG AXI core after programming, got $axes"
}
puts "RUNTIME_JTAG_PROGRAM_PASS target=$target device=$device axi=[lindex $axes 0] bit=$bit_file"
close_hw_target
disconnect_hw_server
close_hw_manager
exit 0
