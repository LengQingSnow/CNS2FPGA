/*

Copyright (c) 2014-2018 Alex Forencich

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

*/

// Language: Verilog 2001

`resetall
`timescale 1ns / 1ps
`default_nettype none

/*
 * FPGA core logic
 */
module cns2fpga_eth_stack #
(
    parameter TARGET = "GENERIC",
    parameter integer PHY_RESET_CYCLES = 2500000,
    parameter integer PHY_MAC_SETTLE_CYCLES = 12500,
    parameter integer TX_RAM_PIPELINE = 1
)
(
    /*
     * Clock: 125MHz
     * Synchronous reset
     */
    input  wire       clk,
    input  wire       clk90,
    input  wire       rst,

    /*
     * Ethernet: 1000BASE-T RGMII
     */
    input  wire       phy_rx_clk,
    input  wire [3:0] phy_rxd,
    input  wire       phy_rx_ctl,
    output wire       phy_tx_clk,
    output wire [3:0] phy_txd,
    output wire       phy_tx_ctl,
    output wire       phy_reset_n,
    output wire       phy_link_activity,
    output wire [31:0] diag_status,
    output wire [15:0] diag_rx_clock_gray,
    output wire [31:0] diag_rx_counts,
    output wire [31:0] diag_tx_counts,
    output wire [31:0] diag_test_count,
    output wire [47:0] diag_last_tx_dest_mac,
    output wire [15:0] diag_last_tx_eth_type,
    output wire [47:0] diag_last_rx_src_mac,
    output wire [15:0] diag_last_rx_eth_type,
    output wire [31:0] diag_error_counts,
    output wire [31:0] diag_flow_live,
    output wire [31:0] diag_flow_counts,
    input  wire       test_frame_toggle,
    output wire       cmd_toggle,
    output wire       cmd_read,
    output wire [19:0] cmd_addr,
    output wire [31:0] cmd_data,
    input  wire       cmd_ack_toggle,
    input  wire [31:0] cmd_read_data
);

// AXI between MAC and Ethernet modules
wire [7:0] rx_axis_tdata;
wire rx_axis_tvalid;
wire rx_axis_tready;
wire rx_axis_tlast;
wire rx_axis_tuser;

wire [7:0] tx_axis_tdata;
wire tx_axis_tvalid;
wire tx_axis_tready;
wire tx_axis_tlast;
wire tx_axis_tuser;
wire [7:0] normal_tx_axis_tdata;
wire normal_tx_axis_tvalid;
wire normal_tx_axis_tready;
wire normal_tx_axis_tlast;
wire normal_tx_axis_tuser;
wire normal_tx_busy;

// Ethernet frame between Ethernet modules and UDP stack
wire rx_eth_hdr_ready;
wire rx_eth_hdr_valid;
wire [47:0] rx_eth_dest_mac;
wire [47:0] rx_eth_src_mac;
wire [15:0] rx_eth_type;
wire [7:0] rx_eth_payload_axis_tdata;
wire rx_eth_payload_axis_tvalid;
wire rx_eth_payload_axis_tready;
wire rx_eth_payload_axis_tlast;
wire rx_eth_payload_axis_tuser;

wire tx_eth_hdr_ready;
wire tx_eth_hdr_valid;
wire [47:0] tx_eth_dest_mac;
wire [47:0] tx_eth_src_mac;
wire [15:0] tx_eth_type;
wire [7:0] tx_eth_payload_axis_tdata;
wire tx_eth_payload_axis_tvalid;
wire tx_eth_payload_axis_tready;
wire tx_eth_payload_axis_tlast;
wire tx_eth_payload_axis_tuser;

// IP frame connections
wire rx_ip_hdr_valid;
wire rx_ip_hdr_ready;
wire [47:0] rx_ip_eth_dest_mac;
wire [47:0] rx_ip_eth_src_mac;
wire [15:0] rx_ip_eth_type;
wire [3:0] rx_ip_version;
wire [3:0] rx_ip_ihl;
wire [5:0] rx_ip_dscp;
wire [1:0] rx_ip_ecn;
wire [15:0] rx_ip_length;
wire [15:0] rx_ip_identification;
wire [2:0] rx_ip_flags;
wire [12:0] rx_ip_fragment_offset;
wire [7:0] rx_ip_ttl;
wire [7:0] rx_ip_protocol;
wire [15:0] rx_ip_header_checksum;
wire [31:0] rx_ip_source_ip;
wire [31:0] rx_ip_dest_ip;
wire [7:0] rx_ip_payload_axis_tdata;
wire rx_ip_payload_axis_tvalid;
wire rx_ip_payload_axis_tready;
wire rx_ip_payload_axis_tlast;
wire rx_ip_payload_axis_tuser;

wire tx_ip_hdr_valid;
wire tx_ip_hdr_ready;
wire [5:0] tx_ip_dscp;
wire [1:0] tx_ip_ecn;
wire [15:0] tx_ip_length;
wire [7:0] tx_ip_ttl;
wire [7:0] tx_ip_protocol;
wire [31:0] tx_ip_source_ip;
wire [31:0] tx_ip_dest_ip;
wire [7:0] tx_ip_payload_axis_tdata;
wire tx_ip_payload_axis_tvalid;
wire tx_ip_payload_axis_tready;
wire tx_ip_payload_axis_tlast;
wire tx_ip_payload_axis_tuser;

// UDP frame connections
wire rx_udp_hdr_valid;
wire rx_udp_hdr_ready;
wire [47:0] rx_udp_eth_dest_mac;
wire [47:0] rx_udp_eth_src_mac;
wire [15:0] rx_udp_eth_type;
wire [3:0] rx_udp_ip_version;
wire [3:0] rx_udp_ip_ihl;
wire [5:0] rx_udp_ip_dscp;
wire [1:0] rx_udp_ip_ecn;
wire [15:0] rx_udp_ip_length;
wire [15:0] rx_udp_ip_identification;
wire [2:0] rx_udp_ip_flags;
wire [12:0] rx_udp_ip_fragment_offset;
wire [7:0] rx_udp_ip_ttl;
wire [7:0] rx_udp_ip_protocol;
wire [15:0] rx_udp_ip_header_checksum;
wire [31:0] rx_udp_ip_source_ip;
wire [31:0] rx_udp_ip_dest_ip;
wire [15:0] rx_udp_source_port;
wire [15:0] rx_udp_dest_port;
wire [15:0] rx_udp_length;
wire [15:0] rx_udp_checksum;
wire [7:0] rx_udp_payload_axis_tdata;
wire rx_udp_payload_axis_tvalid;
wire rx_udp_payload_axis_tready;
wire rx_udp_payload_axis_tlast;
wire rx_udp_payload_axis_tuser;

wire tx_udp_hdr_valid;
wire tx_udp_hdr_ready;
wire [5:0] tx_udp_ip_dscp;
wire [1:0] tx_udp_ip_ecn;
wire [7:0] tx_udp_ip_ttl;
wire [31:0] tx_udp_ip_source_ip;
wire [31:0] tx_udp_ip_dest_ip;
wire [15:0] tx_udp_source_port;
wire [15:0] tx_udp_dest_port;
wire [15:0] tx_udp_length;
wire [15:0] tx_udp_checksum;
wire [7:0] tx_udp_payload_axis_tdata;
wire tx_udp_payload_axis_tvalid;
wire tx_udp_payload_axis_tready;
wire tx_udp_payload_axis_tlast;
wire tx_udp_payload_axis_tuser;

wire [7:0] rx_fifo_udp_payload_axis_tdata;
wire rx_fifo_udp_payload_axis_tvalid;
wire rx_fifo_udp_payload_axis_tready;
wire rx_fifo_udp_payload_axis_tlast;
wire rx_fifo_udp_payload_axis_tuser;

wire [7:0] tx_fifo_udp_payload_axis_tdata;
wire tx_fifo_udp_payload_axis_tvalid;
wire tx_fifo_udp_payload_axis_tready;
wire tx_fifo_udp_payload_axis_tlast;
wire tx_fifo_udp_payload_axis_tuser;

// Configuration
wire [47:0] local_mac   = 48'h02_00_00_00_00_15;
wire [31:0] local_ip    = {8'd192, 8'd168, 8'd1,   8'd128};
wire [31:0] gateway_ip  = {8'd192, 8'd168, 8'd1,   8'd1};
wire [31:0] subnet_mask = {8'd255, 8'd255, 8'd255, 8'd0};

// IP ports not used
assign rx_ip_hdr_ready = 1;
assign rx_ip_payload_axis_tready = 1;

assign tx_ip_hdr_valid = 0;
assign tx_ip_dscp = 0;
assign tx_ip_ecn = 0;
assign tx_ip_length = 0;
assign tx_ip_ttl = 0;
assign tx_ip_protocol = 0;
assign tx_ip_source_ip = 0;
assign tx_ip_dest_ip = 0;
assign tx_ip_payload_axis_tdata = 0;
assign tx_ip_payload_axis_tvalid = 0;
assign tx_ip_payload_axis_tlast = 0;
assign tx_ip_payload_axis_tuser = 0;

// KSZ9031RNX needs reset held after supplies stabilize. Keep the MAC idle
// until the PHY has had another 100 us to establish its clocks and straps.
reg [22:0] phy_startup_count = 0;
always @(posedge clk) begin
    if (rst)
        phy_startup_count <= 0;
    else if (phy_startup_count < PHY_RESET_CYCLES + PHY_MAC_SETTLE_CYCLES)
        phy_startup_count <= phy_startup_count + 1'b1;
end
assign phy_reset_n = !rst && phy_startup_count >= PHY_RESET_CYCLES;
wire mac_rst = rst || phy_startup_count < PHY_RESET_CYCLES + PHY_MAC_SETTLE_CYCLES;
assign phy_link_activity = rx_udp_payload_axis_tvalid;

// Read-only on-board observability; no dependence on the graph upload path.
reg [15:0] raw_rx_clock_count = 0;
reg raw_rx_ctl_seen = 0;
always @(posedge phy_rx_clk or posedge rst) begin
    if (rst) begin
        raw_rx_clock_count <= 0;
        raw_rx_ctl_seen <= 0;
    end else begin
        raw_rx_clock_count <= raw_rx_clock_count + 1'b1;
        raw_rx_ctl_seen <= raw_rx_ctl_seen | phy_rx_ctl;
    end
end
wire [15:0] raw_rx_clock_gray = raw_rx_clock_count ^ (raw_rx_clock_count >> 1);
(* ASYNC_REG = "TRUE" *) reg [15:0] raw_rx_clock_gray_sync1 = 0;
(* ASYNC_REG = "TRUE" *) reg [15:0] raw_rx_clock_gray_sync2 = 0;
(* ASYNC_REG = "TRUE" *) reg raw_rx_ctl_sync1 = 0;
(* ASYNC_REG = "TRUE" *) reg raw_rx_ctl_sync2 = 0;
reg [12:0] seen = 0;
reg [15:0] rx_good_count = 0;
reg [15:0] rx_udp_count = 0;
reg [15:0] tx_good_count = 0;
reg [15:0] tx_udp_count = 0;
reg [31:0] test_sent_count = 0;
reg [47:0] last_tx_dest_mac = 0;
reg [15:0] last_tx_eth_type = 0;
reg [47:0] last_rx_src_mac = 0;
reg [15:0] last_rx_eth_type = 0;
reg [15:0] tx_underflow_count = 0;
reg [15:0] rx_bad_fcs_count = 0;
reg [15:0] rx_overflow_count = 0;
reg [15:0] rx_axis_handshake_count = 0;
wire rx_fifo_good_frame;
wire rx_fifo_bad_frame;
wire rx_fifo_overflow;
wire rx_error_bad_fcs;
wire rx_error_bad_frame;
wire tx_fifo_good_frame;
wire tx_error_underflow;
wire [1:0] mac_speed;
always @(posedge clk) begin
    raw_rx_clock_gray_sync1 <= raw_rx_clock_gray;
    raw_rx_clock_gray_sync2 <= raw_rx_clock_gray_sync1;
    raw_rx_ctl_sync1 <= raw_rx_ctl_seen;
    raw_rx_ctl_sync2 <= raw_rx_ctl_sync1;
    if (rst)
        seen <= 0;
    else begin
        seen[0] <= seen[0] | rx_axis_tvalid;
        seen[1] <= seen[1] | rx_fifo_good_frame;
        seen[2] <= seen[2] | rx_fifo_bad_frame;
        seen[3] <= seen[3] | rx_error_bad_fcs;
        seen[4] <= seen[4] | rx_error_bad_frame;
        seen[5] <= seen[5] | rx_eth_hdr_valid;
        seen[6] <= seen[6] | rx_ip_hdr_valid;
        seen[7] <= seen[7] | rx_udp_hdr_valid;
        seen[8] <= seen[8] | tx_udp_hdr_valid;
        seen[9] <= seen[9] | tx_eth_hdr_valid;
        seen[10] <= seen[10] | tx_axis_tvalid;
        seen[11] <= seen[11] | tx_fifo_good_frame;
        seen[12] <= seen[12] | rx_udp_payload_axis_tvalid;
    end
    if (rst) begin
        rx_good_count <= 0;
        rx_udp_count <= 0;
        tx_good_count <= 0;
        tx_udp_count <= 0;
        last_tx_dest_mac <= 0;
        last_tx_eth_type <= 0;
        last_rx_src_mac <= 0;
        last_rx_eth_type <= 0;
        tx_underflow_count <= 0;
        rx_bad_fcs_count <= 0;
        rx_overflow_count <= 0;
        rx_axis_handshake_count <= 0;
    end else begin
        if (rx_fifo_good_frame) rx_good_count <= rx_good_count + 1'b1;
        if (rx_udp_hdr_valid && rx_udp_hdr_ready) rx_udp_count <= rx_udp_count + 1'b1;
        if (tx_fifo_good_frame) tx_good_count <= tx_good_count + 1'b1;
        if (tx_udp_hdr_valid && tx_udp_hdr_ready) tx_udp_count <= tx_udp_count + 1'b1;
        if (tx_error_underflow) tx_underflow_count <= tx_underflow_count + 1'b1;
        if (rx_error_bad_fcs) rx_bad_fcs_count <= rx_bad_fcs_count + 1'b1;
        if (rx_fifo_overflow) rx_overflow_count <= rx_overflow_count + 1'b1;
        if (rx_axis_tvalid && rx_axis_tready)
            rx_axis_handshake_count <= rx_axis_handshake_count + 1'b1;
        if (tx_eth_hdr_valid && tx_eth_hdr_ready) begin
            last_tx_dest_mac <= tx_eth_dest_mac;
            last_tx_eth_type <= tx_eth_type;
        end
        if (rx_eth_hdr_valid && rx_eth_hdr_ready) begin
            last_rx_src_mac <= rx_eth_src_mac;
            last_rx_eth_type <= rx_eth_type;
        end
    end
end
assign diag_status = {14'd0, mac_speed, seen, raw_rx_ctl_sync2, !mac_rst, phy_reset_n};
assign diag_rx_clock_gray = raw_rx_clock_gray_sync2;
assign diag_rx_counts = {rx_good_count, rx_udp_count};
assign diag_tx_counts = {tx_good_count, tx_udp_count};
assign diag_test_count = test_sent_count;
assign diag_last_tx_dest_mac = last_tx_dest_mac;
assign diag_last_tx_eth_type = last_tx_eth_type;
assign diag_last_rx_src_mac = last_rx_src_mac;
assign diag_last_rx_eth_type = last_rx_eth_type;
assign diag_error_counts = {tx_underflow_count, rx_bad_fcs_count};
assign diag_flow_live = {19'd0,
    normal_tx_busy, normal_tx_axis_tvalid, normal_tx_axis_tready,
    tx_eth_hdr_valid, tx_eth_hdr_ready,
    rx_udp_payload_axis_tvalid, rx_udp_payload_axis_tready,
    rx_udp_hdr_valid, rx_udp_hdr_ready,
    rx_eth_hdr_valid, rx_eth_hdr_ready,
    rx_axis_tvalid, rx_axis_tready};
assign diag_flow_counts = {rx_overflow_count, rx_axis_handshake_count};

// Diagnostic broadcast frame: proves the board-to-PC transmit path without
// relying on the ARP cache, IP/UDP stack, or a loaded graph image.
(* ASYNC_REG = "TRUE" *) reg [2:0] test_toggle_sync = 0;
reg test_toggle_consumed = 0;
reg test_active = 0;
reg [5:0] test_index = 0;
reg [5:0] test_drain = 0;
reg [7:0] test_data;
always @* begin
    case (test_index)
        0,1,2,3,4,5: test_data = 8'hff;
        6: test_data = 8'h02;
        7,8,9,10: test_data = 8'h00;
        11: test_data = 8'h15;
        12: test_data = 8'h88;
        13: test_data = 8'hb5;
        default: test_data = {2'b00,test_index} ^ 8'ha5;
    endcase
end
assign tx_axis_tdata = (test_active || test_drain != 0) ? test_data : normal_tx_axis_tdata;
assign tx_axis_tvalid = test_active ? 1'b1 : (test_drain != 0 ? 1'b0 : normal_tx_axis_tvalid);
assign tx_axis_tlast = test_active ? (test_index == 59) : normal_tx_axis_tlast;
assign tx_axis_tuser = (test_active || test_drain != 0) ? 1'b0 : normal_tx_axis_tuser;
assign normal_tx_axis_tready = (test_active || test_drain != 0) ? 1'b0 : tx_axis_tready;
always @(posedge clk) begin
    if (rst) begin
        test_toggle_sync <= 0;
        test_toggle_consumed <= 0;
        test_active <= 0;
        test_index <= 0;
        test_drain <= 0;
        test_sent_count <= 0;
    end else begin
        test_toggle_sync <= {test_toggle_sync[1:0], test_frame_toggle};
        if (test_drain != 0) test_drain <= test_drain - 1'b1;
        if (!test_active && test_drain == 0 &&
            test_toggle_sync[2] != test_toggle_consumed && !normal_tx_busy) begin
            test_toggle_consumed <= test_toggle_sync[2];
            test_active <= 1;
            test_index <= 0;
        end else if (test_active && tx_axis_tready) begin
            if (test_index == 59) begin
                test_active <= 0;
                test_drain <= 6'd32;
                test_sent_count <= test_sent_count + 1'b1;
            end else begin
                test_index <= test_index + 1'b1;
            end
        end
    end
end

cns2fpga_udp_command udp_command_inst (
    .clk(clk), .rst(mac_rst),
    .rx_hdr_valid(rx_udp_hdr_valid), .rx_hdr_ready(rx_udp_hdr_ready),
    .rx_source_ip(rx_udp_ip_source_ip), .rx_dest_ip(rx_udp_ip_dest_ip),
    .rx_source_port(rx_udp_source_port), .rx_dest_port(rx_udp_dest_port),
    .rx_length(rx_udp_length),
    .rx_data(rx_udp_payload_axis_tdata), .rx_valid(rx_udp_payload_axis_tvalid),
    .rx_ready(rx_udp_payload_axis_tready), .rx_last(rx_udp_payload_axis_tlast),
    .rx_user(rx_udp_payload_axis_tuser),
    .tx_hdr_valid(tx_udp_hdr_valid), .tx_hdr_ready(tx_udp_hdr_ready),
    .tx_dest_ip(tx_udp_ip_dest_ip), .tx_dest_port(tx_udp_dest_port),
    .tx_length(tx_udp_length),
    .tx_data(tx_udp_payload_axis_tdata), .tx_valid(tx_udp_payload_axis_tvalid),
    .tx_ready(tx_udp_payload_axis_tready), .tx_last(tx_udp_payload_axis_tlast),
    .cmd_toggle(cmd_toggle), .cmd_read(cmd_read), .cmd_addr(cmd_addr),
    .cmd_data(cmd_data), .cmd_ack_toggle(cmd_ack_toggle),
    .cmd_read_data(cmd_read_data)
);
assign tx_udp_ip_dscp = 0;
assign tx_udp_ip_ecn = 0;
assign tx_udp_ip_ttl = 64;
assign tx_udp_ip_source_ip = local_ip;
assign tx_udp_source_port = 16'd4321;
assign tx_udp_checksum = 0;
assign tx_udp_payload_axis_tuser = 0;

eth_mac_1g_rgmii_fifo #(
    .TARGET(TARGET),
    .IODDR_STYLE("IODDR"),
    .CLOCK_INPUT_STYLE("BUFG"),
    // KSZ9031RNX defaults require the MAC to provide the TX clock skew;
    // the forwarded clock is delayed by 95.625 degrees (2.125 ns).
    .USE_CLK90("TRUE"),
    .ENABLE_PADDING(1),
    .MIN_FRAME_LENGTH(64),
    .TX_FIFO_DEPTH(4096),
    .TX_FIFO_RAM_PIPELINE(TX_RAM_PIPELINE),
    .TX_FRAME_FIFO(1),
    .RX_FIFO_DEPTH(4096),
    .RX_FRAME_FIFO(1)
)
eth_mac_inst (
    .gtx_clk(clk),
    .gtx_clk90(clk90),
    .gtx_rst(mac_rst),
    .logic_clk(clk),
    .logic_rst(mac_rst),

    .tx_axis_tdata(tx_axis_tdata),
    .tx_axis_tvalid(tx_axis_tvalid),
    .tx_axis_tready(tx_axis_tready),
    .tx_axis_tlast(tx_axis_tlast),
    .tx_axis_tuser(tx_axis_tuser),

    .rx_axis_tdata(rx_axis_tdata),
    .rx_axis_tvalid(rx_axis_tvalid),
    .rx_axis_tready(rx_axis_tready),
    .rx_axis_tlast(rx_axis_tlast),
    .rx_axis_tuser(rx_axis_tuser),

    .rgmii_rx_clk(phy_rx_clk),
    .rgmii_rxd(phy_rxd),
    .rgmii_rx_ctl(phy_rx_ctl),
    .rgmii_tx_clk(phy_tx_clk),
    .rgmii_txd(phy_txd),
    .rgmii_tx_ctl(phy_tx_ctl),

    .tx_fifo_overflow(),
    .tx_fifo_bad_frame(),
    .tx_fifo_good_frame(tx_fifo_good_frame),
    .tx_error_underflow(tx_error_underflow),
    .rx_error_bad_frame(rx_error_bad_frame),
    .rx_error_bad_fcs(rx_error_bad_fcs),
    .rx_fifo_overflow(rx_fifo_overflow),
    .rx_fifo_bad_frame(rx_fifo_bad_frame),
    .rx_fifo_good_frame(rx_fifo_good_frame),
    .speed(mac_speed),

    .cfg_ifg(8'd12),
    .cfg_tx_enable(1'b1),
    .cfg_rx_enable(1'b1)
);

eth_axis_rx
eth_axis_rx_inst (
    .clk(clk),
    .rst(mac_rst),
    // AXI input
    .s_axis_tdata(rx_axis_tdata),
    .s_axis_tvalid(rx_axis_tvalid),
    .s_axis_tready(rx_axis_tready),
    .s_axis_tlast(rx_axis_tlast),
    .s_axis_tuser(rx_axis_tuser),
    // Ethernet frame output
    .m_eth_hdr_valid(rx_eth_hdr_valid),
    .m_eth_hdr_ready(rx_eth_hdr_ready),
    .m_eth_dest_mac(rx_eth_dest_mac),
    .m_eth_src_mac(rx_eth_src_mac),
    .m_eth_type(rx_eth_type),
    .m_eth_payload_axis_tdata(rx_eth_payload_axis_tdata),
    .m_eth_payload_axis_tvalid(rx_eth_payload_axis_tvalid),
    .m_eth_payload_axis_tready(rx_eth_payload_axis_tready),
    .m_eth_payload_axis_tlast(rx_eth_payload_axis_tlast),
    .m_eth_payload_axis_tuser(rx_eth_payload_axis_tuser),
    // Status signals
    .busy(),
    .error_header_early_termination()
);

eth_axis_tx
eth_axis_tx_inst (
    .clk(clk),
    .rst(mac_rst),
    // Ethernet frame input
    .s_eth_hdr_valid(tx_eth_hdr_valid),
    .s_eth_hdr_ready(tx_eth_hdr_ready),
    .s_eth_dest_mac(tx_eth_dest_mac),
    .s_eth_src_mac(tx_eth_src_mac),
    .s_eth_type(tx_eth_type),
    .s_eth_payload_axis_tdata(tx_eth_payload_axis_tdata),
    .s_eth_payload_axis_tvalid(tx_eth_payload_axis_tvalid),
    .s_eth_payload_axis_tready(tx_eth_payload_axis_tready),
    .s_eth_payload_axis_tlast(tx_eth_payload_axis_tlast),
    .s_eth_payload_axis_tuser(tx_eth_payload_axis_tuser),
    // AXI output
    .m_axis_tdata(normal_tx_axis_tdata),
    .m_axis_tvalid(normal_tx_axis_tvalid),
    .m_axis_tready(normal_tx_axis_tready),
    .m_axis_tlast(normal_tx_axis_tlast),
    .m_axis_tuser(normal_tx_axis_tuser),
    // Status signals
    .busy(normal_tx_busy)
);

udp_complete
udp_complete_inst (
    .clk(clk),
    .rst(mac_rst),
    // Ethernet frame input
    .s_eth_hdr_valid(rx_eth_hdr_valid),
    .s_eth_hdr_ready(rx_eth_hdr_ready),
    .s_eth_dest_mac(rx_eth_dest_mac),
    .s_eth_src_mac(rx_eth_src_mac),
    .s_eth_type(rx_eth_type),
    .s_eth_payload_axis_tdata(rx_eth_payload_axis_tdata),
    .s_eth_payload_axis_tvalid(rx_eth_payload_axis_tvalid),
    .s_eth_payload_axis_tready(rx_eth_payload_axis_tready),
    .s_eth_payload_axis_tlast(rx_eth_payload_axis_tlast),
    .s_eth_payload_axis_tuser(rx_eth_payload_axis_tuser),
    // Ethernet frame output
    .m_eth_hdr_valid(tx_eth_hdr_valid),
    .m_eth_hdr_ready(tx_eth_hdr_ready),
    .m_eth_dest_mac(tx_eth_dest_mac),
    .m_eth_src_mac(tx_eth_src_mac),
    .m_eth_type(tx_eth_type),
    .m_eth_payload_axis_tdata(tx_eth_payload_axis_tdata),
    .m_eth_payload_axis_tvalid(tx_eth_payload_axis_tvalid),
    .m_eth_payload_axis_tready(tx_eth_payload_axis_tready),
    .m_eth_payload_axis_tlast(tx_eth_payload_axis_tlast),
    .m_eth_payload_axis_tuser(tx_eth_payload_axis_tuser),
    // IP frame input
    .s_ip_hdr_valid(tx_ip_hdr_valid),
    .s_ip_hdr_ready(tx_ip_hdr_ready),
    .s_ip_dscp(tx_ip_dscp),
    .s_ip_ecn(tx_ip_ecn),
    .s_ip_length(tx_ip_length),
    .s_ip_ttl(tx_ip_ttl),
    .s_ip_protocol(tx_ip_protocol),
    .s_ip_source_ip(tx_ip_source_ip),
    .s_ip_dest_ip(tx_ip_dest_ip),
    .s_ip_payload_axis_tdata(tx_ip_payload_axis_tdata),
    .s_ip_payload_axis_tvalid(tx_ip_payload_axis_tvalid),
    .s_ip_payload_axis_tready(tx_ip_payload_axis_tready),
    .s_ip_payload_axis_tlast(tx_ip_payload_axis_tlast),
    .s_ip_payload_axis_tuser(tx_ip_payload_axis_tuser),
    // IP frame output
    .m_ip_hdr_valid(rx_ip_hdr_valid),
    .m_ip_hdr_ready(rx_ip_hdr_ready),
    .m_ip_eth_dest_mac(rx_ip_eth_dest_mac),
    .m_ip_eth_src_mac(rx_ip_eth_src_mac),
    .m_ip_eth_type(rx_ip_eth_type),
    .m_ip_version(rx_ip_version),
    .m_ip_ihl(rx_ip_ihl),
    .m_ip_dscp(rx_ip_dscp),
    .m_ip_ecn(rx_ip_ecn),
    .m_ip_length(rx_ip_length),
    .m_ip_identification(rx_ip_identification),
    .m_ip_flags(rx_ip_flags),
    .m_ip_fragment_offset(rx_ip_fragment_offset),
    .m_ip_ttl(rx_ip_ttl),
    .m_ip_protocol(rx_ip_protocol),
    .m_ip_header_checksum(rx_ip_header_checksum),
    .m_ip_source_ip(rx_ip_source_ip),
    .m_ip_dest_ip(rx_ip_dest_ip),
    .m_ip_payload_axis_tdata(rx_ip_payload_axis_tdata),
    .m_ip_payload_axis_tvalid(rx_ip_payload_axis_tvalid),
    .m_ip_payload_axis_tready(rx_ip_payload_axis_tready),
    .m_ip_payload_axis_tlast(rx_ip_payload_axis_tlast),
    .m_ip_payload_axis_tuser(rx_ip_payload_axis_tuser),
    // UDP frame input
    .s_udp_hdr_valid(tx_udp_hdr_valid),
    .s_udp_hdr_ready(tx_udp_hdr_ready),
    .s_udp_ip_dscp(tx_udp_ip_dscp),
    .s_udp_ip_ecn(tx_udp_ip_ecn),
    .s_udp_ip_ttl(tx_udp_ip_ttl),
    .s_udp_ip_source_ip(tx_udp_ip_source_ip),
    .s_udp_ip_dest_ip(tx_udp_ip_dest_ip),
    .s_udp_source_port(tx_udp_source_port),
    .s_udp_dest_port(tx_udp_dest_port),
    .s_udp_length(tx_udp_length),
    .s_udp_checksum(tx_udp_checksum),
    .s_udp_payload_axis_tdata(tx_udp_payload_axis_tdata),
    .s_udp_payload_axis_tvalid(tx_udp_payload_axis_tvalid),
    .s_udp_payload_axis_tready(tx_udp_payload_axis_tready),
    .s_udp_payload_axis_tlast(tx_udp_payload_axis_tlast),
    .s_udp_payload_axis_tuser(tx_udp_payload_axis_tuser),
    // UDP frame output
    .m_udp_hdr_valid(rx_udp_hdr_valid),
    .m_udp_hdr_ready(rx_udp_hdr_ready),
    .m_udp_eth_dest_mac(rx_udp_eth_dest_mac),
    .m_udp_eth_src_mac(rx_udp_eth_src_mac),
    .m_udp_eth_type(rx_udp_eth_type),
    .m_udp_ip_version(rx_udp_ip_version),
    .m_udp_ip_ihl(rx_udp_ip_ihl),
    .m_udp_ip_dscp(rx_udp_ip_dscp),
    .m_udp_ip_ecn(rx_udp_ip_ecn),
    .m_udp_ip_length(rx_udp_ip_length),
    .m_udp_ip_identification(rx_udp_ip_identification),
    .m_udp_ip_flags(rx_udp_ip_flags),
    .m_udp_ip_fragment_offset(rx_udp_ip_fragment_offset),
    .m_udp_ip_ttl(rx_udp_ip_ttl),
    .m_udp_ip_protocol(rx_udp_ip_protocol),
    .m_udp_ip_header_checksum(rx_udp_ip_header_checksum),
    .m_udp_ip_source_ip(rx_udp_ip_source_ip),
    .m_udp_ip_dest_ip(rx_udp_ip_dest_ip),
    .m_udp_source_port(rx_udp_source_port),
    .m_udp_dest_port(rx_udp_dest_port),
    .m_udp_length(rx_udp_length),
    .m_udp_checksum(rx_udp_checksum),
    .m_udp_payload_axis_tdata(rx_udp_payload_axis_tdata),
    .m_udp_payload_axis_tvalid(rx_udp_payload_axis_tvalid),
    .m_udp_payload_axis_tready(rx_udp_payload_axis_tready),
    .m_udp_payload_axis_tlast(rx_udp_payload_axis_tlast),
    .m_udp_payload_axis_tuser(rx_udp_payload_axis_tuser),
    // Status signals
    .ip_rx_busy(),
    .ip_tx_busy(),
    .udp_rx_busy(),
    .udp_tx_busy(),
    .ip_rx_error_header_early_termination(),
    .ip_rx_error_payload_early_termination(),
    .ip_rx_error_invalid_header(),
    .ip_rx_error_invalid_checksum(),
    .ip_tx_error_payload_early_termination(),
    .ip_tx_error_arp_failed(),
    .udp_rx_error_header_early_termination(),
    .udp_rx_error_payload_early_termination(),
    .udp_tx_error_payload_early_termination(),
    // Configuration
    .local_mac(local_mac),
    .local_ip(local_ip),
    .gateway_ip(gateway_ip),
    .subnet_mask(subnet_mask),
    .clear_arp_cache(0)
);

endmodule

`resetall
