`timescale 1ns/1ps

module tt_um_femto_cocotb (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        uart_rx,
    output wire        uart_tx,
    input  wire        irq,
    output wire        led,
    input  wire        spi_miso,      // bus SPI compartido
    output wire        spi_mosi,
    output wire        spi_sck,
    output wire        flash_cs_n,    // CS de la flash
    output wire        ram_cs_n,      // CS de la RAM
    output wire [31:0] debug_x6,
    output wire [23:0] debug_pc,
    output wire [31:0] debug_flash_rdata,
    output wire [31:0] debug_flash_raw,
    output wire [29:0] debug_instr
);

wire [7:0] ui_in;
wire [7:0] uo_out;
wire [7:0] uio_out;
wire [7:0] uio_oe;

assign ui_in = {4'b0000, irq, uart_rx, 1'b0, spi_miso};
assign spi_mosi = uo_out[0];
assign flash_cs_n = uo_out[2];
assign ram_cs_n = uo_out[3];
assign spi_sck = uo_out[5];
assign led = uo_out[6];
assign uart_tx = uo_out[7];
assign debug_x6 = dut.femto0.CPU.registerFile[6];
assign debug_pc = dut.femto0.CPU.PC;
assign debug_flash_rdata = dut.femto0.spi_rdata;
assign debug_flash_raw = dut.femto0.mapped_spi.shift_in;
assign debug_instr = dut.femto0.CPU.instr;

tt_um_femto dut (
    .ui_in(ui_in),
    .uo_out(uo_out),
    .uio_in(8'h00),
    .uio_out(uio_out),
    .uio_oe(uio_oe),
    .ena(1'b1),
    .clk(clk),
    .rst_n(rst_n)
);

// Copia de los primeros 64 bytes de la RAM simulada en cocotb, para verlos en GTKWave
// (mismo nombre que la RAM del testbench tt_um_femto_TB.v: flashram0.mem).
ram_view flashram0();

// Archivo de ondas con las mismas señales que guarda tt_um_femto_TB.v
integer idx;
initial begin
    $dumpfile("build/cocotb/tt_um_femto_cocotb.vcd");
    $dumpvars(0, dut);
    for (idx = 0; idx < 32; idx = idx + 1) $dumpvars(0, dut.femto0.CPU.registerFile[idx]);
    for (idx = 0; idx < 64; idx = idx + 1) $dumpvars(0, flashram0.mem[idx]);
end

endmodule

// Memoria que solo sirve para mostrar en GTKWave el contenido de la RAM simulada.
// La prueba de cocotb escribe aquí cada byte que guarda en la RAM.
module ram_view;
reg [7:0] mem [0:63];
integer i;
initial for (i = 0; i < 64; i = i + 1) mem[i] = 8'h00;
endmodule
