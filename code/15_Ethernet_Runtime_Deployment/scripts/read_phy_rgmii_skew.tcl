# Read KSZ9031 RGMII pad-skew registers through the Clause 22 MMD portal.
# Portal selector writes do not change the pad-skew register contents.
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
    set txn [create_hw_axi_txn skew_rd $axis -type READ -address $addr -len 1]
    run_hw_axi $txn
    set data [string trim [get_property DATA $txn]]
    delete_hw_axi_txn $txn
    if {![regexp {^[0-9A-Fa-f]{8}$} $data]} {error "Invalid AXI readback $data"}
    scan $data %x value
    return $value
}
proc wr {axis addr value} {
    set txn [create_hw_axi_txn skew_wr $axis -type WRITE -address $addr -data [format %08X $value] -len 1]
    run_hw_axi $txn
    delete_hw_axi_txn $txn
}
proc phy_cmd {axis reg write value} {
    set cmd [expr {(1 << 31) | ($write << 30) | (1 << 25) | ($reg << 20) | ($value & 0xffff)}]
    wr $axis 00000080 $cmd
    after 5
    set status [rd $axis 00000078]
    if {($status & 7) != 2} {error "MDIO command failed reg=$reg status=[format %08X $status]"}
    if {!$write} {return [expr {[rd $axis 0000007c] & 0xffff}]}
}
proc mmd_read {axis reg} {
    phy_cmd $axis 13 1 0x0002
    phy_cmd $axis 14 1 $reg
    phy_cmd $axis 13 1 0x4002
    return [phy_cmd $axis 14 0 0]
}
if {[rd $axis 00000000] != 0x434e5352 || [phy_cmd $axis 2 0 0] != 0x0022} {
    error "Unexpected FPGA or PHY identity"
}
puts "PHY_BMCR=[format %04X [phy_cmd $axis 0 0 0]]"
puts "PHY_BMSR=[format %04X [phy_cmd $axis 1 0 0]]"
puts "PHY_PCS=[format %04X [phy_cmd $axis 19 0 0]]"
foreach reg {4 5 6 8} {
    puts "PHY_MMD2_RGMII_SKEW_[format %02X $reg]=[format %04X [mmd_read $axis $reg]]"
}
# Leave the MMD portal in register-address mode without altering skew values.
phy_cmd $axis 13 1 0x0002
close_hw_target
disconnect_hw_server
close_hw_manager
exit 0
