`timescale 1ns/1ps

// Single-engine, event-driven CNS2FPGA reference architecture.
// Arithmetic order matches the step-5 integer CPU model.
module cns2fpga_core #(
    parameter integer NEURON_COUNT = 6279,
    parameter integer SYNAPSE_COUNT = 350185,
    parameter integer INPUT_COUNT = 93,
    parameter integer NEURON_INDEX_BITS = 13,
    parameter integer STATE_BITS = 34,
    parameter integer STATE_FRAC = 24,
    parameter integer WEIGHT_BITS = 30,
    parameter integer WEIGHT_FRAC = 24,
    parameter integer DECAY_BITS = 32,
    parameter integer DECAY_FRAC = 30,
    parameter integer ACC_BITS = 35,
    parameter integer NEURON_PARAM_BITS = 128,
    parameter NEURON_PARAM_FILE = "",
    parameter SYNAPSE_FILE = "",
    parameter OFFSET_FILE = "",
    parameter TYPE_SIGN_FILE = ""
) (
    input  wire                              clk,
    input  wire                              rst,
    input  wire                              start_timestep,
    input  wire signed [STATE_BITS-1:0]      input_current,
    output reg                               busy,
    output reg                               timestep_done,
    output reg                               spike_valid,
    output reg [NEURON_INDEX_BITS-1:0]       spike_neuron,
    output reg                               spike_is_pC1,
    output reg                               state_saturation_seen,
    output reg                               accumulator_saturation_seen
);

    localparam [2:0] ST_IDLE        = 3'd0;
    localparam [2:0] ST_UPDATE      = 3'd1;
    localparam [2:0] ST_LOAD_SPIKE  = 3'd2;
    localparam [2:0] ST_LOAD_OFFSET = 3'd3;
    localparam [2:0] ST_EDGE        = 3'd4;
    localparam signed [STATE_BITS+DECAY_BITS:0] STATE_ONE_EXT =
        {{(STATE_BITS+DECAY_BITS){1'b0}}, 1'b1};
    localparam signed [STATE_BITS+DECAY_BITS:0] STATE_MAX_EXT =
        (STATE_ONE_EXT <<< (STATE_BITS-1)) - 1;
    localparam signed [STATE_BITS+DECAY_BITS:0] STATE_MIN_EXT =
        -(STATE_ONE_EXT <<< (STATE_BITS-1));
    localparam signed [ACC_BITS:0] ACC_ONE_EXT = {{ACC_BITS{1'b0}}, 1'b1};
    localparam signed [ACC_BITS:0] ACC_MAX_EXT = (ACC_ONE_EXT <<< (ACC_BITS-1)) - 1;
    localparam signed [ACC_BITS:0] ACC_MIN_EXT = -(ACC_ONE_EXT <<< (ACC_BITS-1));

    reg [2:0] state;
    reg [NEURON_PARAM_BITS-1:0] neuron_param_mem [0:NEURON_COUNT-1];
    reg [63:0] synapse_mem [0:SYNAPSE_COUNT-1];
    reg [31:0] offset_mem [0:NEURON_COUNT-1];
    reg [15:0] type_sign_mem [0:NEURON_COUNT-1];

    reg signed [STATE_BITS-1:0] voltage_mem [0:NEURON_COUNT-1];
    reg signed [ACC_BITS-1:0] syn_current_mem [0:NEURON_COUNT-1];
    reg [7:0] refractory_mem [0:NEURON_COUNT-1];
    reg [NEURON_INDEX_BITS-1:0] spike_queue [0:NEURON_COUNT-1];

    integer init_index;
    integer update_index;
    integer spike_count;
    integer spike_read_index;
    integer active_pre;
    integer edge_cursor;
    integer edge_remaining;

    reg signed [STATE_BITS-1:0] latched_input_current;

    wire [NEURON_PARAM_BITS-1:0] update_param = neuron_param_mem[update_index];
    wire [15:0] update_type = type_sign_mem[update_index];
    wire signed [STATE_BITS-1:0] update_threshold = update_param[0 +: STATE_BITS];
    wire signed [STATE_BITS-1:0] update_reset = update_param[STATE_BITS +: STATE_BITS];
    wire signed [DECAY_BITS-1:0] update_decay = update_param[2*STATE_BITS +: DECAY_BITS];
    wire [7:0] update_refractory_steps = update_param[2*STATE_BITS+DECAY_BITS +: 8];

    wire signed [STATE_BITS+DECAY_BITS-1:0] decay_product =
        $signed(voltage_mem[update_index]) * $signed(update_decay);
    reg signed [STATE_BITS+DECAY_BITS:0] decay_rounded;
    reg signed [STATE_BITS+DECAY_BITS:0] update_sum;
    reg signed [STATE_BITS-1:0] update_saturated;
    reg update_overflow;
    reg update_will_spike;

    wire [63:0] active_synapse = synapse_mem[edge_cursor];
    wire [NEURON_INDEX_BITS-1:0] active_post = active_synapse[0 +: NEURON_INDEX_BITS];
    wire signed [WEIGHT_BITS-1:0] active_weight = active_synapse[NEURON_INDEX_BITS +: WEIGHT_BITS];
    reg signed [ACC_BITS:0] accumulator_sum;
    reg signed [ACC_BITS-1:0] accumulator_saturated;
    reg accumulator_overflow;

    function automatic signed [STATE_BITS+DECAY_BITS:0] round_decay;
        input signed [STATE_BITS+DECAY_BITS-1:0] value;
        reg signed [STATE_BITS+DECAY_BITS:0] wide;
        reg signed [STATE_BITS+DECAY_BITS:0] magnitude;
        begin
            wide = value;
            if (wide >= 0)
                round_decay = (wide + ({{(STATE_BITS+DECAY_BITS){1'b0}},1'b1} <<< (DECAY_FRAC-1))) >>> DECAY_FRAC;
            else begin
                magnitude = -wide;
                round_decay = -((magnitude + ({{(STATE_BITS+DECAY_BITS){1'b0}},1'b1} <<< (DECAY_FRAC-1))) >>> DECAY_FRAC);
            end
        end
    endfunction

    always @* begin
        decay_rounded = round_decay(decay_product);
        update_sum = decay_rounded + $signed(syn_current_mem[update_index]);
        if (update_type[2])
            update_sum = update_sum + $signed(latched_input_current);
        update_overflow = 1'b0;
        if (update_sum > STATE_MAX_EXT) begin
            update_saturated = {1'b0, {(STATE_BITS-1){1'b1}}};
            update_overflow = 1'b1;
        end else if (update_sum < STATE_MIN_EXT) begin
            update_saturated = {1'b1, {(STATE_BITS-1){1'b0}}};
            update_overflow = 1'b1;
        end else begin
            update_saturated = update_sum[STATE_BITS-1:0];
        end
        update_will_spike = (refractory_mem[update_index] == 0) &&
                            ($signed(update_saturated) >= $signed(update_threshold));

        accumulator_sum = $signed(syn_current_mem[active_post]) + $signed(active_weight);
        accumulator_overflow = 1'b0;
        if (accumulator_sum > ACC_MAX_EXT) begin
            accumulator_saturated = {1'b0, {(ACC_BITS-1){1'b1}}};
            accumulator_overflow = 1'b1;
        end else if (accumulator_sum < ACC_MIN_EXT) begin
            accumulator_saturated = {1'b1, {(ACC_BITS-1){1'b0}}};
            accumulator_overflow = 1'b1;
        end else begin
            accumulator_saturated = accumulator_sum[ACC_BITS-1:0];
        end
    end

    initial begin
        if (NEURON_PARAM_FILE != "") $readmemh(NEURON_PARAM_FILE, neuron_param_mem);
        if (SYNAPSE_FILE != "")      $readmemh(SYNAPSE_FILE, synapse_mem);
        if (OFFSET_FILE != "")       $readmemh(OFFSET_FILE, offset_mem);
        if (TYPE_SIGN_FILE != "")    $readmemh(TYPE_SIGN_FILE, type_sign_mem);
        for (init_index = 0; init_index < NEURON_COUNT; init_index = init_index + 1) begin
            voltage_mem[init_index] = {STATE_BITS{1'b0}};
            syn_current_mem[init_index] = {ACC_BITS{1'b0}};
            refractory_mem[init_index] = 8'd0;
            spike_queue[init_index] = {NEURON_INDEX_BITS{1'b0}};
        end
    end

    always @(posedge clk) begin
        if (rst) begin
            state <= ST_IDLE;
            busy <= 1'b0;
            timestep_done <= 1'b0;
            spike_valid <= 1'b0;
            spike_neuron <= {NEURON_INDEX_BITS{1'b0}};
            spike_is_pC1 <= 1'b0;
            state_saturation_seen <= 1'b0;
            accumulator_saturation_seen <= 1'b0;
            update_index <= 0;
            spike_count <= 0;
            spike_read_index <= 0;
            active_pre <= 0;
            edge_cursor <= 0;
            edge_remaining <= 0;
            latched_input_current <= {STATE_BITS{1'b0}};
        end else begin
            timestep_done <= 1'b0;
            spike_valid <= 1'b0;
            case (state)
                ST_IDLE: begin
                    busy <= 1'b0;
                    if (start_timestep) begin
                        busy <= 1'b1;
                        latched_input_current <= input_current;
                        update_index <= 0;
                        spike_count <= 0;
                        state_saturation_seen <= 1'b0;
                        accumulator_saturation_seen <= 1'b0;
                        state <= ST_UPDATE;
                    end
                end

                ST_UPDATE: begin
                    syn_current_mem[update_index] <= {ACC_BITS{1'b0}};
                    if (refractory_mem[update_index] != 0) begin
                        voltage_mem[update_index] <= update_reset;
                        refractory_mem[update_index] <= refractory_mem[update_index] - 1'b1;
                    end else if (update_will_spike) begin
                        voltage_mem[update_index] <= update_reset;
                        refractory_mem[update_index] <= update_refractory_steps;
                        spike_queue[spike_count] <= update_index[NEURON_INDEX_BITS-1:0];
                        spike_count <= spike_count + 1;
                        spike_valid <= 1'b1;
                        spike_neuron <= update_index[NEURON_INDEX_BITS-1:0];
                        spike_is_pC1 <= update_type[7];
                    end else begin
                        voltage_mem[update_index] <= update_saturated;
                    end
                    if (update_overflow)
                        state_saturation_seen <= 1'b1;
                    if (update_index == NEURON_COUNT-1) begin
                        if ((spike_count == 0) && !update_will_spike) begin
                            busy <= 1'b0;
                            timestep_done <= 1'b1;
                            state <= ST_IDLE;
                        end else begin
                            spike_read_index <= 0;
                            state <= ST_LOAD_SPIKE;
                        end
                    end else begin
                        update_index <= update_index + 1;
                    end
                end

                ST_LOAD_SPIKE: begin
                    active_pre <= spike_queue[spike_read_index];
                    state <= ST_LOAD_OFFSET;
                end

                ST_LOAD_OFFSET: begin
                    edge_cursor <= offset_mem[active_pre][18:0];
                    edge_remaining <= offset_mem[active_pre][28:19];
                    if (offset_mem[active_pre][28:19] == 0) begin
                        if (spike_read_index + 1 >= spike_count) begin
                            busy <= 1'b0;
                            timestep_done <= 1'b1;
                            state <= ST_IDLE;
                        end else begin
                            spike_read_index <= spike_read_index + 1;
                            state <= ST_LOAD_SPIKE;
                        end
                    end else begin
                        state <= ST_EDGE;
                    end
                end

                ST_EDGE: begin
                    syn_current_mem[active_post] <= accumulator_saturated;
                    if (accumulator_overflow)
                        accumulator_saturation_seen <= 1'b1;
                    if (edge_remaining == 1) begin
                        if (spike_read_index + 1 >= spike_count) begin
                            busy <= 1'b0;
                            timestep_done <= 1'b1;
                            state <= ST_IDLE;
                        end else begin
                            spike_read_index <= spike_read_index + 1;
                            state <= ST_LOAD_SPIKE;
                        end
                    end else begin
                        edge_cursor <= edge_cursor + 1;
                        edge_remaining <= edge_remaining - 1;
                    end
                end

                default: state <= ST_IDLE;
            endcase
        end
    end
endmodule
