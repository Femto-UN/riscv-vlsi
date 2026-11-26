# Toolchain y entorno de trabajo

Guía para montar desde cero el entorno usado en todas las pruebas del repo.

**Sistema operativo:** Fedora Linux 44
**Editor:** VS Code

## Resumen de herramientas

| Herramienta | Uso | Ubicación |
|-------------|-----|-----------|
| oss-cad-suite 2026-06-29 (Yosys 0.66+179, Icarus Verilog, GTKWave) | Síntesis y simulación | `~/fpga-tools/oss-cad-suite/` |
| Gowin EDA V1.9.11.03 Education (`gw_sh`) | Place & route para Tang Primer 20K | `~/Descargas/IDE/` |
| openFPGALoader | Programar la FPGA | Compilado desde fuente |
| netlistsvg | Diagramas del netlist | npm global (`~/.npm-global`) |
| xPack `riscv-none-elf-gcc` 14.2.0-3 | Firmware bare-metal femtoRV32 | `~/riscv-toolchain` |
| tio | Terminal serial (UART) | dnf |
| KiCad 10.0 | Diseño de PCB | TODO |

## 1. oss-cad-suite

Versión usada: **2026-06-29** (Yosys 0.66+179, git e74db6dea).
Se descarga de https://github.com/YosysHQ/oss-cad-suite-build/releases y se descomprime en `~/fpga-tools/`.

```bash
export PATH="$HOME/fpga-tools/oss-cad-suite/bin:$PATH"   # en ~/.bashrc
```

###  Problema: include duplicado en `cells_sim.v` (ECP5)
En Fedora 44, la simulación post-síntesis de ECP5 falla porque `cells_sim.v` incluye `cells_ff.vh` y `cells_io.vh` dos veces, lo que genera módulos definidos por duplicado.

**Solución:** copiar las celdas de simulación a una carpeta local `sim_cells/` del proyecto y parchear ahí la copia, sin tocar la instalación:

```bash
YOSYS_ECP5=~/fpga-tools/oss-cad-suite/share/yosys/ecp5
mkdir -p sim_cells
cp $YOSYS_ECP5/cells_sim.v $YOSYS_ECP5/common_sim.vh \
   $YOSYS_ECP5/cells_ff.vh $YOSYS_ECP5/cells_io.vh \
   $YOSYS_ECP5/ccu2c_sim.vh sim_cells/
```

Luego, en `sim_cells/cells_sim.v`, eliminar estas dos líneas (223 y 224 en la versión 2026-06-29):

```verilog
`include "cells_ff.vh"
`include "cells_io.vh"
```

Con `sed` (solo válido para esta versión, en otras los números de línea pueden cambiar):

```bash
sed -i '223,224d' sim_cells/cells_sim.v
```

Para verificar el cambio:

```bash
diff $YOSYS_ECP5/cells_sim.v sim_cells/cells_sim.v
```

Una copia ya parcheada está en `mult_32/sim_cells/` de este repo.

###  Nota: `yosys-config` puede no existir
Aunque Yosys esté instalado, `yosys-config` puede faltar. No es necesario para los flujos de este repo.

## 2. Gowin EDA

Versión: **V1.9.11.03 Education** (`Gowin_V1.9.11.03_Education_Linux.tar.gz`), descargada del sitio de Gowin y descomprimida en `~/Descargas/IDE/`.

Los Makefiles lo referencian así:

```make
GW_SH := /home/pci/Descargas/IDE/bin/gw_sh
```

> Cada persona debe ajustar esta ruta a su propia instalación.

###  Problema: conflicto de librerías en Fedora
Gowin trae sus propias copias de `libfreetype.so.6` y `libstdc++.so.6`, más viejas que las del sistema, y eso lo hace fallar en Fedora 44.

**Solución:** moverlas a una carpeta de respaldo para que Gowin use las del sistema:

```bash
cd ~/Descargas/IDE
mkdir -p lib_backup
mv lib/libfreetype.so.6 lib/libstdc++.so.6 lib_backup/
```

