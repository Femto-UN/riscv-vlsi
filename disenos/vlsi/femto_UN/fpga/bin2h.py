"""Convierte un programa .bin en firmware.h (arreglo firmware_bin) para el emulador de
flash del ESP32-C6.  Uso: python3 bin2h.py programa.bin firmware.h"""
import os
import sys

data = open(sys.argv[1], "rb").read()
with open(sys.argv[2], "w") as f:
    f.write(f"// Generado con bin2h.py a partir de {os.path.basename(sys.argv[1])}\n")
    f.write("const unsigned char firmware_bin[] = {\n")
    for i in range(0, len(data), 12):
        f.write("  " + ", ".join(f"0x{b:02x}" for b in data[i:i + 12]) + ",\n")
    f.write(f"}};\nconst unsigned int firmware_bin_len = {len(data)};\n")
