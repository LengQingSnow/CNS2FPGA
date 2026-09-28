`timescale 1ns/1ps

module IOBUF(input wire I, input wire T, output wire O, inout wire IO);
    assign IO = T ? 1'bz : I;
    assign O = IO;
endmodule

module tb_mdio_diag;
    reg clk = 0;
    always #2.5 clk = ~clk;
    reg rst = 1;
    reg start = 0;
    reg write_mode = 0;
    reg [4:0] phy_addr = 5'd3;
    reg [4:0] reg_addr = 5'd2;
    reg [15:0] write_data = 16'h4000;
    wire mdc;
    tri1 mdio;
    wire [31:0] status;
    wire [31:0] result;
    reg [15:0] reply = 16'h0022;
    assign mdio = dut.busy && !dut.operation_write && dut.bit_index == 16 ? 1'b0 :
                  dut.busy && !dut.operation_write && dut.bit_index < 16 ?
                  reply[dut.bit_index] : 1'bz;

    cns2fpga_mdio_diag dut (
        .clk(clk), .rst(rst), .start(start), .write_mode(write_mode),
        .phy_addr(phy_addr), .reg_addr(reg_addr), .write_data(write_data),
        .mdc(mdc), .mdio(mdio), .status(status), .result(result)
    );

    initial begin
        repeat (8) @(posedge clk);
        rst = 0;
        @(negedge clk); start = 1;
        @(negedge clk); start = 0;
        wait (status[1]);
        if (status[2] || result[15:0] !== 16'h0022 ||
            status[12:8] !== 5'd3 || status[7:3] !== 5'd2)
            $fatal(1, "MDIO_READ_FAIL status=%h result=%h", status, result);
        write_mode = 1;
        reg_addr = 0;
        @(negedge clk); start = 1;
        @(negedge clk); start = 0;
        wait (status[0]);
        wait (status[1]);
        if (status[2] || dut.frame[15:0] !== 16'h4000)
            $fatal(1, "MDIO_WRITE_FAIL status=%h frame=%h", status, dut.frame);
        $display("MDIO_DIAG_PASS read=%h write=%h", result[15:0], dut.frame[15:0]);
        $finish;
    end
endmodule
