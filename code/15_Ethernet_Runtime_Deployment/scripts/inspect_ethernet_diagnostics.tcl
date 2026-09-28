# Read-only JTAG probe of the Ethernet diagnostic registers in the repair image.
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
proc read_reg {axis name address} {
    set txn [create_hw_axi_txn inspect_$name $axis -type READ -address $address -len 1]
    run_hw_axi $txn
    set data [string trim [get_property DATA $txn]]
    delete_hw_axi_txn $txn
    if {![regexp {^[0-9A-Fa-f]{8}$} $data]} {error "Invalid $name readback: $data"}
    puts "ETH_DIAG_$name=[string toupper $data]"
    scan $data %x value
    return $value
}
read_reg $axis ID 00000000
read_reg $axis STATUS 00000070
read_reg $axis RX_COUNTS 00000084
read_reg $axis TX_COUNTS 00000088
read_reg $axis TEST_FRAMES 0000008c
read_reg $axis LAST_TX_DEST_LO 00000090
read_reg $axis LAST_TX_TYPE_AND_DEST_HI 00000094
read_reg $axis LAST_RX_SRC_LO 00000098
read_reg $axis LAST_RX_TYPE_AND_SRC_HI 0000009c
read_reg $axis ERROR_COUNTS 000000a4
read_reg $axis FLOW_LIVE 000000a8
read_reg $axis FLOW_COUNTS 000000ac
set clk_a [read_reg $axis RX_CLOCK_A 00000074]
after 137
set clk_b [read_reg $axis RX_CLOCK_B 00000074]
puts "ETH_DIAG_RX_CLOCK_CHANGED=[expr {$clk_a != $clk_b}]"
close_hw_target
disconnect_hw_server
close_hw_manager
