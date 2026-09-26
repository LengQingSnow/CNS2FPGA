create_clock -name sys_clk -period 4.000 -waveform {0.000 2.000} [get_ports clk]
set_clock_uncertainty 0.200 [get_clocks sys_clk]
