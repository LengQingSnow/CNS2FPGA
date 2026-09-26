`timescale 1ns/1ps

// Single-outstanding AXI4-Lite adapter for the synchronous trial-engine bus.
// AW and W may arrive in either order. B is returned only after the engine
// has accepted the write. Read response waits for bus_rd_valid.
module cns2fpga_axi_lite_slave (
    input  wire        clk,
    input  wire        rst,
    input  wire        write_blocked,
    input  wire [31:0] s_axi_awaddr,
    input  wire        s_axi_awvalid,
    output wire        s_axi_awready,
    input  wire [31:0] s_axi_wdata,
    input  wire [3:0]  s_axi_wstrb,
    input  wire        s_axi_wvalid,
    output wire        s_axi_wready,
    output reg  [1:0]  s_axi_bresp,
    output reg         s_axi_bvalid,
    input  wire        s_axi_bready,
    input  wire [31:0] s_axi_araddr,
    input  wire        s_axi_arvalid,
    output wire        s_axi_arready,
    output reg  [31:0] s_axi_rdata,
    output reg  [1:0]  s_axi_rresp,
    output reg         s_axi_rvalid,
    input  wire        s_axi_rready,
    output wire        bus_wr_en,
    output wire [19:0] bus_wr_addr,
    output wire [31:0] bus_wr_data,
    output wire [3:0]  bus_wr_strb,
    output reg         bus_rd_en,
    output reg  [19:0] bus_rd_addr,
    input  wire [31:0] bus_rd_data,
    input  wire        bus_rd_valid
);
    reg have_aw;
    reg have_w;
    reg [31:0] awaddr_hold;
    reg [31:0] wdata_hold;
    reg [3:0] wstrb_hold;
    reg read_waiting;
    reg read_invalid;

    assign s_axi_awready = !have_aw && !s_axi_bvalid;
    assign s_axi_wready = !have_w && !s_axi_bvalid;
    assign s_axi_arready = !read_waiting && !s_axi_rvalid;
    assign bus_wr_en = have_aw && have_w && !s_axi_bvalid && !write_blocked &&
                       (awaddr_hold[31:20] == 12'd0) && (wstrb_hold == 4'hf);
    assign bus_wr_addr = awaddr_hold[19:0];
    assign bus_wr_data = wdata_hold;
    assign bus_wr_strb = wstrb_hold;

    always @(posedge clk) begin
        bus_rd_en <= 1'b0;
        if (rst) begin
            have_aw <= 1'b0;
            have_w <= 1'b0;
            awaddr_hold <= 32'd0;
            wdata_hold <= 32'd0;
            wstrb_hold <= 4'd0;
            s_axi_bresp <= 2'b00;
            s_axi_bvalid <= 1'b0;
            bus_rd_addr <= 20'd0;
            read_waiting <= 1'b0;
            read_invalid <= 1'b0;
            s_axi_rdata <= 32'd0;
            s_axi_rresp <= 2'b00;
            s_axi_rvalid <= 1'b0;
        end else begin
            if (s_axi_awvalid && s_axi_awready) begin
                awaddr_hold <= s_axi_awaddr;
                have_aw <= 1'b1;
            end
            if (s_axi_wvalid && s_axi_wready) begin
                wdata_hold <= s_axi_wdata;
                wstrb_hold <= s_axi_wstrb;
                have_w <= 1'b1;
            end
            if (have_aw && have_w && !s_axi_bvalid) begin
                s_axi_bvalid <= 1'b1;
                s_axi_bresp <= (write_blocked || awaddr_hold[31:20] != 12'd0 ||
                                wstrb_hold != 4'hf) ? 2'b10 : 2'b00;
                have_aw <= 1'b0;
                have_w <= 1'b0;
            end else if (s_axi_bvalid && s_axi_bready) begin
                s_axi_bvalid <= 1'b0;
            end
            if (s_axi_arvalid && s_axi_arready) begin
                read_waiting <= 1'b1;
                read_invalid <= s_axi_araddr[31:20] != 12'd0;
                bus_rd_addr <= s_axi_araddr[19:0];
                if (s_axi_araddr[31:20] == 12'd0)
                    bus_rd_en <= 1'b1;
            end
            if (read_waiting && !s_axi_rvalid && (read_invalid || bus_rd_valid)) begin
                s_axi_rdata <= read_invalid ? 32'd0 : bus_rd_data;
                s_axi_rresp <= read_invalid ? 2'b10 : 2'b00;
                s_axi_rvalid <= 1'b1;
                read_waiting <= 1'b0;
            end else if (s_axi_rvalid && s_axi_rready) begin
                s_axi_rvalid <= 1'b0;
            end
        end
    end
endmodule
