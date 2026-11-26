// MappedSPIBus: un solo bus SPI (modo 0) para la flash y la RAM.
//
// SCK, MOSI y MISO son compartidos; cada memoria tiene su propio chip select.
// Un solo registro de desplazamiento de salida (shift_out) y uno de entrada (shift_in).
//
//   Lectura (flash o RAM):  CS=0, {03h, dirección}, 32 bits de dato, CS=1
//   Escritura (solo RAM):   CS=0, 06h (WREN), CS=1, CS=0, {02h, dirección}, 32 bits, CS=1
//
// Direcciones que se envían:
//   flash: 3 bytes, {mem_addr[23:2], 2'b00}
//   RAM:   2 bytes, {mem_addr[15:2], 2'b00}   (FM25V02: 32 KiB, dirección de 2 bytes)
// El dato viaja en little-endian (primero el byte 0), igual para leer y escribir.
//
// SCK tiene un periodo de 2*DIV ciclos de clk (DIV de 1 a 65535). MOSI cambia en el
// flanco de bajada de SCK y MISO se toma en el de subida. busy vale 1 desde el
// pedido hasta tener el dato.
// Para memorias lentas (por ejemplo, un emulador en un microcontrolador), CS_WAIT da
// tiempo en los dos extremos de cada trama, en unidades de medio periodo de SCK
// (DIV ciclos):
//   - después de bajar CS, el primer flanco de SCK llega CS_WAIT medios periodos después;
//   - al terminar, CS queda en alto CS_WAIT medios periodos antes de la siguiente trama.

module MappedSPIBus #(
    parameter DIV     = 2,               // medio periodo de SCK, en ciclos de clk
    parameter CS_WAIT = 1                // espera alrededor de cada trama (1 a 255)
) (
    input  wire        clk,
    input  wire        resetn,
    input  wire        rd,               // pulso: leer de la memoria elegida
    input  wire        wr,               // pulso: escribir en la RAM
    input  wire        cs_flash,         // destino: flash
    input  wire        cs_ram,           // destino: RAM
    input  wire [23:0] mem_addr,
    input  wire [31:0] mem_wdata,
    output wire [31:0] rdata,
    output reg         busy,

    output reg         spi_sck,
    output wire        spi_mosi,
    input  wire        spi_miso,
    output reg         spi_cs_flash_n,
    output reg         spi_cs_ram_n
);

localparam IDLE = 3'd0,   // espera un pedido
           WREN = 3'd1,   // envía 06h a la RAM
           GAP  = 3'd2,   // CS de la RAM en alto entre WREN y WRITE
           XFER = 3'd3,   // comando + dirección + dato
           DONE = 3'd4;   // CS en alto antes de aceptar otro pedido

reg [2:0]  state;
reg [31:0] shift_out;     // bits que salen por MOSI (el bit 31 primero)
reg [31:0] shift_in;      // bits que llegan por MISO
reg [31:0] wdata_reg;     // dato a escribir, con los bytes invertidos
reg [23:0] addr_reg;      // dirección de la RAM para la escritura
reg        is_write;
reg [5:0]  bit_cnt;       // bit actual de la trama
reg [5:0]  last_bit;      // último bit de la trama: 7 (WREN), 55 (RAM) o 63 (flash)
reg [5:0]  hdr_last;      // último bit de comando + dirección: 23 (RAM) o 31 (flash)
reg [15:0] div_cnt;
reg [7:0]  wait_cnt;      // medios periodos que faltan de la espera de CS_WAIT

wire tick = (div_cnt == DIV - 1);        // momento de cambiar SCK

assign spi_mosi = shift_out[31];
assign rdata    = {shift_in[7:0], shift_in[15:8], shift_in[23:16], shift_in[31:24]};

// Comando + dirección, alineados a la izquierda en 32 bits
wire [31:0] rd_header = cs_ram ? {8'h03, mem_addr[15:2], 2'b00, 8'h00}
                               : {8'h03, mem_addr[23:2], 2'b00};

always @(negedge clk) begin
    if (!resetn) begin
        state          <= IDLE;
        busy           <= 1'b0;
        spi_sck        <= 1'b0;
        spi_cs_flash_n <= 1'b1;
        spi_cs_ram_n   <= 1'b1;
        shift_out      <= 32'd0;
        div_cnt        <= 16'd0;
    end else begin
        div_cnt <= (state == IDLE || tick) ? 16'd0 : div_cnt + 16'd1;

        case (state)
        IDLE:
            if (rd || wr) begin
                busy      <= 1'b1;
                is_write  <= wr;
                addr_reg  <= {8'h00, mem_addr[15:2], 2'b00};   // solo se usa al escribir
                hdr_last  <= cs_ram ? 6'd23 : 6'd31;
                wdata_reg <= {mem_wdata[7:0], mem_wdata[15:8], mem_wdata[23:16], mem_wdata[31:24]};
                bit_cnt   <= 6'd0;
                wait_cnt  <= CS_WAIT - 1;
                if (wr) begin                          // escritura: primero WREN
                    shift_out    <= 32'h06000000;
                    last_bit     <= 6'd7;
                    spi_cs_ram_n <= 1'b0;
                    state        <= WREN;
                end else begin                         // lectura
                    shift_out      <= rd_header;
                    last_bit       <= cs_ram ? 6'd55 : 6'd63;
                    spi_cs_flash_n <= ~cs_flash;
                    spi_cs_ram_n   <= ~cs_ram;
                    state          <= XFER;
                end
            end

        WREN, XFER:
            if (tick) begin
                if (wait_cnt != 0) begin               // espera después de bajar CS
                    wait_cnt <= wait_cnt - 8'd1;
                end else if (!spi_sck) begin           // flanco de subida: toma MISO
                    spi_sck  <= 1'b1;
                    shift_in <= {shift_in[30:0], spi_miso};
                end else begin                         // flanco de bajada
                    spi_sck <= 1'b0;
                    if (bit_cnt == last_bit) begin     // fin de la trama
                        spi_cs_flash_n <= 1'b1;
                        spi_cs_ram_n   <= 1'b1;
                        wait_cnt       <= CS_WAIT - 1;
                        state <= (state == WREN) ? GAP : DONE;
                    end else begin
                        bit_cnt   <= bit_cnt + 6'd1;
                        shift_out <= (bit_cnt == hdr_last) ? (is_write ? wdata_reg : 32'd0)
                                                        : {shift_out[30:0], 1'b0};
                    end
                end
            end

        DONE:                                          // CS alto CS_WAIT medios periodos
            if (tick) begin
                if (wait_cnt != 0) wait_cnt <= wait_cnt - 8'd1;
                else begin
                    busy  <= 1'b0;
                    state <= IDLE;
                end
            end

        GAP:                                           // CS alto CS_WAIT medios periodos
            if (tick) begin
              if (wait_cnt != 0) wait_cnt <= wait_cnt - 8'd1;
              else begin
                shift_out    <= {8'h02, addr_reg[15:0], 8'h00};
                bit_cnt      <= 6'd0;
                last_bit     <= 6'd55;
                spi_cs_ram_n <= 1'b0;
                wait_cnt     <= CS_WAIT - 1;
                state        <= XFER;
              end
            end
        endcase
    end
end

endmodule
