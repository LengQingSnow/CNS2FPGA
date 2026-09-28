open_checkpoint [file normalize "code/15_Ethernet_Runtime_Deployment/build/runtime_eth_200mhz/post_route_initial.dcp"]
set_property CLKOUT2_PHASE 95.625 [get_cells clock_manager]
set rxports [get_ports {phy_rxd[*] phy_rx_ctl}]
set_input_delay -clock [get_clocks phy_rx_clk] -max -1.0 $rxports
set_input_delay -clock [get_clocks phy_rx_clk] -min 1.0 $rxports
set_input_delay -clock [get_clocks phy_rx_clk] -clock_fall -max -1.0 -add_delay $rxports
set_input_delay -clock [get_clocks phy_rx_clk] -clock_fall -min 1.0 -add_delay $rxports
set delays [get_cells -hier -filter {REF_NAME == IDELAYE3}]
set_property DELAY_VALUE 400 $delays
set_property SLEW FAST [get_ports {phy_tx_clk phy_txd[*] phy_tx_ctl}]
set_clock_uncertainty -setup 0.125 [get_clocks clk_200m_mmcm]
puts "TX_CLOCK_WAVEFORM=[get_property WAVEFORM [get_clocks phy_tx_clk_forwarded]]"
puts "RX_SETUP_SLACK=[get_property SLACK [get_timing_paths -from $rxports -delay_type max -max_paths 1]]"
puts "RX_HOLD_SLACK=[get_property SLACK [get_timing_paths -from $rxports -delay_type min -max_paths 1]]"
puts "TX_SETUP_SLACK=[get_property SLACK [get_timing_paths -to [get_ports {phy_txd[*] phy_tx_ctl}] -delay_type max -max_paths 1]]"
puts "GLOBAL_SETUP_SLACK=[get_property SLACK [get_timing_paths -delay_type max -max_paths 1]]"
puts "GLOBAL_HOLD_SLACK=[get_property SLACK [get_timing_paths -delay_type min -max_paths 1]]"
report_drc -file [file normalize "code/15_Ethernet_Runtime_Deployment/reports/runtime_eth_200mhz/eco_probe_drc.rpt"]
