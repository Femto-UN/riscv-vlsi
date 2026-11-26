# Diseños

Código RTL de los procesadores del proyecto.

| Carpeta | Contenido |
|---|---|
| [`femto_UN_fabricado/`](femto_UN_fabricado/) | Copia del repositorio [cicamargoba/femto_UN](https://github.com/cicamargoba/femto_UN): el diseño enviado a fabricación en Tiny Tapeout. **No se modifica**; es la referencia. Ver su [`ORIGEN.md`](femto_UN_fabricado/ORIGEN.md). |
| [`vlsi/`](vlsi/) | Copia del repositorio [cicamargoba/VLSI](https://github.com/cicamargoba/VLSI): base para las mejoras del procesador (simulaciones con Icarus Verilog y cocotb, flujo OpenLane y suite de verificación). Ver su [`ORIGEN.md`](vlsi/ORIGEN.md). |

El diseño fabricado corresponde al commit `baab83f` de `cicamargoba/femto_UN`. La copia de `femto_UN_fabricado/` es del commit `b28ff83`, posterior, y solo difiere en `src/MappedSPIFlash.v`.
