# Reportes de Gowin — femto_UN v2 en la Tang Primer 20K

Reportes de síntesis y place & route de Gowin EDA para el procesador femto_UN v2 (bus SPI único e interrupciones) en la FPGA GW2A-LV18PG256C8/I7 de la Tang Primer 20K Dock. Corresponden al bitstream usado en la [prueba en hardware](../../../../../pruebas/fpga_tang20k_v2/).

Se generan con `make bitstream` en `disenos/vlsi/femto_UN/fpga/`; Gowin los deja en `build/femto_tang20k/impl/`.

## Resumen de recursos

| Recurso | Uso | Porcentaje |
|---|---|---|
| Lógica (LUT + ALU) | 2627 / 20736 (2361 LUT, 266 ALU) | 13 % |
| Registros | 1613 / 16173 (1608 FF de lógica, 5 FF de I/O, 0 latches) | 10 % |
| CLS | 2249 / 10368 | 22 % |
| BSRAM | 0 | |
| I/O | 16 / 207 | 8 % |
| rPLL | 1 / 4 | 25 % |

El banco de registros de 32 × 32 bits se implementa con flip-flops, lo que explica la mayor parte de los registros usados. El programa se lee de la flash externa por el bus SPI.

## Timing

| Reloj | Restricción | Fmax obtenida |
|---|---|---|
| Salida del rPLL (reloj del sistema) | 24.000 MHz | 33.145 MHz |

## Potencia estimada

| Potencia | mW |
|---|---|
| Total | 129,285 |
| Reposo (quiescent) | 122,636 |

La potencia dinámica es de unos 6,6 mW; casi todo el consumo estimado corresponde al reposo del dispositivo.

## Archivos

| Archivo | Contenido |
|---|---|
| `femto_tang20k_syn.rpt.html` | Reporte de síntesis |
| `femto_tang20k_syn_resource.html` | Recursos de síntesis por módulo |
| `femto_tang20k.rpt.txt`, `femto_tang20k.rpt.html` | Reporte de place & route con el uso de recursos |
| `femto_tang20k.tr.html`, `femto_tang20k_tr_cata.html`, `femto_tang20k_tr_content.html` | Reporte de timing (abrir `femto_tang20k.tr.html`) |
| `femto_tang20k.timing_paths` | Rutas críticas |
| `femto_tang20k.power.html` | Estimación de potencia |
| `femto_tang20k.pin.html` | Asignación de pines |
