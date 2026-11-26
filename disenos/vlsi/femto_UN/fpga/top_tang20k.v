// top_tang20k: femto_UN (tt_um_femto) en la Sipeed Tang Primer 20K Dock.
//
// Reloj: 27 MHz de la tarjeta (H11) -> PLL -> 24 MHz, el mismo reloj de la simulación.
//        Con 24 MHz la UART del diseño trabaja a 115200 baud.
// Reset: al configurar la FPGA y con el botón S0 (sin rebotes: el reset termina ~22 ms
//        después de soltar el botón).
// IRQ:   botón S1, con antirrebote (~10 ms).
// Bus SPI único (SCK, MOSI, MISO) para la flash (ESP32-C6) y la RAM (FM25V02),
// con un chip select para cada una. SCK = 24 MHz / (2*SPI_DIV).
// UART 115200 8N1 por el FTDI y por el USB del Dock.
// LEDs del Dock (activos en bajo): 0 LED del femto, 1 latido, 2 acceso a la RAM,
// 3 acceso a la flash.

module top_tang20k #(
    parameter SPI_DIV  = 400,      // SCK = 30 kHz, velocidad que alcanza el ESP32-C6
    parameter CS_WAIT  = 6,        // ~100 µs con CS quieto antes y después de cada trama
    parameter POR_BITS = 20,       // reset al encender: 2^(POR_BITS-1) ciclos (~22 ms)
    parameter DEB_BITS = 18        // antirrebote de S1: 2^DEB_BITS ciclos (~11 ms)
) (
    input  wire       clk27,
    input  wire       btn_rst_n,   // S0 (activo en bajo)
    input  wire       btn_irq_n,   // S1 (activo en bajo)

    output wire       ftdi_tx,     // al RX del FTDI
    input  wire       ftdi_rx,     // del TX del FTDI
    output wire       uart_tx,     // USB del Dock
    input  wire       uart_rx,

    output wire       spi_sck,     // bus SPI compartido
    output wire       spi_mosi,
    input  wire       spi_miso,
    output wire       flash_cs_n,  // ESP32-C6
    output wire       ram_cs_n,    // FM25V02

    output wire [3:0] led_n
);

    // ------------------------------------------------------------ reloj de 24 MHz
    // CLKOUT = 27 MHz * (FBDIV_SEL+1) / (IDIV_SEL+1) = 27 * 8 / 9 = 24 MHz
    // VCO    = CLKOUT * ODIV_SEL = 768 MHz
    wire clk, pll_lock;
    rPLL #(
        .FCLKIN   ("27"),
        .IDIV_SEL (8),
        .FBDIV_SEL(7),
        .ODIV_SEL (32),
        .DEVICE   ("GW2A-18C")
    ) pll (
        .CLKIN   (clk27),
        .CLKOUT  (clk),
        .LOCK    (pll_lock),
        .CLKOUTP (),
        .CLKOUTD (),
        .CLKOUTD3(),
        .RESET   (1'b0),
        .RESET_P (1'b0),
        .CLKFB   (1'b0),
        .FBDSEL  (6'b000000),
        .IDSEL   (6'b000000),
        .ODSEL   (6'b000000),
        .PSDA    (4'b0000),
        .DUTYDA  (4'b0000),
        .FDLY    (4'b0000)
    );

    // ------------------------------------------------------------ reset
    // Mientras el PLL no esté listo o S0 esté presionado, el contador vuelve a 0; el
    // reset termina cuando el contador llega a su bit más alto. Así los rebotes de S0
    // producen un solo reset.
    reg [1:0] rst_sync = 2'b00;    // el botón se sincroniza con el reloj
    always @(posedge clk) rst_sync <= {rst_sync[0], btn_rst_n};

    reg [POR_BITS-1:0] por = 0;
    always @(posedge clk)
        if (!pll_lock || !rst_sync[1]) por <= 0;
        else if (!por[POR_BITS-1])     por <= por + 1'b1;

    wire rst_n = por[POR_BITS-1];

    // ------------------------------------------------------------ S1 sin rebotes
    // irq_btn solo cambia cuando el botón lleva 2^DEB_BITS ciclos estable.
    reg [1:0]          irq_s   = 2'b11;
    reg [DEB_BITS-1:0] deb     = 0;
    reg                irq_btn = 1'b0;        // 1 = presionado
    always @(posedge clk) begin
        irq_s <= {irq_s[0], btn_irq_n};
        if ((~irq_s[1]) == irq_btn)
            deb <= 0;
        else if (&deb)
            irq_btn <= ~irq_s[1];
        else
            deb <= deb + 1'b1;
    end

    // ------------------------------------------------------------ procesador
    wire [7:0] uo_out;
    wire [7:0] uio_out, uio_oe;
    wire       rxd = ftdi_rx & uart_rx;       // los dos están en 1 en reposo

    tt_um_femto #(.SPI_DIV(SPI_DIV), .SPI_CS_WAIT(CS_WAIT)) femto (
        .ui_in  ({4'b0000, irq_btn, rxd, 1'b0, spi_miso}),
        .uo_out (uo_out),
        .uio_in (8'h00),
        .uio_out(uio_out),
        .uio_oe (uio_oe),
        .ena    (1'b1),
        .clk    (clk),
        .rst_n  (rst_n)
    );

    assign spi_mosi   = uo_out[0];
    assign flash_cs_n = uo_out[2];
    assign ram_cs_n   = uo_out[3];
    assign spi_sck    = uo_out[5];
    wire   led_femto  = uo_out[6];
    assign uart_tx    = uo_out[7];
    assign ftdi_tx    = uo_out[7];

    // ------------------------------------------------------------ LEDs
    reg [23:0] beat = 0;
    always @(posedge clk) beat <= beat + 1'b1;

    reg [21:0] ram_act = 0, flash_act = 0;    // alargan cada acceso ~0.2 s
    always @(posedge clk) begin
        ram_act   <= !ram_cs_n   ? {22{1'b1}} : (ram_act   != 0 ? ram_act   - 1'b1 : 22'd0);
        flash_act <= !flash_cs_n ? {22{1'b1}} : (flash_act != 0 ? flash_act - 1'b1 : 22'd0);
    end

    assign led_n = ~{flash_act != 0, ram_act != 0, beat[23], led_femto};

endmodule
