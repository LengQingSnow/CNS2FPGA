`timescale 1ns/1ps

// Runtime-reconfigurable trial engine. The bitstream reserves maximum graph
// capacity; the host loads a validated image before any trial may start.
module cns2fpga_trial_engine #(
    parameter integer MAX_STEPS = 8192,
    parameter integer MAX_EVENTS = 65536,
    parameter integer MAX_NEURONS = 6279,
    parameter integer MAX_SYNAPSES = 350185
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
    localparam [31:0] IDENT = 32'h434e5352; // "CNSR"
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
    (* ram_style = "block", cascade_height = 1 *) reg [15:0] event_mem [0:MAX_EVENTS-1];
    reg [31:0] stim_low_read;
    reg [1:0] stim_high_read;
    reg [255:0] summary_read;
    reg [15:0] event_read;
    reg [15:0] event_read_stage;
    reg [2:0] read_word;
    reg [2:0] read_pending_kind = 3'd0;
    reg image_ready = 1'b0;
    reg load_active = 1'b0;
    reg image_error = 1'b0;
    reg [3:0] image_error_code = 4'd0;
    reg [12:0] staging_neurons = 13'd0;
    reg [18:0] staging_synapses = 19'd0;
    reg [12:0] active_neurons = 13'd0;
    reg [18:0] active_synapses = 19'd0;
    reg [1:0] load_region = 2'd0;
    reg [19:0] param_words = 20'd0;
    reg [19:0] syn_words = 20'd0;
    reg [19:0] offset_words = 20'd0;
    reg [19:0] type_words = 20'd0;
    reg [31:0] image_checksum = 32'd0;
    reg [31:0] expected_checksum = 32'd0;
    reg expected_set = 1'b0;
    reg [31:0] image_epoch = 32'd0;
    reg image_wr_en = 1'b0;
    reg [1:0] image_wr_kind = 2'd0;
    (* max_fanout = 32 *) reg [18:0] image_wr_index = 19'd0;
    reg [1:0] image_wr_lane = 2'd0;
    // This drives thousands of distributed parameter-RAM write inputs.
    // Replication keeps one host-write bit from spanning the whole device.
    (* max_fanout = 32 *) reg [31:0] image_wr_data = 32'd0;
    wire [19:0] param_limit = {5'd0, staging_neurons, 2'd0};
    wire [19:0] syn_limit = {staging_synapses, 1'b0};
    wire core_done;
    wire [15:0] captured_this_step = event_count[15:0] - event_start[15:0];
    // During a trial, hold the current timestep's stimulus address across
    // S_WAIT and prefetch the next address at the completing S_RUN edge.
    wire [12:0] stim_read_addr = trial_running ?
        (((run_state == S_RUN) && core_done) ?
            step_index[12:0] + 1'b1 : step_index[12:0]) :
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
        .NEURON_COUNT(MAX_NEURONS),
        .SYNAPSE_COUNT(MAX_SYNAPSES),
        .NEURON_INDEX_BITS(13),
        .STATE_BITS(34),
        .STATE_FRAC(24),
        .WEIGHT_BITS(30),
        .WEIGHT_FRAC(24),
        .DECAY_BITS(32),
        .DECAY_FRAC(30),
        .ACC_BITS(35),
        .NEURON_PARAM_BITS(128)
    ) core (
        .clk(clk),
        .rst(rst),
        .clear_state(clear_state),
        .start_timestep(start_timestep),
        .input_current(input_current),
        .active_neuron_count(active_neurons),
        .image_wr_en(image_wr_en),
        .image_wr_kind(image_wr_kind),
        .image_wr_index(image_wr_index),
        .image_wr_lane(image_wr_lane),
        .image_wr_data(image_wr_data),
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
    assign fault_seen = fault_sticky || event_overflow || image_error;
    assign deadline_miss_seen = deadline_sticky;

    // One BRAM read port is shared by host readback and trial prefetch. Keep
    // it enabled to avoid a step-index-to-BRAM-enable timing path. The AXI
    // bridge holds its address until the pending read completes.
    always @(posedge clk) begin
        stim_low_read <= stimulus_low[stim_read_addr];
        stim_high_read <= stimulus_high[stim_read_addr];
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

    // Graph image protocol: BEGIN(1), stream four regions, EXPECTED_CHECKSUM,
    // COMMIT(2). No graph is executable until all four exact word counts and
    // the rolling checksum agree. BEGIN invalidates the old image immediately.
    always @(posedge clk) begin
        image_wr_en <= 1'b0;
        if (rst) begin
            image_ready <= 1'b0;
            load_active <= 1'b0;
            image_error <= 1'b0;
            image_error_code <= 4'd0;
            staging_neurons <= 13'd0;
            staging_synapses <= 19'd0;
            active_neurons <= 13'd0;
            active_synapses <= 19'd0;
            load_region <= 2'd0;
            param_words <= 20'd0;
            syn_words <= 20'd0;
            offset_words <= 20'd0;
            type_words <= 20'd0;
            image_checksum <= 32'd0;
            expected_checksum <= 32'd0;
            expected_set <= 1'b0;
            image_epoch <= 32'd0;
        end else if (bus_wr_en && bus_wr_strb == 4'hf && !trial_running && !core_busy) begin
            case (bus_wr_addr)
                20'h00030: begin
                    case (bus_wr_data)
                        32'd1: begin
                            image_ready <= 1'b0;
                            load_active <= 1'b1;
                            image_error <= 1'b0;
                            image_error_code <= 4'd0;
                            staging_neurons <= 13'd0;
                            staging_synapses <= 19'd0;
                            active_neurons <= 13'd0;
                            active_synapses <= 19'd0;
                            load_region <= 2'd0;
                            param_words <= 20'd0;
                            syn_words <= 20'd0;
                            offset_words <= 20'd0;
                            type_words <= 20'd0;
                            image_checksum <= 32'd0;
                            expected_checksum <= 32'd0;
                            expected_set <= 1'b0;
                        end
                        32'd2: begin
                            if (load_active && !image_error &&
                                staging_neurons != 0 && staging_neurons <= MAX_NEURONS &&
                                staging_synapses <= MAX_SYNAPSES &&
                                param_words == param_limit && syn_words == syn_limit &&
                                offset_words == staging_neurons &&
                                type_words == staging_neurons &&
                                expected_set && image_checksum == expected_checksum) begin
                                active_neurons <= staging_neurons;
                                active_synapses <= staging_synapses;
                                image_ready <= 1'b1;
                                load_active <= 1'b0;
                                image_epoch <= image_epoch + 1'b1;
                            end else begin
                                image_ready <= 1'b0;
                                image_error <= 1'b1;
                                image_error_code <= 4'd1;
                            end
                        end
                        32'd3: begin
                            load_active <= 1'b0;
                            image_ready <= 1'b0;
                            active_neurons <= 13'd0;
                            active_synapses <= 19'd0;
                        end
                        default: begin
                            image_error <= 1'b1;
                            image_error_code <= 4'd2;
                        end
                    endcase
                end
                20'h00034: if (load_active && param_words == 0 && syn_words == 0 &&
                               offset_words == 0 && type_words == 0 &&
                               bus_wr_data != 0 && bus_wr_data <= MAX_NEURONS) begin
                    staging_neurons <= bus_wr_data[12:0];
                end else begin
                    image_error <= 1'b1;
                    image_error_code <= 4'd3;
                end
                20'h00038: if (load_active && param_words == 0 && syn_words == 0 &&
                               offset_words == 0 && type_words == 0 &&
                               bus_wr_data <= MAX_SYNAPSES) begin
                    staging_synapses <= bus_wr_data[18:0];
                end else begin
                    image_error <= 1'b1;
                    image_error_code <= 4'd3;
                end
                20'h0003c: if (load_active && bus_wr_data < 4) begin
                    load_region <= bus_wr_data[1:0];
                end else begin
                    image_error <= 1'b1;
                    image_error_code <= 4'd4;
                end
                20'h00040: begin
                    if (!load_active || image_error) begin
                        image_error <= 1'b1;
                        image_error_code <= 4'd5;
                    end else begin
                        case (load_region)
                            2'd0: if (param_words < param_limit) begin
                                image_wr_en <= 1'b1;
                                image_wr_kind <= 2'd0;
                                image_wr_index <= param_words >> 2;
                                image_wr_lane <= param_words[1:0];
                                image_wr_data <= bus_wr_data;
                                param_words <= param_words + 1'b1;
                                image_checksum <= {image_checksum[30:0],image_checksum[31]} ^ bus_wr_data;
                            end else begin
                                image_error <= 1'b1;
                                image_error_code <= 4'd6;
                            end
                            // The low lane carries post_index. Reject an
                            // out-of-image target before it reaches graph RAM.
                            2'd1: if (syn_words < syn_limit &&
                                      (syn_words[0] || bus_wr_data[12:0] < staging_neurons)) begin
                                image_wr_en <= 1'b1;
                                image_wr_kind <= 2'd1;
                                image_wr_index <= syn_words >> 1;
                                image_wr_lane <= {1'b0,syn_words[0]};
                                image_wr_data <= bus_wr_data;
                                syn_words <= syn_words + 1'b1;
                                image_checksum <= {image_checksum[30:0],image_checksum[31]} ^ bus_wr_data ^ 32'd1;
                            end else begin
                                image_error <= 1'b1;
                                image_error_code <= 4'd6;
                            end
                            2'd2: if (offset_words < staging_neurons &&
                                      bus_wr_data[31:29] == 0 &&
                                      ({1'b0,bus_wr_data[18:0]} + {10'd0,bus_wr_data[28:19]}) <=
                                      {1'b0,staging_synapses}) begin
                                image_wr_en <= 1'b1;
                                image_wr_kind <= 2'd2;
                                image_wr_index <= offset_words[18:0];
                                image_wr_lane <= 2'd0;
                                image_wr_data <= bus_wr_data;
                                offset_words <= offset_words + 1'b1;
                                image_checksum <= {image_checksum[30:0],image_checksum[31]} ^ bus_wr_data ^ 32'd2;
                            end else begin
                                image_error <= 1'b1;
                                image_error_code <= 4'd6;
                            end
                            2'd3: if (type_words < staging_neurons && bus_wr_data[31:16] == 0) begin
                                image_wr_en <= 1'b1;
                                image_wr_kind <= 2'd3;
                                image_wr_index <= type_words[18:0];
                                image_wr_lane <= 2'd0;
                                image_wr_data <= bus_wr_data;
                                type_words <= type_words + 1'b1;
                                image_checksum <= {image_checksum[30:0],image_checksum[31]} ^ bus_wr_data ^ 32'd3;
                            end else begin
                                image_error <= 1'b1;
                                image_error_code <= 4'd6;
                            end
                        endcase
                    end
                end
                20'h00044: if (load_active) begin
                    expected_checksum <= bus_wr_data;
                    expected_set <= 1'b1;
                end else begin
                    image_error <= 1'b1;
                    image_error_code <= 4'd5;
                end
            endcase
        end
    end

    // The event RAM has a deeper read mux than the other memories. Its extra
    // stage isolates BRAM output timing from the bus data-selection mux.
    // The AXI bridge waits for bus_rd_valid, so this only adds one host-read
    // cycle and does not affect trial computation latency.
    always @(posedge clk) begin
        bus_rd_valid <= 1'b0;
        if (rst) begin
            read_pending_kind <= 3'd0;
            bus_rd_data <= 32'd0;
        end else if (read_pending_kind != 3'd0) begin
            case (read_pending_kind)
                3'd1: bus_rd_data <= summary_read[read_word*32 +: 32];
                3'd2: begin
                    event_read_stage <= event_read;
                    read_pending_kind <= 3'd4;
                end
                3'd4: bus_rd_data <= {16'd0, event_read_stage};
                3'd3: bus_rd_data <= read_word[0] ? {30'd0, stim_high_read} : stim_low_read;
                default: bus_rd_data <= 32'd0;
            endcase
            if (read_pending_kind != 3'd2) begin
                bus_rd_valid <= 1'b1;
                read_pending_kind <= 3'd0;
            end
        end else if (bus_rd_en) begin
            if (bus_rd_addr >= 20'h60000 && bus_rd_addr < 20'ha0000) begin
                event_read <= event_mem[(bus_rd_addr - 20'h60000) >> 2];
                read_pending_kind <= 3'd2;
            end else if (bus_rd_addr >= 20'h20000 && bus_rd_addr < 20'h60000) begin
                summary_read <= summary_mem[(bus_rd_addr - 20'h20000) >> 5];
                read_word <= bus_rd_addr[4:2];
                read_pending_kind <= 3'd1;
            end else if (bus_rd_addr >= 20'h10000 && bus_rd_addr < 20'h20000) begin
                read_word <= {2'd0, bus_rd_addr[2]};
                read_pending_kind <= 3'd3;
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
                    20'h00030: bus_rd_data <= {24'd0, image_error_code, 1'b0,
                        image_error, load_active, image_ready};
                    20'h00034: bus_rd_data <= {19'd0, staging_neurons};
                    20'h00038: bus_rd_data <= {13'd0, staging_synapses};
                    20'h0003c: bus_rd_data <= {30'd0, load_region};
                    20'h00044: bus_rd_data <= expected_checksum;
                    20'h00048: bus_rd_data <= image_checksum;
                    20'h0004c: bus_rd_data <= image_epoch;
                    20'h00050: bus_rd_data <= {12'd0, param_words};
                    20'h00054: bus_rd_data <= {12'd0, syn_words};
                    20'h00058: bus_rd_data <= {12'd0, offset_words};
                    20'h0005c: bus_rd_data <= {12'd0, type_words};
                    20'h00060: bus_rd_data <= {19'd0, active_neurons};
                    20'h00064: bus_rd_data <= {13'd0, active_synapses};
                    20'h00068: bus_rd_data <= MAX_NEURONS;
                    20'h0006c: bus_rd_data <= MAX_SYNAPSES;
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
                    if (start_request && image_ready && !load_active && !image_error &&
                        step_length != 0 && step_length <= MAX_STEPS &&
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
