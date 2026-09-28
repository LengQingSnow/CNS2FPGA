# AXKU115 V1.0 pinout from support/AXKU115_UG.pdf.
set_property PACKAGE_PIN AL14 [get_ports clk_50m]
set_property IOSTANDARD LVCMOS33 [get_ports clk_50m]
create_clock -name clk_50m -period 20.000 -waveform {0.000 10.000} [get_ports clk_50m]

set_property PACKAGE_PIN AL33 [get_ports key1_n]
set_property IOSTANDARD LVCMOS18 [get_ports key1_n]
set_property PULLUP true [get_ports key1_n]

set_property PACKAGE_PIN AH21 [get_ports led1]
set_property PACKAGE_PIN AJ23 [get_ports led2]
set_property IOSTANDARD LVCMOS18 [get_ports {led1 led2}]
set_property DRIVE 8 [get_ports {led1 led2}]
set_property SLEW SLOW [get_ports {led1 led2}]

# AXKU115 V1.0 page 17, KSZ9031RNX RGMII in fixed 1.8 V Bank 25.
set_property PACKAGE_PIN AP39 [get_ports phy_tx_clk]
set_property PACKAGE_PIN AL39 [get_ports {phy_txd[0]}]
set_property PACKAGE_PIN AM39 [get_ports {phy_txd[1]}]
set_property PACKAGE_PIN AN39 [get_ports {phy_txd[2]}]
set_property PACKAGE_PIN AN38 [get_ports {phy_txd[3]}]
set_property PACKAGE_PIN AP38 [get_ports phy_tx_ctl]
set_property PACKAGE_PIN AR37 [get_ports phy_rx_clk]
set_property PACKAGE_PIN AP35 [get_ports {phy_rxd[0]}]
set_property PACKAGE_PIN AK37 [get_ports {phy_rxd[1]}]
set_property PACKAGE_PIN AK38 [get_ports {phy_rxd[2]}]
set_property PACKAGE_PIN AJ39 [get_ports {phy_rxd[3]}]
set_property PACKAGE_PIN AT37 [get_ports phy_rx_ctl]
set_property PACKAGE_PIN AW38 [get_ports phy_reset_n]
set_property PACKAGE_PIN AU39 [get_ports phy_mdc]
set_property PACKAGE_PIN AT39 [get_ports phy_mdio]
set_property IOSTANDARD LVCMOS18 [get_ports {phy_mdc phy_mdio}]
set_property PULLUP true [get_ports phy_mdio]
set_property IOSTANDARD LVCMOS18 [get_ports {phy_tx_clk phy_txd[*] phy_tx_ctl phy_rx_clk phy_rxd[*] phy_rx_ctl phy_reset_n}]
set_property DRIVE 8 [get_ports {phy_tx_clk phy_txd[*] phy_tx_ctl phy_reset_n}]
set_property DRIVE 8 [get_ports {phy_mdc phy_mdio}]
set_property SLEW FAST [get_ports {phy_tx_clk phy_txd[*] phy_tx_ctl}]
create_clock -name phy_rx_clk -period 8.000 [get_ports phy_rx_clk]

# KSZ9031RNX RGMII-ID receive data are valid around each RXC sampling edge.
# Datasheet Table 7-1 guarantees >=1.2 ns setup and hold; use a conservative
# 1.0 ns window, where max is the preceding transition and min is the next.
# Both DDR edges are constrained. The five RX input IDELAYE3 taps are fixed
# to 400 COUNT units after synthesis to compensate BUFG clock insertion.
set_input_delay -clock [get_clocks phy_rx_clk] -max -1.0 [get_ports {phy_rxd[*] phy_rx_ctl}]
set_input_delay -clock [get_clocks phy_rx_clk] -min 1.0 [get_ports {phy_rxd[*] phy_rx_ctl}]
set_input_delay -clock [get_clocks phy_rx_clk] -clock_fall -max -1.0 -add_delay [get_ports {phy_rxd[*] phy_rx_ctl}]
set_input_delay -clock [get_clocks phy_rx_clk] -clock_fall -min 1.0 -add_delay [get_ports {phy_rxd[*] phy_rx_ctl}]
# TX limits use AMD PG160's "delay added by the MAC" case. A 95.625 degree
# forwarded clock adds 2.125 ns at 125 MHz, within RGMII-ID timing limits.
create_generated_clock -name phy_tx_clk_forwarded -source [get_pins clock_manager/CLKOUT2] -divide_by 1 [get_ports phy_tx_clk]
set_output_delay -clock [get_clocks phy_tx_clk_forwarded] -max 0.75 [get_ports {phy_txd[*] phy_tx_ctl}]
set_output_delay -clock [get_clocks phy_tx_clk_forwarded] -min -0.7 [get_ports {phy_txd[*] phy_tx_ctl}]
set_output_delay -clock [get_clocks phy_tx_clk_forwarded] -clock_fall -max 0.75 -add_delay [get_ports {phy_txd[*] phy_tx_ctl}]
set_output_delay -clock [get_clocks phy_tx_clk_forwarded] -clock_fall -min -0.7 -add_delay [get_ports {phy_txd[*] phy_tx_ctl}]

# RGMII RXC is PHY-source-clocked and asynchronous to the MAC GTX clock.
# The MAC's dual-clock FIFO and the command-toggle bridge handle CDC.
set_clock_groups -asynchronous -group [get_clocks phy_rx_clk] -group [get_clocks -of_objects [get_pins ethernet_clock_buffer/O]]
set_clock_groups -asynchronous -group [get_clocks -of_objects [get_pins ethernet_clock_buffer/O]] -group [get_clocks -of_objects [get_pins system_clock_buffer/O]]

set_false_path -from [get_ports key1_n]
set_false_path -to [get_ports {led1 led2}]
# PHY reset is an asynchronous control, not a source-synchronous data output.
set_false_path -to [get_ports phy_reset_n]
# A shared MMCM/BUFG clock has fully correlated edge jitter on same-domain
# hold paths. Keep 125 ps extra setup guard; use a separate 50 ps extra hold
# guard instead of imposing the full setup guard on intra-slice JTAG FIFO paths.
set_clock_uncertainty -setup 0.125 [get_clocks -of_objects [get_pins system_clock_buffer/O]]
set_clock_uncertainty -hold 0.050 [get_clocks -of_objects [get_pins system_clock_buffer/O]]

set_property BITSTREAM.GENERAL.COMPRESS TRUE [current_design]
set_property CFGBVS VCCO [current_design]
set_property CONFIG_VOLTAGE 3.3 [current_design]
