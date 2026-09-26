`timescale 1ns/1ps

// Minimal, safe AXKU115 board-level smoke-test top.
// KEY1 resets the design. A debounced KEY2 press starts one timestep.
// LED1 is high while the core is busy; LED2 toggles after every completed step.
module cns2fpga_axku115_top (
    input  wire clk_50m,
    input  wire key1_n,
    input  wire key2_n,
    output wire led1,
    output wire led2
);
    wire clk_50m_ibuf;
    wire clkfb_mmcm;
    wire clkfb_buf;
    wire clk_195m_mmcm;
    wire clk_195m;
    wire mmcm_locked;

    IBUF clock_input_buffer (
        .I(clk_50m),
        .O(clk_50m_ibuf)
    );

    // 50 MHz * 19.5 / 5 = 195 MHz, VCO = 975 MHz.
    MMCME3_BASE #(
        .BANDWIDTH("OPTIMIZED"),
        .CLKIN1_PERIOD(20.000),
        .DIVCLK_DIVIDE(1),
        .CLKFBOUT_MULT_F(19.500),
        .CLKOUT0_DIVIDE_F(5.000),
        .CLKOUT0_DUTY_CYCLE(0.500),
        .STARTUP_WAIT("FALSE")
    ) clock_manager (
        .CLKIN1(clk_50m_ibuf),
        .CLKFBIN(clkfb_buf),
        .RST(~key1_n),
        .PWRDWN(1'b0),
        .CLKFBOUT(clkfb_mmcm),
        .CLKFBOUTB(),
        .CLKOUT0(clk_195m_mmcm),
        .CLKOUT0B(),
        .CLKOUT1(),
        .CLKOUT1B(),
        .CLKOUT2(),
        .CLKOUT2B(),
        .CLKOUT3(),
        .CLKOUT3B(),
        .CLKOUT4(),
        .CLKOUT5(),
        .CLKOUT6(),
        .LOCKED(mmcm_locked)
    );

    BUFG feedback_clock_buffer (
        .I(clkfb_mmcm),
        .O(clkfb_buf)
    );

    BUFG system_clock_buffer (
        .I(clk_195m_mmcm),
        .O(clk_195m)
    );

    // Asynchronous assertion from LOCKED, synchronous release on clk_195m.
    (* ASYNC_REG = "TRUE" *) reg [3:0] reset_sync = 4'hf;
    always @(posedge clk_195m or negedge mmcm_locked) begin
        if (!mmcm_locked)
            reset_sync <= 4'hf;
        else
            reset_sync <= {reset_sync[2:0], 1'b0};
    end
    wire core_reset = reset_sync[3];

    // KEY2 is active low. Require approximately 5.38 ms of stable input.
    (* ASYNC_REG = "TRUE" *) reg [2:0] key2_sync = 3'b111;
    reg key2_debounced = 1'b1;
    reg [19:0] debounce_count = 20'd0;
    reg start_timestep = 1'b0;

    always @(posedge clk_195m) begin
        if (core_reset) begin
            key2_sync <= 3'b111;
            key2_debounced <= 1'b1;
            debounce_count <= 20'd0;
            start_timestep <= 1'b0;
        end else begin
            key2_sync <= {key2_sync[1:0], key2_n};
            start_timestep <= 1'b0;
            if (key2_sync[2] == key2_debounced) begin
                debounce_count <= 20'd0;
            end else if (&debounce_count) begin
                debounce_count <= 20'd0;
                key2_debounced <= key2_sync[2];
                if (key2_debounced && !key2_sync[2])
                    start_timestep <= 1'b1;
            end else begin
                debounce_count <= debounce_count + 1'b1;
            end
        end
    end

    wire busy;
    wire timestep_done;
    wire spike_valid;
    wire [12:0] spike_neuron;
    wire spike_is_pc1;
    wire state_saturation_seen;
    wire accumulator_saturation_seen;

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
        .clk(clk_195m),
        .rst(core_reset),
        .clear_state(1'b0),
        .start_timestep(start_timestep),
        .input_current(34'sd0),
        .busy(busy),
        .timestep_done(timestep_done),
        .spike_valid(spike_valid),
        .spike_neuron(spike_neuron),
        .spike_is_pC1(spike_is_pc1),
        .state_saturation_seen(state_saturation_seen),
        .accumulator_saturation_seen(accumulator_saturation_seen)
    );

    reg done_toggle = 1'b0;
    reg [13:0] activity_signature = 14'd0;
    reg fault_seen = 1'b0;
    always @(posedge clk_195m) begin
        if (core_reset) begin
            done_toggle <= 1'b0;
            activity_signature <= 14'd0;
            fault_seen <= 1'b0;
        end else begin
            if (start_timestep)
                activity_signature <= 14'd0;
            else if (spike_valid)
                activity_signature <= activity_signature ^ {spike_is_pc1, spike_neuron};
            if (state_saturation_seen || accumulator_saturation_seen)
                fault_seen <= 1'b1;
            if (timestep_done)
                done_toggle <= ~done_toggle;
        end
    end

    assign led1 = busy | fault_seen;
    assign led2 = done_toggle ^ (^activity_signature);
endmodule
