# Gowin (gw_sh): síntesis, place & route y bitstream de femto_UN para la Tang Primer 20K.
# Se corre desde femto_UN/fpga con:  make bitstream
# Resultado: build/femto_tang20k/impl/pnr/femto_tang20k.fs

set here [pwd]
set src  [file normalize $here/../src]

create_project -name femto_tang20k -dir $here/build -pn GW2A-LV18PG256C8/I7 -device_version C -force

foreach f {femto.v femtorv32_quark_un_irq.v MappedSPIBus.v perip_uart.v uart.v} {
    add_file -type verilog $src/$f
}
add_file -type verilog $here/top_tang20k.v
add_file -type cst     $here/tang20k.cst
add_file -type sdc     $here/tang20k.sdc

set_option -top_module top_tang20k
set_option -verilog_std sysv2017

# Pines de doble función usados como E/S normales (T10 es del MSPI)
set_option -use_mspi_as_gpio 1
set_option -use_sspi_as_gpio 1
set_option -use_ready_as_gpio 1
set_option -use_done_as_gpio 1

run all
