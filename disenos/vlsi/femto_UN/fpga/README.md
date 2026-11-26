# femto_UN en la Tang Primer 20K Dock

El procesador de `femto_UN/src` corre en la FPGA con el bus SPI único:
- la flash es un ESP32-C6 que la emula;
- la RAM es una FM25V02;
- la UART sale por un FTDI.

## Archivos

| Archivo | Contenido |
|---|---|
| `top_tang20k.v` | PLL de 27 a 24 MHz, reset (S0), IRQ con antirrebote (S1), `tt_um_femto` y LEDs |
| `tang20k.cst` | Pines |
| `tang20k.sdc` | Reloj de 27 MHz |
| `build.tcl`, `Makefile` | Bitstream con Gowin (`make bitstream`) y carga (`make prog`) |
| `bin2h.py` | Convierte el programa `.bin` en `firmware.h` para el ESP32 |
| `esp32_flash_emu/` | Emulador de flash para el ESP32-C6 y el programa de prueba (`firmware.h`) |

## Conexiones

Todo el bus va en el **PMOD0** del Dock, el que está bajo "MIC ARRAY". GND es común a la Tang, el ESP32, la RAM y el FTDI.

| Señal | Pin FPGA | ESP32-C6 (flash) | FM25V02 (RAM) | FTDI |
|---|---|---|---|---|
| spi_sck | T7 | GPIO6 (SCK) | pin 6 (C) | |
| spi_mosi | T8 | GPIO5 (MOSI) | pin 5 (D) | |
| spi_miso | P9 | GPIO4 (MISO) | pin 2 (Q) | |
| flash_cs_n | P8 | GPIO7 (CS) | | |
| ram_cs_n | T6 | | pin 1 (/S) | |
| ftdi_tx | P6 | | | RX |
| ftdi_rx | R8 | | | TX |
| 3V3 | 3V3 del PMOD | | pin 8 (VDD), pin 3 (/W), pin 7 (/HOLD) | |
| GND | GND del PMOD | GND | pin 4 (VSS) | GND |

- **Condensador de la RAM:** 100 nF entre el pin 8 (VDD) y el pin 4 (VSS), lo más cerca posible del chip.
- **MISO compartido:** el cable MISO es uno solo, al que se conectan el ESP32, la RAM y la FPGA. Cada memoria solo lo maneja mientras su CS está en bajo.
- **Alimentación:** el ESP32 se alimenta por su USB y el FTDI por el suyo; solo se unen las tierras.

**Botones:**
- S0 (T10): reset.
- S1 (T3): IRQ.

**LEDs** (L14, L16, N14, N16), activos en bajo:

| LED | Pin | Indica |
|---|---|---|
| 0 | L14 | LED del femto: cambia con cada IRQ |
| 1 | L16 | Latido: la FPGA está corriendo |
| 2 | N14 | Acceso a la RAM |
| 3 | N16 | Acceso a la flash |

## Pasos

1. **Programa de prueba:** `cd tinytapeout && make cocotb` lo simula y genera `build/cocotb/programa_fpga.bin`. `esp32_flash_emu/firmware.h` ya trae ese mismo programa; `make esp-firmware` lo vuelve a generar.
2. **ESP32:** `make esp-upload`. El monitor serie del ESP32 (115200) debe mostrar `Primeros bytes: 13 00 00 00`.
3. **FPGA:** `make bitstream` y luego `make prog`.
4. **UART:** `sudo minicom -b 115200 -D /dev/ttyUSB0`. Después presiona S0 (reset).

Lo que se debe ver:
```
femto_UN FPGA
Hello World
Esperando IRQ...
```
Con cada pulsación de S1 aparece `IRQ 1`, `IRQ 2`… y el LED 0 cambia de estado.

**Velocidad:** el bus va a 30 kHz (`SPI_DIV = 400`) para que el ESP32 alcance a responder. Por eso cada instrucción tarda unos 2 ms, y el saludo completo se demora cerca de un segundo.

**Margen para el ESP32:** con `CS_WAIT = 6`, el CS queda quieto unos 100 µs antes del primer flanco de SCK y después de cada trama. Así el ESP32 tiene tiempo de atender sus interrupciones sin perder flancos.

**Errores del bus:** en el monitor del ESP32, `p` muestra cuántas transacciones hubo y cuántas tuvieron error (otro comando, otra cantidad de bytes o una trama cortada). Lo normal es 0 errores.
