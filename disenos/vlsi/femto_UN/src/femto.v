/* verilator lint_off SYNCASYNCNET */
module tt_um_femto #(
    parameter SPI_DIV     = 2,       // SCK = clk / (2*SPI_DIV)
    parameter SPI_CS_WAIT = 1        // espera alrededor de cada trama SPI (medios periodos)
)(
    input  wire [7:0] ui_in,    // Dedicated inputs
    output wire [7:0] uo_out,   // Dedicated outputs
    input  wire [7:0] uio_in,   // IOs: Input path
    output wire [7:0] uio_out,  // IOs: Output path
    output wire [7:0] uio_oe,   // IOs: Enable path (active high: 0=input, 1=output)
    input  wire       ena,      // always 1 when the design is powered, so you can ignore it
    input  wire       clk,      // clock
    input  wire       rst_n     // reset_n - low to reset
);

  // Register the reset on the negative edge of clock for safety.
  // This also allows the option of async reset in the design, which might be preferable in some cases
  
  reg resetn;
  /* verilator lint_on SYNCASYNCNET */
  always @(negedge clk) resetn <= rst_n;
  /* verilator lint_off UNDRIVEN */
	
	femto #(.SPI_DIV(SPI_DIV), .SPI_CS_WAIT(SPI_CS_WAIT)) femto0( 
		.clk          (clk), 
		.resetn       (resetn), 
		.spi_mosi     (uo_out[0]),     // bus SPI compartido por la flash y la RAM
		.spi_cs_n     (uo_out[2]),     // CS de la flash
		.spi_cs_n_ram (uo_out[3]),     // CS de la RAM
		.spi_clk      (uo_out[5]),
		.LEDS         (uo_out[6]),
		.TXD          (uo_out[7]),
		
		.spi_miso     (ui_in[0]),
		.RXD          (ui_in[2]),
      .interrupt_request (ui_in[3])

		
	);
	
	assign uo_out[1] = 1'b0;         // libres con el bus único
	assign uo_out[4] = 1'b0;
	wire _unused = &{ena, uio_oe[7:0] , uio_in[7:0], uio_out[7:0], ui_in[7:4], ui_in[1], 1'b0};
	assign uio_out = 8'h00;
	assign uio_oe = 8'h00;
	
/* verilator lint_on UNDRIVEN */
endmodule

module femto #(
   parameter SPI_DIV     = 2,        // SCK = clk / (2*SPI_DIV)
   parameter SPI_CS_WAIT = 1         // espera alrededor de cada trama SPI (medios periodos)
) (
   input 	     clk,    // system clock 
   input 	     resetn, // reset button
   input         interrupt_request,

   // Bus SPI único: SCK, MOSI y MISO compartidos, un CS por memoria
   output        spi_mosi,
   input         spi_miso,
   output        spi_clk,
   output        spi_cs_n,         // CS de la flash, activo en bajo
   output        spi_cs_n_ram,     // CS de la RAM, activo en bajo

   output        wire LEDS,   // system LEDs
   input 	     RXD,    // UART receive
   output 	     TXD     // UART transmit
);
   wire [31:0] mem_address;
   reg  [31:0] mem_rdata;
   wire mem_rstrb;
   wire  [31:0] mem_wdata;
   wire [3:0]  mem_wmask;
   wire spi_busy;                    // bus SPI ocupado (lectura o escritura)

   FemtoRV32 CPU(
      .clk(clk),
      .reset(resetn),		 
      .mem_addr(mem_address),
      .mem_rdata(mem_rdata),
      .mem_rstrb(mem_rstrb),
      .mem_wdata(mem_wdata),
      .mem_wmask(mem_wmask),
      .mem_rbusy(spi_busy),
      .mem_wbusy(spi_busy),
      .interrupt_request(interrupt_request)
   );
   wire  wr = |mem_wmask;
   wire  rd = mem_rstrb; 
   wire [31:0] spi_rdata;

   // Flash (cs[0]) y RAM (cs[6]) en el mismo bus SPI
   MappedSPIBus #(.DIV(SPI_DIV), .CS_WAIT(SPI_CS_WAIT)) mapped_spi(
      .clk(clk),
      .resetn(resetn),
      .rd((cs[0] | cs[6]) & rd),
      .wr(cs[6] & wr),
      .cs_flash(cs[0]),
      .cs_ram(cs[6]),
      .mem_addr(mem_address[23:0]),
      .mem_wdata(mem_wdata),
      .rdata(spi_rdata),
      .busy(spi_busy),
      .spi_sck(spi_clk),
      .spi_mosi(spi_mosi),
      .spi_miso(spi_miso),
      .spi_cs_flash_n(spi_cs_n),
      .spi_cs_ram_n(spi_cs_n_ram)
   );

   wire [31:0] uart_dout;

  peripheral_uart #(
     .clk_freq(27000000),    // 27000000 for gowin
     .baud(115200)            // 57600 for gowin
   ) per_uart(
     .clk(clk), 
     .rst(!resetn), 
     .d_in(mem_wdata[7:0]), 
     .cs(cs[5]), 
     .addr(mem_address[4:0]), 
     .wr(wr), 
     .d_out(uart_dout), 
     .uart_tx(TXD), 
     .uart_rx(RXD), 
     .ledout(LEDS)
   ); 

  // ============== Chip_Select (Addres decoder) ======================== 
  // se hace con los 8 bits mas significativos de mem_addr
  // Se asigna el rango de la memoria de programa 0x00000000 - 0x003FFFFF
  // ====================================================================
  reg [6:0]cs;  // CHIP-SELECT
  always @*
  begin
      case (mem_address[31:16])	// direcciones - chip_select
        16'h0000: cs= 7'b0000001; 	//RAM
        16'h0040: cs= 7'b0100000; 	//uart
//        16'h0041: cs= 7'b0010000;	//gpio
//        16'h0042: cs= 7'b0001000;	//mult
//        16'h0043: cs= 7'b0000100;	//div
//        16'h0044: cs= 7'b0000010;	//bin_to_bcd
        16'h0001: cs= 7'b1000000;   //dpRAM
        default: cs= 7'b0000001;
      endcase
  end
  // ============== MUX ========================  // se encarga de lecturas del RV32
  always @*
  begin
      case (cs)
        7'b1000000: mem_rdata = spi_rdata;
        7'b0100000: mem_rdata = uart_dout;
//        7'b0010000: mem_rdata = gpio_dout;
//        7'b0001000: mem_rdata = mult_dout;
//        7'b0000100: mem_rdata = div_dout;
//        7'b0000010: mem_rdata = bin2bcd_dout;
        7'b0000001: mem_rdata = spi_rdata;
        default:    mem_rdata = 32'h00000000;
      endcase
  end
 // ============== MUX ========================  // 

`ifdef BENCH
   always @(posedge clk) begin
      if(cs[5] & wr ) begin
	 $write("%c", mem_wdata[7:0] );
	 $fflush(32'h8000_0001);
      end
   end
`endif

endmodule
