# Informe de pruebas del procesador femto_UN

Informe técnico de las pruebas del procesador femto_UN fabricado en Tiny Tapeout.

**[Abrir el PDF](informe_pruebas_femto_UN.pdf)**

## Contenido

1. Introducción
2. El diseño fabricado: arquitectura RTL, layout 2D y 3D y resultados de implementación
3. Montaje físico: equipos, conexiones y condiciones
4. ESP32-C6 como memoria flash y primer arranque: comportamiento del bus SPI del chip y Hello World por UART
5. Prueba de la memoria RAM SPI: WREN provocado, lectura, escritura y persistencia, y conversión de texto a mayúsculas
6. Conclusiones y cambios propuestos para una segunda versión

Las evidencias originales (fotos, capturas y sesiones de PulseView) están en [`pruebas/chip_femto_UN/`](../../pruebas/chip_femto_UN/), y las vistas del layout en [`asic/femto_UN_ttsky25b/`](../../asic/femto_UN_ttsky25b/).

## Compilar

- **Overleaf:** subir esta carpeta como proyecto (*New Project → Upload Project*) y compilar con pdfLaTeX.
- **Local:** `latexmk -pdf main.tex`
