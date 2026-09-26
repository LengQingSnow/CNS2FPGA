`timescale 1ns/1ps

// One 34-bit stimulus value per 1 ms model timestep. A host writes the
// stimulus before START and reads the fixed-size summary after DONE.
// All RAM ports and the core run on the same 200 MHz clock.
module cns2fpga_trial_engine #(
    parameter integer MAX_STEPS = 8192,
    parameter integer MAX_EVENTS = 65536,
    parameter NEURON_PARAM_FILE = "",
    parameter SYNAPSE_FILE = "",
    parameter OFFSET_FILE = "",
    parameter TYPE_SIGN_FILE = ""
) (
    input  wire        clk,
    input  wire        rst,
    input  wire        bus_wr_en,
    input  wire [19:0] bus_wr_addr,
    input  wire [31:0] bus_wr_data,
    input  wire [3:0]  bus_wr_strb,
    input  wire        bus_rd_en,
    input  wire [19:0] bus_rd_addr,
    output reg  [31:0] bus_rd_data,
    output reg         bus_rd_valid,
    output wire        trial_running,
    output wire        trial_done,
    output wire        core_busy,
    output wire        fault_seen,
    output wire        deadline_miss_seen
);
    localparam [31:0] IDENT = 32'h434e5339; // "CNS9"
    localparam [2:0] S_IDLE = 3'd0;
    localparam [2:0] S_CLEAR = 3'd1;
    localparam [2:0] S_LOAD = 3'd2;
    localparam [2:0] S_START = 3'd3;
    localparam [2:0] S_RUN = 3'd4;
    localparam [2:0] S_WAIT = 3'd5;
    localparam [2:0] S_DONE = 3'd6;

    reg [2:0] run_state = S_IDLE;
    reg [31:0] step_length = 32'd8;
    reg [31:0] period_cycles = 32'd200000;
    reg capture_events = 1'b1;
    reg start_request = 1'b0;
    reg clear_state = 1'b0;
    reg start_timestep = 1'b0;
    reg signed [33:0] input_current = 34'sd0;
    reg [31:0] step_index = 32'd0;
    reg [31:0] completed_steps = 32'd0;
    reg [31:0] period_count = 32'd0;
    reg [31:0] latency_count = 32'd0;
    reg [31:0] max_latency = 32'd0;
    reg [31:0] missed_steps = 32'd0;
    reg deadline_this_step = 1'b0;
    reg deadline_sticky = 1'b0;
    reg event_overflow = 1'b0;
    reg fault_sticky = 1'b0;
    reg [31:0] event_count = 32'd0;
    reg [31:0] event_start = 32'd0;
    reg [31:0] step_synops = 32'd0;
    reg [63:0] total_synops = 64'd0;
    reg [15:0] total_spikes = 16'd0;
    reg [15:0] apn1_spikes = 16'd0;
    reg [15:0] vpn1_spikes = 16'd0;
    reg [15:0] pc1_spikes = 16'd0;
    reg [15:0] pip10_spikes = 16'd0;
    reg [15:0] pmp2_spikes = 16'd0;
    reg state_sat_step = 1'b0;
    reg acc_sat_step = 1'b0;

    (* ram_style = "block" *) reg [31:0] stimulus_low [0:MAX_STEPS-1];
    (* ram_style = "block" *) reg [1:0] stimulus_high [0:MAX_STEPS-1];
    (* ram_style = "block" *) reg [255:0] summary_mem [0:MAX_STEPS-1];
    (* ram_style = "block" *) reg [15:0] event_mem [0:MAX_EVENTS-1];
    reg [31:0] stim_low_read;
    reg [1:0] stim_high_read;
    reg [255:0] summary_read;
    reg [15:0] event_read;
    reg [2:0] read_word;
    reg [1:0] read_pending_kind = 2'd0;
    wire core_done;
    wire [15:0] captured_this_step = event_count[15:0] - event_start[15:0];
    wire bus_stim_read = bus_rd_en && bus_rd_addr >= 20'h10000 &&
                         bus_rd_addr < 20'h20000 && !trial_running;
    wire run_stim_read = (run_state == S_LOAD) ||
                         ((run_state == S_RUN) && core_done &&
                          (step_index + 1 < step_length));
    wire [12:0] stim_read_addr = run_stim_read ?
        ((run_state == S_LOAD) ? step_index[12:0] : step_index[12:0] + 1'b1) :
        bus_rd_addr[15:3];

    wire spike_valid;
    wire [12:0] spike_neuron;
    wire spike_is_pc1;
    wire [4:0] spike_group_flags;
    wire clear_done;
    wire synapse_op_valid;
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
        .NEURON_PARAM_FILE(NEURON_PARAM_FILE),
        .SYNAPSE_FILE(SYNAPSE_FILE),
        .OFFSET_FILE(OFFSET_FILE),
        .TYPE_SIGN_FILE(TYPE_SIGN_FILE)
    ) core (
        .clk(clk),
        .rst(rst),
        .clear_state(clear_state),
        .start_timestep(start_timestep),
        .input_current(input_current),
        .busy(core_busy),
        .timestep_done(core_done),
        .spike_valid(spike_valid),
        .spike_neuron(spike_neuron),
        .spike_is_pC1(spike_is_pc1),
        .spike_group_flags(spike_group_flags),
        .clear_done(clear_done),
        .synapse_op_valid(synapse_op_valid),
        .state_saturation_seen(state_saturation_seen),
        .accumulator_saturation_seen(accumulator_saturation_seen)
    );

    assign trial_running = (run_state != S_IDLE) && (run_state != S_DONE);
    assign trial_done = (run_state == S_DONE);
    assign fault_seen = fault_sticky || event_overflow;
    assign deadline_miss_seen = deadline_sticky;

    // One BRAM read port is shared by host readback before a trial and by
    // sequential prefetch during a trial. The other port performs host writes.
    always @(posedge clk) begin
        if (run_stim_read || bus_stim_read) begin
            stim_low_read <= stimulus_low[stim_read_addr];
            stim_high_read <= stimulus_high[stim_read_addr];
        end
    end

    // The host writes whole 32-bit words. Stimulus writes are blocked during
    // execution, so the core never sees a partly updated trial.
    always @(posedge clk) begin
        start_request <= 1'b0;
        if (rst) begin
            step_length <= 32'd8;
            period_cycles <= 32'd200000;
            capture_events <= 1'b1;
        end else if (bus_wr_en && bus_wr_strb == 4'hf && !trial_running) begin
            if (bus_wr_addr == 20'h00004)
                start_request <= bus_wr_data[0];
            else if (bus_wr_addr == 20'h0000c)
                step_length <= bus_wr_data;
            else if (bus_wr_addr == 20'h00010)
                period_cycles <= bus_wr_data;
            else if (bus_wr_addr == 20'h0002c)
                capture_events <= bus_wr_data[0];
            else if (bus_wr_addr >= 20'h10000 && bus_wr_addr < 20'h20000) begin
                if (bus_wr_addr[2])
                    stimulus_high[bus_wr_addr[15:3]] <= bus_wr_data[1:0];
                else
                    stimulus_low[bus_wr_addr[15:3]] <= bus_wr_data;
            end
        end
    end

    // Synchronous BRAM reads have a two-cycle bus response. The AXI bridge
    // waits for bus_rd_valid; it never assumes a combinational RAM output.
    always @(posedge clk) begin
        bus_rd_valid <= 1'b0;
        if (rst) begin
            read_pending_kind <= 2'd0;
            bus_rd_data <= 32'd0;
        end else if (read_pending_kind != 2'd0) begin
            case (read_pending_kind)
                2'd1: bus_rd_data <= summary_read[read_word*32 +: 32];
                2'd2: bus_rd_data <= {16'd0, event_read};
                2'd3: bus_rd_data <= read_word[0] ? {30'd0, stim_high_read} : stim_low_read;
                default: bus_rd_data <= 32'd0;
            endcase
            bus_rd_valid <= 1'b1;
            read_pending_kind <= 2'd0;
        end else if (bus_rd_en) begin
            if (bus_rd_addr >= 20'h60000 && bus_rd_addr < 20'ha0000) begin
                event_read <= event_mem[(bus_rd_addr - 20'h60000) >> 2];
                read_pending_kind <= 2'd2;
            end else if (bus_rd_addr >= 20'h20000 && bus_rd_addr < 20'h60000) begin
                summary_read <= summary_mem[(bus_rd_addr - 20'h20000) >> 5];
                read_word <= bus_rd_addr[4:2];
                read_pending_kind <= 2'd1;
            end else if (bus_rd_addr >= 20'h10000 && bus_rd_addr < 20'h20000) begin
                read_word <= {2'd0, bus_rd_addr[2]};
                read_pending_kind <= 2'd3;
            end else begin
                case (bus_rd_addr)
                    20'h00000: bus_rd_data <= IDENT;
                    20'h00008: bus_rd_data <= {26'd0, (run_state == S_CLEAR),
                        fault_seen, event_overflow, deadline_sticky, trial_done, trial_running};
                    20'h0000c: bus_rd_data <= step_length;
                    20'h00010: bus_rd_data <= period_cycles;
                    20'h00014: bus_rd_data <= completed_steps;
                    20'h00018: bus_rd_data <= event_count;
                    20'h0001c: bus_rd_data <= missed_steps;
                    20'h00020: bus_rd_data <= max_latency;
                    20'h00024: bus_rd_data <= total_synops[31:0];
                    20'h00028: bus_rd_data <= total_synops[63:32];
                    20'h0002c: bus_rd_data <= {31'd0, capture_events};
                    default: bus_rd_data <= 32'd0;
                endcase
                bus_rd_valid <= 1'b1;
            end
        end
    end

    always @(posedge clk) begin
        clear_state <= 1'b0;
        start_timestep <= 1'b0;
        if (rst) begin
            run_state <= S_IDLE;
            step_index <= 32'd0;
            completed_steps <= 32'd0;
            period_count <= 32'd0;
            latency_count <= 32'd0;
            max_latency <= 32'd0;
            missed_steps <= 32'd0;
            deadline_this_step <= 1'b0;
            deadline_sticky <= 1'b0;
            event_overflow <= 1'b0;
            fault_sticky <= 1'b0;
            event_count <= 32'd0;
            event_start <= 32'd0;
            step_synops <= 32'd0;
            total_synops <= 64'd0;
            total_spikes <= 16'd0;
            apn1_spikes <= 16'd0;
            vpn1_spikes <= 16'd0;
            pc1_spikes <= 16'd0;
            pip10_spikes <= 16'd0;
            pmp2_spikes <= 16'd0;
            state_sat_step <= 1'b0;
            acc_sat_step <= 1'b0;
            input_current <= 34'sd0;
        end else begin
            case (run_state)
                S_IDLE, S_DONE: begin
                    if (start_request && step_length != 0 && step_length <= MAX_STEPS &&
                        period_cycles >= 32'd2) begin
                        step_index <= 32'd0;
                        completed_steps <= 32'd0;
                        max_latency <= 32'd0;
                        missed_steps <= 32'd0;
                        deadline_sticky <= 1'b0;
                        event_overflow <= 1'b0;
                        fault_sticky <= 1'b0;
                        event_count <= 32'd0;
                        total_synops <= 64'd0;
                        clear_state <= 1'b1;
                        run_state <= S_CLEAR;
                    end
                end
                S_CLEAR: begin
                    if (clear_done)
                        run_state <= S_LOAD;
                end
                S_LOAD: begin
                    run_state <= S_START;
                end
                S_START: begin
                    input_current <= {stim_high_read, stim_low_read};
                    start_timestep <= 1'b1;
                    period_count <= 32'd0;
                    latency_count <= 32'd0;
                    deadline_this_step <= 1'b0;
                    step_synops <= 32'd0;
                    total_spikes <= 16'd0;
                    apn1_spikes <= 16'd0;
                    vpn1_spikes <= 16'd0;
                    pc1_spikes <= 16'd0;
                    pip10_spikes <= 16'd0;
                    pmp2_spikes <= 16'd0;
                    state_sat_step <= 1'b0;
                    acc_sat_step <= 1'b0;
                    event_start <= event_count;
                    run_state <= S_RUN;
                end
                S_RUN: begin
                    period_count <= period_count + 1'b1;
                    latency_count <= latency_count + 1'b1;
                    if (spike_valid) begin
                        total_spikes <= total_spikes + 1'b1;
                        if (spike_group_flags[0]) apn1_spikes <= apn1_spikes + 1'b1;
                        if (spike_group_flags[1]) vpn1_spikes <= vpn1_spikes + 1'b1;
                        if (spike_group_flags[2]) pc1_spikes <= pc1_spikes + 1'b1;
                        if (spike_group_flags[3]) pip10_spikes <= pip10_spikes + 1'b1;
                        if (spike_group_flags[4]) pmp2_spikes <= pmp2_spikes + 1'b1;
                        if (capture_events) begin
                            if (event_count < MAX_EVENTS) begin
                                event_mem[event_count[15:0]] <= {3'b0, spike_neuron};
                                event_count <= event_count + 1'b1;
                            end else
                                event_overflow <= 1'b1;
                        end
                    end
                    if (synapse_op_valid)
                        step_synops <= step_synops + 1'b1;
                    if (state_saturation_seen) begin
                        state_sat_step <= 1'b1;
                        fault_sticky <= 1'b1;
                    end
                    if (accumulator_saturation_seen) begin
                        acc_sat_step <= 1'b1;
                        fault_sticky <= 1'b1;
                    end
                    if (period_count >= period_cycles-1 && !deadline_this_step) begin
                        deadline_this_step <= 1'b1;
                        deadline_sticky <= 1'b1;
                        missed_steps <= missed_steps + 1'b1;
                    end
                    if (core_done) begin
                        summary_mem[step_index[12:0]] <= {
                            32'd0,
                            event_start,
                            {captured_this_step,
                            12'd0, event_overflow,
                                (deadline_this_step || period_count >= period_cycles-1),
                                acc_sat_step, state_sat_step},
                            {pmp2_spikes, pip10_spikes},
                            {pc1_spikes, vpn1_spikes},
                            {apn1_spikes, total_spikes},
                            step_synops,
                            latency_count
                        };
                        completed_steps <= completed_steps + 1'b1;
                        total_synops <= total_synops + step_synops;
                        if (latency_count > max_latency) max_latency <= latency_count;
                        if (step_index + 1 >= step_length) begin
                            run_state <= S_DONE;
                        end else begin
                            step_index <= step_index + 1'b1;
                            run_state <= S_WAIT;
                        end
                    end
                end
                S_WAIT: begin
                    if (period_count >= period_cycles-2)
                        run_state <= S_START;
                    else
                        period_count <= period_count + 1'b1;
                end
                default: run_state <= S_IDLE;
            endcase
        end
    end
endmodule
