# Restore KSZ9031 auto-negotiation after a temporary forced-speed test.
open_hw_manager
connect_hw_server -url localhost:3121
set targets [get_hw_targets -quiet]
if {[llength $targets] != 1} {error "Expected one JTAG target"}
set target [lindex $targets 0]
open_hw_target $target
set device [lindex [get_hw_devices -of_objects $target] 0]
if {![string match -nocase *xcku115* $device]} {error "Expected xcku115"}
current_hw_device $device
refresh_hw_device $device
set axis [lindex [get_hw_axis -of_objects $device] 0]
if {$axis eq ""} {error "JTAG AXI core missing"}
reset_hw_axi $axis
proc rd {axis addr} {
    set txn [create_hw_axi_txn restart_rd $axis -type READ -address $addr -len 1]
    run_hw_axi $txn
    set data [string trim [get_property DATA $txn]]
    delete_hw_axi_txn $txn
    scan $data %x value
    return $value
}
proc wr {axis addr value} {
    set txn [create_hw_axi_txn restart_wr $axis -type WRITE -address $addr -data [format %08X $value] -len 1]
    run_hw_axi $txn
    delete_hw_axi_txn $txn
}
proc phy_read {axis reg} {
    wr $axis 00000080 [expr {(1 << 31) | (1 << 25) | ($reg << 20)}]
    after 5
    if {([rd $axis 00000078] & 7) != 2} {error "PHY read failed"}
    return [expr {[rd $axis 0000007c] & 0xffff}]
}
if {[rd $axis 00000000] != 0x434e5352 || [phy_read $axis 2] != 0x0022} {
    error "Board/PHY identification failed"
}
set bmcr [phy_read $axis 0]
if {($bmcr & 0x5000) != 0x1000} {error "Unexpected PHY BMCR [format %04X $bmcr]"}
puts "AUTONEG_BMCR_BEFORE=[format %04X $bmcr]"
wr $axis 00000080 [expr {(1 << 31) | (1 << 30) | (1 << 25) | ($bmcr | 0x0200)}]
after 5
if {([rd $axis 00000078] & 3) != 2} {error "PHY restart write failed"}
after 5000
puts "AUTONEG_BMCR_AFTER=[format %04X [phy_read $axis 0]]"
puts "AUTONEG_BMSR_AFTER=[format %04X [phy_read $axis 1]]"
puts "AUTONEG_PCS_AFTER=[format %04X [phy_read $axis 19]]"
puts "AUTONEG_CTRL_AFTER=[format %04X [phy_read $axis 31]]"
close_hw_target
disconnect_hw_server
close_hw_manager
exit 0
