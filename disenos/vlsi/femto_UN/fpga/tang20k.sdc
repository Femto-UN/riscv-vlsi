// Reloj de 27 MHz de la tarjeta (el PLL deriva el de 24 MHz)
create_clock -name clk27 -period 37.037 [get_ports {clk27}]
