# Probe the installed Vivado 2021.2 JTAG-to-AXI IP in an isolated directory.
set probe_dir [file normalize [file join [file dirname [info script]] .. build jtag_ip_probe]]
file mkdir $probe_dir
create_project -in_memory -part xcku115-flva1517-2-i
set defs [get_ipdefs -all xilinx.com:ip:jtag_axi:*]
puts "IP_PROBE_DEFS $defs"
if {[llength $defs] == 0} {exit 2}
set ip [create_ip -name jtag_axi -vendor xilinx.com -library ip -version 1.2 -module_name jtag_axi_probe -dir $probe_dir]
set_property CONFIG.PROTOCOL 2 [get_ips jtag_axi_probe]
set_property CONFIG.M_AXI_DATA_WIDTH 32 [get_ips jtag_axi_probe]
set_property CONFIG.M_AXI_ADDR_WIDTH 32 [get_ips jtag_axi_probe]
foreach prop {CONFIG.PROTOCOL CONFIG.M_AXI_DATA_WIDTH CONFIG.M_AXI_ADDR_WIDTH IPDEF} {
    if {![catch {get_property $prop [get_ips jtag_axi_probe]} val]} {
        puts "IP_PROBE_PROPERTY $prop $val"
    }
}
if {[catch {generate_target instantiation_template [get_ips jtag_axi_probe]} err]} {
    puts "IP_PROBE_TEMPLATE_ERROR $err"
    exit 3
}
puts "IP_PROBE_DIR $probe_dir"
exit 0
