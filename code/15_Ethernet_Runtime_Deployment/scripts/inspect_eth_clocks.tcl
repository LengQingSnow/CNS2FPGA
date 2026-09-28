open_checkpoint [file normalize "code/15_Ethernet_Runtime_Deployment/build/runtime_eth_200mhz/post_synth.dcp"]
puts "TX_PORT_CLOCKS=[get_clocks -of_objects [get_ports phy_tx_clk]]"
puts "TX_ODDR_CELLS=[get_cells -hier -filter {NAME =~ *clk_oddr_inst*}]"
puts "RX_CLOCKS=[get_clocks -of_objects [get_ports phy_rx_clk]]"
puts "CLK90_CLOCKS=[get_clocks -of_objects [get_pins ethernet_clock90_buffer/O]]"
report_timing -from [get_clocks clk_125m_mmcm] -to [get_ports {phy_txd[*] phy_tx_ctl}] -max_paths 2