Para deshacerlo, basta con devolverlas a `lib/`.

###  Problemas con el scripting TCL
- `create_project` cambia el directorio de trabajo: guardar el directorio con `[pwd]` **antes** de llamarlo.
- Usar rutas absolutas en todos los `add_file`.
- El bitstream queda en `build/<proyecto>/impl/pnr/`.

La síntesis se hace con Yosys y Gowin solo hace place & route:

```bash
yosys -p "synth_gowin -top top -family gw2a -vout build/netlist_gw.v"
```

## 3. openFPGALoader

Compilado desde el código fuente (https://github.com/trabucayre/openFPGALoader).

TODO: dependencias y comandos de compilación.

Verificar que detecta la placa y programar:

```bash
openFPGALoader --scan-usb
openFPGALoader -b tangprimer20k build/<proyecto>/impl/pnr/<proyecto>.fs
```

## 4. netlistsvg (Node.js)

```bash
sudo dnf install nodejs22-bin nodejs22-npm-bin
```

 `npm install -g` falla por permisos si no se configura un prefijo local primero:

```bash
mkdir -p ~/.npm-global
npm config set prefix "$HOME/.npm-global"
echo 'export PATH="$HOME/.npm-global/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
npm install -g netlistsvg
```

## 5. Toolchain RISC-V

###  Lo que NO funciona
El paquete de Fedora `gcc-riscv32-linux-gnu` / `binutils-riscv32-linux-gnu` **no sirve** para bare-metal: no trae sysroot (falta `stdint.h`, etc.) y no hay paquete `glibc-riscv32-linux-gnu` disponible.

###  Lo que sí funciona: xPack riscv-none-elf-gcc

```bash
curl -L -o riscv-toolchain.tar.gz \
  https://github.com/xpack-dev-tools/riscv-none-elf-gcc-xpack/releases/download/v14.2.0-3/xpack-riscv-none-elf-gcc-14.2.0-3-linux-x64.tar.gz
mkdir -p ~/riscv-toolchain
tar -xzf riscv-toolchain.tar.gz -C ~/riscv-toolchain --strip-components=1
echo 'export PATH="$HOME/riscv-toolchain/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
riscv-none-elf-gcc --version
```

> `--strip-components=1` es importante: sin él los binarios quedan en una subcarpeta y `riscv-none-elf-as` no se encuentra en el PATH.

### Compilar con los Makefiles del curso
Los Makefiles usan `riscv64-unknown-elf` por defecto:

```bash
make CROSS=riscv-none-elf TARGET=hello firmware.bin
```

###  Problema: ruta de `libgcc` al enlazar
El Makefile del curso apunta `-L` a `/usr/lib/gcc/riscv64-unknown-elf/14.2.0/rv32i/ilp32/`, que no existe con xPack. Hay que cambiarla a la ruta del toolchain:

```
-L$(HOME)/riscv-toolchain/lib/gcc/riscv-none-elf/14.2.0/rv32i/ilp32/
```

Para encontrarla:

```bash
find ~/riscv-toolchain -iname "libgcc.a"
```

## 6. Instrumentos y comunicación

| Herramienta | Instalación | Uso |
|-------------|-------------|-----|
| tio | `sudo dnf install tio` | Terminal serial para la UART |
| Digilent Adept Runtime 2.30.1 | `sudo dnf install ./digilent.adept.runtime-2.30.1-2.x86_64.rpm` | Driver del Analog Discovery 2 |
| WaveForms | TODO | Software del Analog Discovery 2 |
| PulseView | `sudo dnf install pulseview sigrok-firmware-fx2lafw` | Analizador lógico |
| SEGGER J-Link | `sudo dnf install ./JLink_Linux_*.rpm` | TODO: para qué se usó |

## 7. Otros

- **Chrome como Flatpak:** necesita permisos explícitos de acceso al sistema de archivos (TODO: comando o Flatseal).

## Verificación rápida

```bash
yosys -V
iverilog -V
openFPGALoader --Version
riscv-none-elf-gcc --version
netlistsvg --version
tio --version
```