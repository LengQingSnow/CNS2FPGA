# Read-only Clause 22 PHY address scan. KSZ9031RNX PHY ID1 should be 0x0022.
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
proc rd {axis addr} {
    set txn [create_hw_axi_txn mdio_read $axis -type READ -address $addr -len 1]
    run_hw_axi $txn
    set data [string trim [get_property DATA $txn]]
    delete_hw_axi_txn $txn
    if {![regexp {^[0-9A-Fa-f]{8}$} $data]} {error "Invalid MDIO AXI readback: $data"}
    scan $data %x value
    return $value
}
proc wr {axis addr value} {
    set txn [create_hw_axi_txn mdio_write $axis -type WRITE -address $addr -data [format %08X $value] -len 1]
    run_hw_axi $txn
    delete_hw_axi_txn $txn
}
set id [rd $axis 00000000]
if {$id != 0x434e5352} {error "Unexpected runtime ID [format %08X $id]"}
set found {}
for {set phy 0} {$phy < 32} {incr phy} {
    set command [expr {(1 << 31) | ($phy << 25) | (2 << 20)}]
    wr $axis 00000080 $command
    after 5
    set status [rd $axis 00000078]
    set value [rd $axis 0000007c]
    if {($status & 1) != 0 || ($status & 2) == 0} {
        error "MDIO transaction incomplete at PHY $phy: [format %08X $status]"
    }
    puts "MDIO_PHY_$phy status=[format %08X $status] id1=[format %04X [expr {$value & 0xffff}]]"
    if {($status & 4) == 0 && ($value & 0xffff) == 0x0022} {lappend found $phy}
}
puts "MDIO_KSZ9031_ADDRESSES=$found"
if {[llength $found] == 1} {
    set phy [lindex $found 0]
    foreach reg {0 1 3 4 5 9 10 17 19 31} {
        set command [expr {(1 << 31) | ($phy << 25) | ($reg << 20)}]
        wr $axis 00000080 $command
        after 5
        set status [rd $axis 00000078]
        set value [rd $axis 0000007c]
        if {($status & 7) != 2} {error "Invalid MDIO status for reg $reg: [format %08X $status]"}
        puts "MDIO_REG_[format %02X $reg]=[format %04X [expr {$value & 0xffff}]]"
    }
}
close_hw_target
disconnect_hw_server
close_hw_manager
