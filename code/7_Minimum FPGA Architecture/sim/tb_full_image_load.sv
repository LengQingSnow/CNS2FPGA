`timescale 1ns/1ps

module tb_full_image_load;
    reg clk = 1'b0;
    reg rst = 1'b1;
    wire busy, timestep_done, spike_valid, spike_is_pC1;
    wire [12:0] spike_neuron;
    wire state_saturation_seen, accumulator_saturation_seen;
    integer index;
    integer input_count;
    integer pc1_count;
    integer last_start;
    integer last_count;

    always #5 clk = ~clk;

    cns2fpga_core #(
        .NEURON_COUNT(6279), .SYNAPSE_COUNT(350185), .INPUT_COUNT(93),
        .NEURON_INDEX_BITS(13), .STATE_BITS(34), .STATE_FRAC(24),
        .WEIGHT_BITS(30), .WEIGHT_FRAC(24), .DECAY_BITS(32), .DECAY_FRAC(30),
        .ACC_BITS(35),
        .NEURON_PARAM_FILE("../6_Connectome Compiler/outputs/courtship_song_hw_ir_v1/neuron_param.mem"),
        .SYNAPSE_FILE("../6_Connectome Compiler/outputs/courtship_song_hw_ir_v1/synapse.mem"),
        .OFFSET_FILE("../6_Connectome Compiler/outputs/courtship_song_hw_ir_v1/offset.mem"),
        .TYPE_SIGN_FILE("../6_Connectome Compiler/outputs/courtship_song_hw_ir_v1/type_sign.mem")
    ) dut (
        .clk(clk), .rst(rst), .start_timestep(1'b0), .input_current(34'sd0),
        .busy(busy), .timestep_done(timestep_done), .spike_valid(spike_valid),
        .spike_neuron(spike_neuron), .spike_is_pC1(spike_is_pC1),
        .state_saturation_seen(state_saturation_seen),
        .accumulator_saturation_seen(accumulator_saturation_seen)
    );

    initial begin
        #20;
        input_count = 0;
        pc1_count = 0;
        for (index = 0; index < 6279; index = index + 1) begin
            if (dut.type_sign_mem[index][2]) input_count = input_count + 1;
            if (dut.type_sign_mem[index][7]) pc1_count = pc1_count + 1;
            if (^dut.neuron_param_mem[index] === 1'bx) begin
                $display("FAIL unknown neuron parameter at %0d", index);
                $finish;
            end
        end
        if (input_count != 93 || pc1_count != 112) begin
            $display("FAIL group counts input=%0d pC1=%0d", input_count, pc1_count);
            $finish;
        end
        if (^dut.synapse_mem[0] === 1'bx || ^dut.synapse_mem[350184] === 1'bx) begin
            $display("FAIL synapse image contains unknown endpoint record");
            $finish;
        end
        last_start = dut.offset_mem[6278][18:0];
        last_count = dut.offset_mem[6278][28:19];
        if (dut.offset_mem[0][18:0] != 0 || last_start + last_count != 350185) begin
            $display("FAIL CSR endpoints first=%0d last_end=%0d", dut.offset_mem[0][18:0], last_start+last_count);
            $finish;
        end
        $display("PASS full image load neurons=6279 synapses=350185 inputs=%0d pC1=%0d", input_count, pc1_count);
        $finish;
    end
endmodule
