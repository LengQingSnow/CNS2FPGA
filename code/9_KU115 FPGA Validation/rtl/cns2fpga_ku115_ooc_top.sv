`timescale 1ns/1ps

// Out-of-context implementation wrapper. It binds the frozen Step 6 memory
// images so Vivado synthesizes the real network rather than empty ROMs.
module cns2fpga_ku115_ooc_top (
    input  wire                 clk,
    input  wire                 rst,
    input  wire                 start_timestep,
    input  wire signed [33:0]   input_current,
    output wire                 busy,
    output wire                 timestep_done,
    output wire                 spike_valid,
    output wire [12:0]          spike_neuron,
    output wire                 spike_is_pC1,
    output wire                 state_saturation_seen,
    output wire                 accumulator_saturation_seen
);
    wire core_clk;

    // A real board top will place an IBUF/IBUFDS before this global buffer.
    // Keeping BUFG in the OOC wrapper makes internal clock routing realistic.
    BUFG clock_buffer (
        .I(clk),
        .O(core_clk)
    );

    cns2fpga_core_sync #(
        .NEURON_COUNT(6279),
        .SYNAPSE_COUNT(350185),
        .NEURON_INDEX_BITS(13),
        .STATE_BITS(34),
        .STATE_FRAC(24),
        .WEIGHT_BITS(30),
        .WEIGHT_FRAC(24),
        .DECAY_BITS(32),
        .DECAY_FRAC(30),
        .ACC_BITS(35),
        .NEURON_PARAM_BITS(128),
        .NEURON_PARAM_FILE("E:/Workspace/CNS2FPGA/code/6_Connectome Compiler/outputs/courtship_song_hw_ir_v1/neuron_param.mem"),
        .SYNAPSE_FILE("E:/Workspace/CNS2FPGA/code/6_Connectome Compiler/outputs/courtship_song_hw_ir_v1/synapse.mem"),
        .OFFSET_FILE("E:/Workspace/CNS2FPGA/code/6_Connectome Compiler/outputs/courtship_song_hw_ir_v1/offset.mem"),
        .TYPE_SIGN_FILE("E:/Workspace/CNS2FPGA/code/6_Connectome Compiler/outputs/courtship_song_hw_ir_v1/type_sign.mem")
    ) core (
        .clk(core_clk),
        .rst(rst),
        .clear_state(1'b0),
        .start_timestep(start_timestep),
        .input_current(input_current),
        .busy(busy),
        .timestep_done(timestep_done),
        .spike_valid(spike_valid),
        .spike_neuron(spike_neuron),
        .spike_is_pC1(spike_is_pC1),
        .state_saturation_seen(state_saturation_seen),
        .accumulator_saturation_seen(accumulator_saturation_seen)
    );
endmodule
