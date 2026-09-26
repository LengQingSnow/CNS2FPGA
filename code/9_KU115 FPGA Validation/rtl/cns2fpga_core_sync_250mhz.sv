`timescale 1ns/1ps

// Timing-pipelined, bit-exact implementation of the Step 8 synchronous core.
// The module name intentionally matches the reference core so the same
// verification interface can be reused while compiling this file alone.
module cns2fpga_core_sync #(
    parameter integer NEURON_COUNT = 6279,
    parameter integer SYNAPSE_COUNT = 350185,
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
    input  wire                              clear_state,
    input  wire                              start_timestep,
    input  wire signed [STATE_BITS-1:0]      input_current,
    output reg                               busy,
    output reg                               timestep_done,
    output reg                               spike_valid,
    output reg [NEURON_INDEX_BITS-1:0]       spike_neuron,
    output reg                               spike_is_pC1,
    output reg [4:0]                         spike_group_flags,
    output reg                               clear_done,
    output wire                              synapse_op_valid,
    output reg                               state_saturation_seen,
    output reg                               accumulator_saturation_seen
);
    localparam [3:0] ST_IDLE         = 4'd0;
    localparam [3:0] ST_UPDATE_READ  = 4'd1;
    localparam [3:0] ST_UPDATE_MULT  = 4'd2;
    localparam [3:0] ST_UPDATE_ROUND = 4'd3;
    localparam [3:0] ST_UPDATE_ADD   = 4'd4;
    localparam [3:0] ST_UPDATE_SAT   = 4'd5;
    localparam [3:0] ST_UPDATE_EXEC  = 4'd6;
    localparam [3:0] ST_QUEUE_READ   = 4'd7;
    localparam [3:0] ST_OFFSET_READ  = 4'd8;
    localparam [3:0] ST_OFFSET_EXEC  = 4'd9;
    localparam [3:0] ST_EDGE_READ    = 4'd10;
    localparam [3:0] ST_ACC_READ     = 4'd11;
    localparam [3:0] ST_ACC_WRITE    = 4'd12;
    localparam [3:0] ST_CLEAR        = 4'd13;
    localparam [3:0] ST_UPDATE_MULT2 = 4'd14;

    localparam signed [STATE_BITS+DECAY_BITS:0] STATE_ONE_EXT =
        {{(STATE_BITS+DECAY_BITS){1'b0}}, 1'b1};
    localparam signed [STATE_BITS+DECAY_BITS:0] STATE_MAX_EXT =
        (STATE_ONE_EXT <<< (STATE_BITS-1)) - 1;
    localparam signed [STATE_BITS+DECAY_BITS:0] STATE_MIN_EXT =
        -(STATE_ONE_EXT <<< (STATE_BITS-1));
    localparam signed [ACC_BITS:0] ACC_ONE_EXT = {{ACC_BITS{1'b0}}, 1'b1};
    localparam signed [ACC_BITS:0] ACC_MAX_EXT = (ACC_ONE_EXT <<< (ACC_BITS-1)) - 1;
    localparam signed [ACC_BITS:0] ACC_MIN_EXT = -(ACC_ONE_EXT <<< (ACC_BITS-1));

    reg [3:0] state;
    assign synapse_op_valid = (state == ST_ACC_WRITE) && !rst;
    (* rom_style = "block" *) reg [NEURON_PARAM_BITS-1:0] neuron_param_mem [0:NEURON_COUNT-1];
    (* rom_style = "block" *) reg [63:0] synapse_mem [0:SYNAPSE_COUNT-1];
    (* rom_style = "block" *) reg [31:0] offset_mem [0:NEURON_COUNT-1];
    (* rom_style = "block" *) reg [15:0] type_sign_mem [0:NEURON_COUNT-1];
    (* ram_style = "block" *) reg signed [STATE_BITS-1:0] voltage_mem [0:NEURON_COUNT-1];
    (* ram_style = "block" *) reg signed [ACC_BITS-1:0] syn_current_mem [0:NEURON_COUNT-1];
    (* ram_style = "block" *) reg [7:0] refractory_mem [0:NEURON_COUNT-1];
    (* ram_style = "block" *) reg [NEURON_INDEX_BITS-1:0] spike_queue [0:NEURON_COUNT-1];

    integer init_index;
    integer update_index;
    reg [NEURON_INDEX_BITS-1:0] clear_index;
    integer spike_count;
    integer spike_read_index;
    integer active_pre;
    integer edge_cursor;
    integer edge_remaining;

    reg signed [STATE_BITS-1:0] latched_input_current;
    reg [NEURON_PARAM_BITS-1:0] param_read;
    reg [15:0] type_read;
    reg signed [STATE_BITS-1:0] voltage_read;
    reg signed [ACC_BITS-1:0] syn_current_read;
    reg [7:0] refractory_read;
    reg [31:0] offset_read;
    reg [63:0] synapse_read;
    reg [NEURON_INDEX_BITS-1:0] edge_post_read;
    reg signed [WEIGHT_BITS-1:0] edge_weight_read;
    reg signed [ACC_BITS-1:0] accumulator_read;

    reg signed [34:0] product_ll_reg;
    reg signed [33:0] product_lh_reg;
    reg signed [33:0] product_hl_reg;
    reg signed [32:0] product_hh_reg;
    reg signed [49:0] product_low_pair_reg;
    reg signed [49:0] product_high_pair_reg;
    reg signed [35:0] syn_input_sum_reg;
    reg signed [STATE_BITS+DECAY_BITS:0] decay_rounded_reg;
    reg signed [STATE_BITS+DECAY_BITS:0] update_sum_reg;
    reg signed [STATE_BITS-1:0] update_saturated_reg;
    reg update_overflow_reg;
    reg update_will_spike_reg;

    wire signed [STATE_BITS-1:0] read_threshold = param_read[0 +: STATE_BITS];
    wire signed [STATE_BITS-1:0] read_reset = param_read[STATE_BITS +: STATE_BITS];
    wire signed [DECAY_BITS-1:0] read_decay = param_read[2*STATE_BITS +: DECAY_BITS];
    wire [7:0] read_refractory_steps = param_read[2*STATE_BITS+DECAY_BITS +: 8];
    // Four one-DSP products avoid a two-DSP combinational cascade. The
    // partial products are combined in the following two existing/added
    // pipeline states without changing the exact signed 34 x 32 result.
    wire signed [34:0] product_ll =
        $signed({1'b0, voltage_read[16:0]}) *
        $signed({1'b0, read_decay[15:0]});
    wire signed [33:0] product_lh =
        $signed({1'b0, voltage_read[16:0]}) *
        $signed(read_decay[31:16]);
    wire signed [33:0] product_hl =
        $signed(voltage_read[33:17]) *
        $signed({1'b0, read_decay[15:0]});
    wire signed [32:0] product_hh =
        $signed(voltage_read[33:17]) *
        $signed(read_decay[31:16]);
    wire signed [49:0] product_low_pair =
        $signed({{15{product_ll_reg[34]}}, product_ll_reg}) +
        ($signed({{16{product_lh_reg[33]}}, product_lh_reg}) <<< 16);
    wire signed [49:0] product_high_pair =
        $signed({{16{product_hl_reg[33]}}, product_hl_reg}) +
        ($signed({{17{product_hh_reg[32]}}, product_hh_reg}) <<< 16);
    wire signed [STATE_BITS+DECAY_BITS-1:0] decay_product =
        $signed({{16{product_low_pair_reg[49]}}, product_low_pair_reg}) +
        ($signed({{16{product_high_pair_reg[49]}}, product_high_pair_reg}) <<< 17);

    reg signed [STATE_BITS+DECAY_BITS:0] decay_rounded;
    reg signed [STATE_BITS+DECAY_BITS:0] update_sum;
    reg signed [STATE_BITS-1:0] update_saturated;
    reg update_overflow;
    reg update_will_spike;
    reg signed [ACC_BITS:0] accumulator_sum;
    reg signed [ACC_BITS-1:0] accumulator_saturated;
    reg accumulator_overflow;

    function automatic signed [STATE_BITS+DECAY_BITS:0] round_decay;
        input signed [STATE_BITS+DECAY_BITS-1:0] value;
        reg signed [STATE_BITS+DECAY_BITS:0] wide;
        reg signed [STATE_BITS+DECAY_BITS:0] magnitude;
        reg signed [STATE_BITS+DECAY_BITS:0] half;
        begin
            wide = value;
            half = STATE_ONE_EXT <<< (DECAY_FRAC-1);
            if (wide >= 0)
                round_decay = (wide + half) >>> DECAY_FRAC;
            else begin
                magnitude = -wide;
                round_decay = -((magnitude + half) >>> DECAY_FRAC);
            end
        end
    endfunction

    always @* begin
        decay_rounded = round_decay(decay_product);
        update_sum = decay_rounded_reg + $signed(syn_input_sum_reg);
        update_overflow = 1'b0;
        if (update_sum_reg > STATE_MAX_EXT) begin
            update_saturated = {1'b0, {(STATE_BITS-1){1'b1}}};
            update_overflow = 1'b1;
        end else if (update_sum_reg < STATE_MIN_EXT) begin
            update_saturated = {1'b1, {(STATE_BITS-1){1'b0}}};
            update_overflow = 1'b1;
        end else begin
            update_saturated = update_sum_reg[STATE_BITS-1:0];
        end
        update_will_spike = (refractory_read == 0) &&
                            ($signed(update_saturated) >= $signed(read_threshold));

        accumulator_sum = $signed(accumulator_read) + $signed(edge_weight_read);
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
        if (STATE_FRAC != WEIGHT_FRAC) $error("This core requires equal state/weight fractional scale");
        if (STATE_BITS != 34 || DECAY_BITS != 32 || ACC_BITS != 35)
            $error("The split-product pipeline requires STATE_BITS=34, DECAY_BITS=32, ACC_BITS=35");
        if (NEURON_PARAM_FILE != "") $readmemh(NEURON_PARAM_FILE, neuron_param_mem);
        if (SYNAPSE_FILE != "")      $readmemh(SYNAPSE_FILE, synapse_mem);
        if (OFFSET_FILE != "")       $readmemh(OFFSET_FILE, offset_mem);
        if (TYPE_SIGN_FILE != "")    $readmemh(TYPE_SIGN_FILE, type_sign_mem);
        for (init_index = 0; init_index < NEURON_COUNT; init_index = init_index + 1) begin
            voltage_mem[init_index] = {STATE_BITS{1'b0}};
            syn_current_mem[init_index] = {ACC_BITS{1'b0}};
            refractory_mem[init_index] = 8'd0;
        end
    end

    always @(posedge clk) begin
        if (rst) begin
            state <= ST_IDLE;
            busy <= 1'b0;
            timestep_done <= 1'b0;
            spike_valid <= 1'b0;
            spike_neuron <= 0;
            spike_is_pC1 <= 1'b0;
            spike_group_flags <= 5'b0;
            clear_done <= 1'b0;
            clear_index <= 0;
            state_saturation_seen <= 1'b0;
            accumulator_saturation_seen <= 1'b0;
            update_index <= 0;
            spike_count <= 0;
            spike_read_index <= 0;
            active_pre <= 0;
            edge_cursor <= 0;
            edge_remaining <= 0;
            latched_input_current <= 0;
            product_ll_reg <= 0;
            product_lh_reg <= 0;
            product_hl_reg <= 0;
            product_hh_reg <= 0;
            product_low_pair_reg <= 0;
            product_high_pair_reg <= 0;
            syn_input_sum_reg <= 0;
            decay_rounded_reg <= 0;
            update_sum_reg <= 0;
            update_saturated_reg <= 0;
            update_overflow_reg <= 1'b0;
            update_will_spike_reg <= 1'b0;
        end else begin
            timestep_done <= 1'b0;
            spike_valid <= 1'b0;
            clear_done <= 1'b0;
            case (state)
                ST_IDLE: begin
                    busy <= 1'b0;
                    if (clear_state) begin
                        clear_index <= 0;
                        busy <= 1'b1;
                        state <= ST_CLEAR;
                    end else if (start_timestep) begin
                        busy <= 1'b1;
                        latched_input_current <= input_current;
                        update_index <= 0;
                        spike_count <= 0;
                        state_saturation_seen <= 1'b0;
                        accumulator_saturation_seen <= 1'b0;
                        state <= ST_UPDATE_READ;
                    end
                end

                ST_UPDATE_READ: begin
                    param_read <= neuron_param_mem[update_index];
                    type_read <= type_sign_mem[update_index];
                    voltage_read <= voltage_mem[update_index];
                    syn_current_read <= syn_current_mem[update_index];
                    refractory_read <= refractory_mem[update_index];
                    state <= ST_UPDATE_MULT;
                end

                ST_UPDATE_MULT: begin
                    product_ll_reg <= product_ll;
                    product_lh_reg <= product_lh;
                    product_hl_reg <= product_hl;
                    product_hh_reg <= product_hh;
                    state <= ST_UPDATE_MULT2;
                end

                ST_UPDATE_MULT2: begin
                    product_low_pair_reg <= product_low_pair;
                    product_high_pair_reg <= product_high_pair;
                    syn_input_sum_reg <= $signed({syn_current_read[ACC_BITS-1], syn_current_read}) +
                        (type_read[2] ? $signed({{2{latched_input_current[STATE_BITS-1]}}, latched_input_current}) : 36'sd0);
                    state <= ST_UPDATE_ROUND;
                end

                ST_UPDATE_ROUND: begin
                    decay_rounded_reg <= decay_rounded;
                    state <= ST_UPDATE_ADD;
                end

                ST_UPDATE_ADD: begin
                    update_sum_reg <= update_sum;
                    state <= ST_UPDATE_SAT;
                end

                ST_UPDATE_SAT: begin
                    update_saturated_reg <= update_saturated;
                    update_overflow_reg <= update_overflow;
                    update_will_spike_reg <= update_will_spike;
                    state <= ST_UPDATE_EXEC;
                end

                ST_UPDATE_EXEC: begin
                    syn_current_mem[update_index] <= 0;
                    if (refractory_read != 0) begin
                        voltage_mem[update_index] <= read_reset;
                        refractory_mem[update_index] <= refractory_read - 1'b1;
                    end else if (update_will_spike_reg) begin
                        voltage_mem[update_index] <= read_reset;
                        refractory_mem[update_index] <= read_refractory_steps;
                        spike_queue[spike_count] <= update_index[NEURON_INDEX_BITS-1:0];
                        spike_count <= spike_count + 1;
                        spike_valid <= 1'b1;
                        spike_neuron <= update_index[NEURON_INDEX_BITS-1:0];
                        spike_is_pC1 <= type_read[7];
                        spike_group_flags <= type_read[9:5];
                    end else begin
                        voltage_mem[update_index] <= update_saturated_reg;
                    end
                    if (update_overflow_reg) state_saturation_seen <= 1'b1;
                    if (update_index == NEURON_COUNT-1) begin
                        if ((spike_count == 0) && !update_will_spike_reg) begin
                            busy <= 1'b0;
                            timestep_done <= 1'b1;
                            state <= ST_IDLE;
                        end else begin
                            spike_read_index <= 0;
                            state <= ST_QUEUE_READ;
                        end
                    end else begin
                        update_index <= update_index + 1;
                        state <= ST_UPDATE_READ;
                    end
                end

                ST_QUEUE_READ: begin
                    active_pre <= spike_queue[spike_read_index];
                    state <= ST_OFFSET_READ;
                end

                ST_OFFSET_READ: begin
                    offset_read <= offset_mem[active_pre];
                    state <= ST_OFFSET_EXEC;
                end

                ST_OFFSET_EXEC: begin
                    edge_cursor <= offset_read[18:0];
                    edge_remaining <= offset_read[28:19];
                    if (offset_read[28:19] == 0) begin
                        if (spike_read_index + 1 >= spike_count) begin
                            busy <= 1'b0;
                            timestep_done <= 1'b1;
                            state <= ST_IDLE;
                        end else begin
                            spike_read_index <= spike_read_index + 1;
                            state <= ST_QUEUE_READ;
                        end
                    end else begin
                        state <= ST_EDGE_READ;
                    end
                end

                ST_EDGE_READ: begin
                    synapse_read <= synapse_mem[edge_cursor];
                    state <= ST_ACC_READ;
                end

                ST_ACC_READ: begin
                    edge_post_read <= synapse_read[0 +: NEURON_INDEX_BITS];
                    edge_weight_read <= synapse_read[NEURON_INDEX_BITS +: WEIGHT_BITS];
                    accumulator_read <= syn_current_mem[synapse_read[0 +: NEURON_INDEX_BITS]];
                    state <= ST_ACC_WRITE;
                end

                ST_ACC_WRITE: begin
                    syn_current_mem[edge_post_read] <= accumulator_saturated;
                    if (accumulator_overflow) accumulator_saturation_seen <= 1'b1;
                    if (edge_remaining == 1) begin
                        if (spike_read_index + 1 >= spike_count) begin
                            busy <= 1'b0;
                            timestep_done <= 1'b1;
                            state <= ST_IDLE;
                        end else begin
                            spike_read_index <= spike_read_index + 1;
                            state <= ST_QUEUE_READ;
                        end
                    end else begin
                        edge_cursor <= edge_cursor + 1;
                        edge_remaining <= edge_remaining - 1;
                        state <= ST_EDGE_READ;
                    end
                end

                ST_CLEAR: begin
                    voltage_mem[clear_index] <= 0;
                    syn_current_mem[clear_index] <= 0;
                    refractory_mem[clear_index] <= 0;
                    if (clear_index == NEURON_COUNT-1) begin
                        busy <= 1'b0;
                        clear_done <= 1'b1;
                        state <= ST_IDLE;
                    end else begin
                        clear_index <= clear_index + 1'b1;
                    end
                end

                default: state <= ST_IDLE;
            endcase
        end
    end
endmodule
