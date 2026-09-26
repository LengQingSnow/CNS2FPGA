transcript file sim/bit_exact_250mhz_transcript.log
if {[file exists work]} {vdel -lib work -all}
vlib work
vlog -sv rtl/cns2fpga_core_sync_250mhz.sv sim/tb_bit_exact_250mhz.sv
vsim -c work.tb_bit_exact_250mhz -do "run -all; quit -f"
