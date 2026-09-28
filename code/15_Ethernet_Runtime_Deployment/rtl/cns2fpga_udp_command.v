`timescale 1ns/1ps

// Stop-and-wait UDP command endpoint. One datagram carries up to 64 graph
// words; a reply is emitted only after all writes and IMAGE_STATUS readback.
// All multibyte command fields and graph words are little-endian.
module cns2fpga_udp_command (
    input  wire        clk,
    input  wire        rst,
    input  wire        rx_hdr_valid,
    output wire        rx_hdr_ready,
    input  wire [31:0] rx_source_ip,
    input  wire [31:0] rx_dest_ip,
    input  wire [15:0] rx_source_port,
    input  wire [15:0] rx_dest_port,
    input  wire [15:0] rx_length,
    input  wire [7:0]  rx_data,
    input  wire        rx_valid,
    output wire        rx_ready,
    input  wire        rx_last,
    input  wire        rx_user,
    output wire        tx_hdr_valid,
    input  wire        tx_hdr_ready,
    output reg  [31:0] tx_dest_ip,
    output reg  [15:0] tx_dest_port,
    output wire [15:0] tx_length,
    output reg  [7:0]  tx_data,
    output wire        tx_valid,
    input  wire        tx_ready,
    output wire        tx_last,
    output reg         cmd_toggle,
    output reg         cmd_read,
    output reg  [19:0] cmd_addr,
    output reg  [31:0] cmd_data,
    input  wire        cmd_ack_toggle,
    input  wire [31:0] cmd_read_data
);
    localparam S_IDLE=0, S_RECV=1, S_VALIDATE=2, S_ISSUE=3,
               S_WAIT_WRITE=4, S_WAIT_STATUS=5, S_TX_HEADER=6, S_TX_BYTES=7,
               S_DROP=8;
    localparam OP_BEGIN=8'd1, OP_DATA=8'd2, OP_COMMIT=8'd3, OP_STATUS=8'd4;
    localparam ACK_OK=8'd0, ACK_INVALID=8'd1, ACK_SEQUENCE=8'd2,
               ACK_ENGINE=8'd3, ACK_DUPLICATE=8'd4;

    reg [3:0] state = S_IDLE;
    reg [10:0] rx_count = 0;
    reg rx_bad = 0;
    reg [31:0] magic = 0;
    reg [7:0] opcode = 0;
    reg [7:0] region = 0;
    reg [15:0] count = 0;
    reg [31:0] packet_seq = 0;
    reg [31:0] value = 0;
    reg [31:0] expected_sequence = 1;
    reg [31:0] word_buf [0:63];
    reg [7:0] ack_status = ACK_OK;
    reg [31:0] ack_image_status = 0;
    reg [6:0] operation_index = 0;
    reg [6:0] operation_total = 0;
    reg [4:0] tx_index = 0;
    (* ASYNC_REG = "TRUE" *) reg [2:0] ack_sync = 0;

    assign rx_hdr_ready = (state == S_IDLE);
    assign rx_ready = (state == S_RECV || state == S_DROP);
    assign tx_hdr_valid = (state == S_TX_HEADER);
    assign tx_valid = (state == S_TX_BYTES);
    assign tx_last = (tx_index == 15);
    assign tx_length = 16'd24; // UDP header (8) plus 16 response bytes.

    always @* begin
        case (tx_index)
            0: tx_data = 8'h43; // CNSA
            1: tx_data = 8'h4e;
            2: tx_data = 8'h53;
            3: tx_data = 8'h41;
            4: tx_data = ack_status;
            5: tx_data = opcode;
            6: tx_data = region;
            7: tx_data = 0;
            8: tx_data = packet_seq[7:0];
            9: tx_data = packet_seq[15:8];
            10: tx_data = packet_seq[23:16];
            11: tx_data = packet_seq[31:24];
            12: tx_data = ack_image_status[7:0];
            13: tx_data = ack_image_status[15:8];
            14: tx_data = ack_image_status[23:16];
            default: tx_data = ack_image_status[31:24];
        endcase
    end

    always @(posedge clk) begin
        ack_sync <= {ack_sync[1:0], cmd_ack_toggle};
        if (rst) begin
            state <= S_IDLE;
            rx_count <= 0;
            rx_bad <= 0;
            expected_sequence <= 1;
            cmd_toggle <= 0;
            cmd_read <= 0;
            cmd_addr <= 0;
            cmd_data <= 0;
            operation_index <= 0;
            operation_total <= 0;
            tx_index <= 0;
            ack_status <= ACK_OK;
            ack_image_status <= 0;
            tx_dest_ip <= 0;
            tx_dest_port <= 0;
        end else begin
            case (state)
                S_IDLE: if (rx_hdr_valid) begin
                    // Ignore unrelated LAN broadcasts and foreign UDP ports.
                    // Replying to those packets can fill the ARP/TX queues
                    // while the host has no route back to their source IP.
                    if (rx_dest_ip != 32'hc0a80180 || rx_dest_port != 16'd4321) begin
                        state <= (rx_length <= 16'd8) ? S_IDLE : S_DROP;
                    end else begin
                        tx_dest_ip <= rx_source_ip;
                        tx_dest_port <= rx_source_port;
                        rx_bad <= 0;
                        rx_count <= 0;
                        magic <= 0;
                        opcode <= 0;
                        region <= 0;
                        count <= 0;
                        packet_seq <= 0;
                        value <= 0;
                        state <= (rx_length <= 16'd8) ? S_VALIDATE : S_RECV;
                    end
                end
                S_DROP: if (rx_valid && rx_last) state <= S_IDLE;
                S_RECV: if (rx_valid) begin
                    if (rx_user || rx_count >= 272)
                        rx_bad <= 1;
                    if (rx_count < 4)
                        magic[8*rx_count +: 8] <= rx_data;
                    else if (rx_count == 4)
                        opcode <= rx_data;
                    else if (rx_count == 5)
                        region <= rx_data;
                    else if (rx_count < 8)
                        count[8*(rx_count-6) +: 8] <= rx_data;
                    else if (rx_count < 12)
                        packet_seq[8*(rx_count-8) +: 8] <= rx_data;
                    else if (rx_count < 16)
                        value[8*(rx_count-12) +: 8] <= rx_data;
                    else if (rx_count < 272)
                        word_buf[(rx_count-16)>>2][8*((rx_count-16)&3) +: 8] <= rx_data;
                    rx_count <= rx_count + 1'b1;
                    if (rx_last)
                        state <= S_VALIDATE;
                end
                S_VALIDATE: begin
                    ack_image_status <= 0;
                    if (rx_bad || magic != 32'h45534e43 ||
                        !(opcode == OP_BEGIN || opcode == OP_DATA ||
                          opcode == OP_COMMIT || opcode == OP_STATUS) ||
                        ((opcode == OP_DATA) ?
                            (count == 0 || count > 64 || region > 3 ||
                             rx_count != 16 + count*4) : (rx_count != 16)) ||
                        (opcode == OP_BEGIN && (count == 0 || count > 6279 ||
                                                value > 350185))) begin
                        ack_status <= ACK_INVALID;
                        state <= S_TX_HEADER;
                    end else if (opcode != OP_BEGIN && packet_seq == expected_sequence - 1) begin
                        ack_status <= ACK_DUPLICATE;
                        state <= S_TX_HEADER;
                    end else if (opcode != OP_BEGIN && packet_seq != expected_sequence) begin
                        ack_status <= ACK_SEQUENCE;
                        state <= S_TX_HEADER;
                    end else begin
                        ack_status <= ACK_OK;
                        operation_index <= 0;
                        if (opcode == OP_BEGIN)
                            operation_total <= 3;
                        else if (opcode == OP_DATA)
                            operation_total <= count[6:0] + 1'b1;
                        else if (opcode == OP_COMMIT)
                            operation_total <= 2;
                        else
                            operation_total <= 0;
                        state <= S_ISSUE;
                    end
                end
                S_ISSUE: begin
                    if (operation_index == operation_total) begin
                        cmd_read <= 1;
                        cmd_addr <= 20'h00030;
                        cmd_data <= 0;
                        cmd_toggle <= ~cmd_toggle;
                        state <= S_WAIT_STATUS;
                    end else begin
                        cmd_read <= 0;
                        if (opcode == OP_BEGIN) begin
                            case (operation_index)
                                0: begin cmd_addr <= 20'h00030; cmd_data <= 1; end
                                1: begin cmd_addr <= 20'h00034; cmd_data <= {16'd0,count}; end
                                default: begin cmd_addr <= 20'h00038; cmd_data <= value; end
                            endcase
                        end else if (opcode == OP_DATA) begin
                            if (operation_index == 0) begin
                                cmd_addr <= 20'h0003c;
                                cmd_data <= {24'd0,region};
                            end else begin
                                cmd_addr <= 20'h00040;
                                cmd_data <= word_buf[operation_index-1];
                            end
                        end else begin
                            if (operation_index == 0) begin
                                cmd_addr <= 20'h00044;
                                cmd_data <= value;
                            end else begin
                                cmd_addr <= 20'h00030;
                                cmd_data <= 2;
                            end
                        end
                        cmd_toggle <= ~cmd_toggle;
                        state <= S_WAIT_WRITE;
                    end
                end
                S_WAIT_WRITE: if (ack_sync[2] == cmd_toggle) begin
                    operation_index <= operation_index + 1'b1;
                    state <= S_ISSUE;
                end
                S_WAIT_STATUS: if (ack_sync[2] == cmd_toggle) begin
                    ack_image_status <= cmd_read_data;
                    if (cmd_read_data[2] ||
                        (opcode == OP_COMMIT && cmd_read_data != 1) ||
                        ((opcode == OP_BEGIN || opcode == OP_DATA) &&
                         !cmd_read_data[1]))
                        ack_status <= ACK_ENGINE;
                    else
                        expected_sequence <= packet_seq + 1'b1;
                    state <= S_TX_HEADER;
                end
                S_TX_HEADER: if (tx_hdr_ready) begin
                    tx_index <= 0;
                    state <= S_TX_BYTES;
                end
                S_TX_BYTES: if (tx_ready) begin
                    if (tx_index == 15)
                        state <= S_IDLE;
                    else
                        tx_index <= tx_index + 1'b1;
                end
                default: state <= S_IDLE;
            endcase
        end
    end
endmodule
