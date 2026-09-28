`timescale 1ns/1ps

// One command at a time from the 125 MHz UDP domain into the 200 MHz engine.
// The source holds address/data until ack_toggle returns; only the request and
// acknowledge toggles are synchronized. JTAG and Ethernet must not issue
// simultaneous transactions.
module cns2fpga_eth_bus_bridge (
    input  wire        clk,
    input  wire        rst,
    input  wire        req_toggle,
    input  wire        req_read,
    input  wire [19:0] req_addr,
    input  wire [31:0] req_data,
    output reg         ack_toggle = 0,
    output reg  [31:0] read_data = 0,
    input  wire        jtag_activity,
    output reg         bus_wr_en = 0,
    output reg  [19:0] bus_wr_addr = 0,
    output reg  [31:0] bus_wr_data = 0,
    output reg         bus_rd_en = 0,
    output reg  [19:0] bus_rd_addr = 0,
    input  wire [31:0] bus_rd_data,
    input  wire        bus_rd_valid
);
    localparam S_IDLE=0, S_WRITE_ACK=1, S_READ_WAIT=2;
    reg [1:0] state = S_IDLE;
    (* ASYNC_REG = "TRUE" *) reg [2:0] request_sync = 0;
    reg seen_toggle = 0;

    always @(posedge clk) begin
        request_sync <= {request_sync[1:0], req_toggle};
        bus_wr_en <= 0;
        bus_rd_en <= 0;
        if (rst) begin
            state <= S_IDLE;
            seen_toggle <= 0;
            ack_toggle <= 0;
            read_data <= 0;
        end else begin
            case (state)
                S_IDLE: if (request_sync[2] != seen_toggle && !jtag_activity) begin
                    seen_toggle <= request_sync[2];
                    if (req_read) begin
                        bus_rd_addr <= req_addr;
                        bus_rd_en <= 1;
                        state <= S_READ_WAIT;
                    end else begin
                        bus_wr_addr <= req_addr;
                        bus_wr_data <= req_data;
                        bus_wr_en <= 1;
                        state <= S_WRITE_ACK;
                    end
                end
                S_WRITE_ACK: begin
                    ack_toggle <= seen_toggle;
                    state <= S_IDLE;
                end
                S_READ_WAIT: if (bus_rd_valid) begin
                    read_data <= bus_rd_data;
                    ack_toggle <= seen_toggle;
                    state <= S_IDLE;
                end
                default: state <= S_IDLE;
            endcase
        end
    end
endmodule
