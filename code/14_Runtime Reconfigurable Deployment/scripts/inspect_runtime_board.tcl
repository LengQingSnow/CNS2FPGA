# Read-only runtime firmware and image-loader status.
open_hw_manager
connect_hw_server -url localhost:3121
set targets [get_hw_targets -quiet]
if {[llength $targets] != 1} {error "Expected one JTAG target, got $targets"}
set target [lindex $targets 0]
open_hw_target $target
set devices [get_hw_devices -of_objects $target]
if {[llength $devices] != 1 || ![string match -nocase *xcku115* [lindex $devices 0]]} {
    error "Expected one xcku115, got $devices"
}
set device [lindex $devices 0]
current_hw_device $device
refresh_hw_device $device
set axes [get_hw_axis -of_objects $device]
if {[llength $axes] != 1} {error "Expected one JTAG AXI core, got $axes"}
set axis [lindex $axes 0]
reset_hw_axi $axis
foreach {name address} {
    ID 00000000 STATUS 00000008 IMAGE_STATUS 00000030
    IMAGE_CHECKSUM 00000048 IMAGE_EPOCH 0000004C
    ACTIVE_NEURONS 00000060 ACTIVE_SYNAPSES 00000064
} {
    set txn [create_hw_axi_txn inspect_$name $axis -type READ -address $address -len 1]
    run_hw_axi $txn
    set data [string trim [get_property DATA $txn]]
    if {![regexp {^[0-9A-Fa-f]{8}$} $data]} {error "Invalid $name readback: $data"}
    puts "RUNTIME_BOARD_$name=[string toupper $data]"
    delete_hw_axi_txn $txn
}
close_hw_target
disconnect_hw_server
close_hw_manager
