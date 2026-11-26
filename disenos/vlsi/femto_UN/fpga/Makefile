# femto_UN en la Tang Primer 20K Dock
#
#   make bitstream     síntesis, place & route y bitstream con Gowin (gw_sh)
#   make prog          carga el bitstream en la FPGA (se pierde al apagar)
#   make esp-firmware  genera esp32_flash_emu/firmware.h desde el programa de prueba
#   make esp-upload    compila y sube el emulador de flash al ESP32-C6 (arduino-cli)
#
# El programa de prueba lo genera la simulación:  cd ../../tinytapeout && make cocotb
# (archivo tinytapeout/build/cocotb/programa_fpga.bin)

FS      = build/femto_tang20k/impl/pnr/femto_tang20k.fs
BIN    ?= ../../tinytapeout/build/cocotb/programa_fpga.bin
ESP     = $(CURDIR)/esp32_flash_emu
ARDUINO ?= $(HOME)/arduino-cli/arduino-cli
PORT    ?= /dev/ttyACM0

.PHONY: bitstream prog esp-firmware esp-upload clean

bitstream:
	QT_QPA_PLATFORM=offscreen gw_sh build.tcl
	@ls -la $(FS)

prog:
	openFPGALoader -b tangprimer20k $(FS)

esp-firmware:
	python3 bin2h.py $(BIN) $(ESP)/firmware.h

esp-upload:
	$(ARDUINO) compile --fqbn esp32:esp32:esp32c6 $(ESP)
	$(ARDUINO) upload -p $(PORT) --fqbn esp32:esp32:esp32c6 $(ESP)

clean:
	rm -rf build
