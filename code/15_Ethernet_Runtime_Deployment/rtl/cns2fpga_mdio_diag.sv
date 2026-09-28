`timescale 1ns/1ps

// JTAG-controlled Clause 22 MDIO master. One transaction at a time, 1 MHz MDC.
module cns2fpga_mdio_diag (
    input  wire clk,
    input  wire rst,
    input  wire start,
    input  wire write_mode,
    input  wire [4:0] phy_addr,
    input  wire [4:0] reg_addr,
    input  wire [15:0] write_data,
    output reg  mdc = 0,
    inout  wire mdio,
    output wire [31:0] status,
    output wire [31:0] result
);
    reg [63:0] frame = 0;
    reg [5:0] bit_index = 0;
    reg [6:0] half_period = 0;
    reg busy = 0;
    reg done = 0;
    reg ta_error = 0;
    reg operation_write = 0;
    reg [4:0] selected_phy = 0;
    reg [4:0] selected_reg = 0;
    reg [15:0] read_data = 0;
    wire mdio_input;
    wire drive_enable = busy && (operation_write || bit_index > 17);
    IOBUF mdio_buffer (
        .I(frame[bit_index]), .T(~drive_enable), .O(mdio_input), .IO(mdio)
    );
    assign status = {19'd0, selected_phy, selected_reg, ta_error, done, busy};
    assign result = {16'd0, read_data};

    always @(posedge clk) begin
        if (rst) begin
            frame <= 0;
            bit_index <= 0;
            half_period <= 0;
            mdc <= 0;
            busy <= 0;
            done <= 0;
            ta_error <= 0;
            operation_write <= 0;
            selected_phy <= 0;
            selected_reg <= 0;
            read_data <= 0;
        end else if (start && !busy) begin
            frame <= {32'hffff_ffff, 2'b01, write_mode ? 2'b01 : 2'b10,
                      phy_addr, reg_addr, write_mode ? 2'b10 : 2'b11,
                      write_mode ? write_data : 16'hffff};
            bit_index <= 63;
            half_period <= 0;
            mdc <= 0;
            busy <= 1;
            done <= 0;
            ta_error <= 0;
            operation_write <= write_mode;
            selected_phy <= phy_addr;
            selected_reg <= reg_addr;
            read_data <= 0;
        end else if (busy) begin
            if (half_period == 99) begin
                half_period <= 0;
                if (!mdc) begin
                    mdc <= 1;
                    if (!operation_write) begin
                        if (bit_index == 16) ta_error <= mdio_input;
                        if (bit_index < 16) read_data[bit_index] <= mdio_input;
                    end
                    if (bit_index == 0) begin
                        busy <= 0;
                        done <= 1;
                    end
                end else begin
                    mdc <= 0;
                    bit_index <= bit_index - 1'b1;
                end
            end else begin
                half_period <= half_period + 1'b1;
            end
        end else begin
            mdc <= 0;
        end
    end
endmodule
