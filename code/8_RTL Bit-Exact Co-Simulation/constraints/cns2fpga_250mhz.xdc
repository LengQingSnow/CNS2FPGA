# Step 8/9 timing target: 250 MHz (4.000 ns).
# This constraint sets the implementation target; timing closure must still be
# demonstrated by Vivado synthesis and place-and-route for the selected KU115.
create_clock -name sys_clk -period 4.000 -waveform {0.000 2.000} [get_ports clk]

# Reserve 200 ps for clock uncertainty/jitter during implementation.
set_clock_uncertainty 0.200 [get_clocks sys_clk]
