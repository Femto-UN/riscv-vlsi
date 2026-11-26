# Bus SPI único e interrupciones — femto_UN v2

Esta versión del procesador reemplaza los dos buses SPI independientes (uno para la flash y otro para la RAM) por un solo bus compartido con un chip select por memoria. Además corrige la atención de interrupciones y la generación de pulsos de la UART. Los cambios se verificaron en simulación con cocotb y en una FPGA Tang Primer 20K.

## Archivos modificados

| Archivo | Estado | Cambio |
|---|---|---|
| `femto_UN/src/MappedSPIBus.v` | Nuevo | Controlador del bus SPI único (SCK, MOSI y MISO compartidos; `cs_flash` y `cs_ram`) |
| `femto_UN/src/femto.v` | Modificado | Instancia `MappedSPIBus` en lugar de `MappedSPIFlash` y `MappedSPIRAM`; agrega los parámetros `SPI_DIV` y `SPI_CS_WAIT`; libera los pines `uo1`, `uo4` y `ui1` |
| `femto_UN/src/femtorv32_quark_un_irq.v` | Modificado | La IRQ se sincroniza con el reloj y se atiende por flanco de subida |
| `femto_UN/src/perip_uart.v` | Modificado | `tx_wr` y `rx_ack` duran un solo ciclo de reloj |
| `tinytapeout/Makefile` | Modificado | Incluye `MappedSPIBus.v` en la compilación |
| `tinytapeout/tt_um_femto_cocotb.v` | Modificado | Conexiones del bus único, IRQ, LED y modelo de memoria |
| `tinytapeout/test_tt_um_femto.py` | Modificado | Suite de 10 pruebas cocotb |

`MappedSPIFlash.v` y `MappedSPIRAM.v` se conservan en el repositorio, pero esta versión ya no los usa.

## Bus SPI único (`MappedSPIBus.v`)

- **Señales:** SCK, MOSI y MISO compartidos; un CS para la flash y otro para la RAM. Modo SPI 0.
- **Lectura (flash o RAM):** comando `03h` + dirección + 32 bits de dato.
- **Escritura (solo RAM):** comando `06h` (WREN) en una trama propia, CS en alto y luego `02h` + dirección + 32 bits de dato.
- **Dirección:** 3 bytes para la flash y 2 bytes para la RAM (FM25V02).
- **Orden de datos:** little-endian, como lo espera el núcleo femtorv.
- **`SPI_DIV`:** divisor del reloj del sistema para generar SCK.
- **`SPI_CS_WAIT`:** ciclos de espera con CS activo antes y después de cada trama. Dan margen a dispositivos lentos, como un microcontrolador que emula la flash.
- **Estado `DONE`:** obliga a que el CS permanezca en alto un tiempo mínimo entre tramas consecutivas.
- **MISO compartido:** cada dispositivo debe poner su MISO en alta impedancia mientras su CS esté en alto.

## Interrupciones

La entrada de IRQ se sincroniza con el reloj del sistema y el núcleo la atiende en el flanco de subida. Así, una señal que se mantiene en alto genera una sola interrupción y no varias seguidas.

## UART

`tx_wr` y `rx_ack` pasaron de ser niveles a pulsos de un ciclo. Con el bus SPI a baja velocidad, el nivel permanecía activo varios ciclos y cada byte se transmitía repetido.

## Verificación

```bash
source ~/venvs/cocotb/bin/activate
cd disenos/vlsi/tinytapeout
make cocotb
```

Resultado: **10/10 pruebas aprobadas** (Icarus Verilog 12, cocotb 2, reloj de 24 MHz).

| # | Prueba | Qué verifica |
|---|---|---|
| 1 | `execute_lui_from_cocotb_spi_flash` | Arranque y primera instrucción leída de la flash |
| 2 | `test_hello_world` | Una letra por registro (x10–x31), la frase escrita en la RAM y enviada por la UART |
| 3 | `test_alu` | Operaciones aritméticas y lógicas |
| 4 | `test_saltos` | Saltos y ramificaciones |
| 5 | `test_cargas_flash` | Cargas de datos desde la flash |
| 6 | `test_ram` | Lectura y escritura en la RAM, incluida la última palabra (0x7FFC), con la secuencia WREN + WRITE |
| 7 | `test_uart_tx` | Transmisión por la UART |
| 8 | `test_uart_rx` | Recepción por la UART, almacenamiento en la RAM y retransmisión |
| 9 | `test_interrupcion` | Atención de la IRQ por flanco |
| 10 | `test_programa_fpga` | Ejecuta el programa de la prueba en FPGA y genera `build/cocotb/programa_fpga.bin` |

En todas las pruebas se revisa además que:
- los dos CS nunca estén activos al mismo tiempo;
- el CS permanezca en alto al menos `SPI_DIV` ciclos entre tramas.

## Limitaciones

- El chip fabricado (TTSKY25b) y la placa tester mantienen la arquitectura de dos buses. El bus único corresponde a la siguiente versión del procesador.
- El testbench en Verilog (`make sim`) compila, pero su modelo de RAM sigue conectado a los pines anteriores.
- La prueba en hardware (Tang Primer 20K con ESP32-C6 como flash, FM25V02 como RAM y UART por FTDI) se documenta por separado.
