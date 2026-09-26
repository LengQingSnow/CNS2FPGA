# Pure non-project synthesis smoke test of an XCI created in an in-memory project.
set root_dir [file normalize [file join [file dirname [info script]] ..]]
set xci_file [file join $root_dir build jtag_ip_probe jtag_axi_probe jtag_axi_probe.xci]
set rtl_file [file join $root_dir build jtag_nonproject_probe jtag_axi_smoke_top.v]
set dcp_file [file join $root_dir build jtag_nonproject_probe post_synth.dcp]
set part_name xcku115-flva1517-2-i

if {![file exists $xci_file]} {error "Missing XCI $xci_file"}
set_part $part_name
read_ip [list $xci_file]
puts "NONPROJECT_READ_IP_PASS $xci_file"
generate_target all [get_ips jtag_axi_probe]
puts "NONPROJECT_GENERATE_PASS"
synth_ip [get_ips jtag_axi_probe]
puts "NONPROJECT_SYNTH_IP_PASS"
read_verilog [list $rtl_file]
synth_design -top jtag_axi_smoke_top -part $part_name -flatten_hierarchy rebuilt
set cores [get_cells -hier -filter {REF_NAME =~ *jtag_axi*}]
puts "NONPROJECT_SYNTH_IP_CELLS [llength $cores]"
write_checkpoint -force $dcp_file
puts "NONPROJECT_SYNTH_PASS $dcp_file"
exit 0
