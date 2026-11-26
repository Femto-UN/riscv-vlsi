/*
 * Emulador de flash SPI (solo lectura) en un ESP32-C6 para femto_UN en la Tang Primer 20K.
 *
 * Responde al comando READ (03h + 3 bytes de dirección) con el programa de firmware.h.
 * firmware.h se genera desde femto_UN/fpga con:  make esp-firmware
 *
 * El bus SPI es compartido con la RAM (FM25V02): el ESP32 solo maneja MISO mientras su
 * CS está en bajo; el resto del tiempo deja MISO en alta impedancia para que la RAM
 * pueda contestar por el mismo cable.
 *
 * Conexiones (GND común entre ESP32, Tang, RAM y FTDI):
 *   GPIO7  CS   <- flash_cs_n  (FPGA P8)
 *   GPIO6  SCK  <- spi_sck     (FPGA T7)
 *   GPIO5  MOSI <- spi_mosi    (FPGA T8)
 *   GPIO4  MISO -> spi_miso    (FPGA P9)
 *
 * SPI modo 0 leyendo los registros de GPIO: la FPGA usa un SCK lento (30 kHz).
 * Para no perder flancos de SCK:
 *   - cada lectura de los pines se repite hasta obtener 3 valores iguales (filtra
 *     rebotes y ruido de los cables);
 *   - las interrupciones del ESP32 se desactivan mientras dura cada transacción (unos
 *     2 ms), porque una interrupción larga podría hacer perder un flanco.
 * Monitor serie (115200): 'p' = contadores y últimas transacciones con error,
 * 'c' = borrar contadores.
 * La FPGA siempre pide 4 bytes por lectura: una transacción con otro comando, otra
 * cantidad de bytes o cortada antes de tiempo se cuenta como error (flancos perdidos o
 * ruido en los cables).
 */
#include "soc/gpio_reg.h"
#include "firmware.h"

#define PIN_MISO 4
#define PIN_MOSI 5
#define PIN_SCK  6
#define PIN_CS   7

#define M_CS   (1UL << PIN_CS)
#define M_SCK  (1UL << PIN_SCK)
#define M_MOSI (1UL << PIN_MOSI)
#define M_MISO (1UL << PIN_MISO)

// Lee los pines; repite hasta tener 3 lecturas iguales de CS, SCK y MOSI
static inline uint32_t rd() {
  const uint32_t m = M_CS | M_SCK | M_MOSI;
  uint32_t a, b, c;
  do {
    a = REG_READ(GPIO_IN_REG);
    b = REG_READ(GPIO_IN_REG);
    c = REG_READ(GPIO_IN_REG);
  } while (((a ^ b) | (b ^ c)) & m);
  return a;
}

// Valor de MISO
static inline void miso(uint32_t bit) {
  if (bit) REG_WRITE(GPIO_OUT_W1TS_REG, M_MISO);
  else     REG_WRITE(GPIO_OUT_W1TC_REG, M_MISO);
}

// MISO como salida (CS en bajo) o en alta impedancia (CS en alto)
static inline void miso_on()  { REG_WRITE(GPIO_ENABLE_W1TS_REG, M_MISO); }
static inline void miso_off() { REG_WRITE(GPIO_ENABLE_W1TC_REG, M_MISO); }

static inline uint8_t mem(uint32_t a) {
  return a < firmware_bin_len ? firmware_bin[a] : 0xFF;
}

// Esperan un flanco de SCK; devuelven false si CS sube (fin de la transacción)
static inline bool wait_rise(uint32_t &v) {
  do { v = rd(); if (v & M_CS) return false; } while (!(v & M_SCK));
  return true;
}
static inline bool wait_fall() {
  uint32_t v;
  do { v = rd(); if (v & M_CS) return false; } while (v & M_SCK);
  return true;
}

// Recibe un byte (MOSI se toma en el flanco de subida). -1 si CS sube antes.
static int rx_byte() {
  uint8_t b = 0;
  uint32_t v;
  for (int i = 0; i < 8; i++) {
    if (!wait_rise(v)) return -1;
    b = (b << 1) | ((v & M_MOSI) ? 1 : 0);
    if (!wait_fall()) return (i == 7) ? b : -1;
  }
  return b;
}

// Envía un byte (MISO cambia después del flanco de bajada)
static bool tx_byte(uint8_t b) {
  uint32_t v;
  for (int i = 7; i >= 0; i--) {
    miso((b >> i) & 1);
    if (!wait_rise(v)) return false;
    if (!wait_fall()) return false;
  }
  return true;
}

// ---------------- Registro de las últimas transacciones ----------------
struct Entry { int16_t cmd; uint32_t addr; uint32_t n; };
#define LOGN 32
static Entry logbuf[LOGN];
static uint32_t nlog = 0, ntrans = 0, nerr = 0;

// Guarda solo las transacciones con error (las buenas solo se cuentan)
static void logit(int16_t cmd, uint32_t addr, uint32_t n) {
  if (cmd == 0x03 && n == 4) return;
  nerr++;
  logbuf[nlog % LOGN] = {cmd, addr, n};
  nlog++;
}

static void dump() {
  Serial.printf("\nTransacciones: %lu   con error: %lu\n",
                (unsigned long)ntrans, (unsigned long)nerr);
  uint32_t first = nlog > LOGN ? nlog - LOGN : 0;
  for (uint32_t i = first; i < nlog; i++) {
    Entry &e = logbuf[i % LOGN];
    if (e.cmd < 0)
      Serial.printf("#%lu  incompleta (CS subio antes de 8 pulsos de SCK)\n", (unsigned long)i);
    else
      Serial.printf("#%lu  cmd=%02X  addr=0x%06lX  bytes enviados=%lu\n",
                    (unsigned long)i, e.cmd, (unsigned long)e.addr, (unsigned long)e.n);
  }
}

static void transaction() {
  int cmd = rx_byte();
  if (cmd < 0) { logit(-1, 0, 0); return; }
  if (cmd != 0x03) { logit(cmd, 0, 0); return; }

  uint32_t a = 0;
  for (int i = 0; i < 3; i++) {
    int x = rx_byte();
    if (x < 0) { logit(cmd, a, 0); return; }
    a = (a << 8) | (uint32_t)x;
  }
  uint32_t start = a, n = 0;
  while (tx_byte(mem(a))) { a = (a + 1) & 0xFFFFFF; n++; }
  logit(cmd, start, n);
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_CS, INPUT_PULLUP);
  pinMode(PIN_SCK, INPUT);
  pinMode(PIN_MOSI, INPUT);
  pinMode(PIN_MISO, OUTPUT);
  miso(1);
  miso_off();                              // en reposo: alta impedancia
  delay(1500);
  Serial.printf("\nEmulador de flash (femto_UN, bus compartido) listo: %u bytes\n", firmware_bin_len);
  Serial.printf("Primeros bytes: %02X %02X %02X %02X (deben ser 13 00 00 00)\n",
                mem(0), mem(1), mem(2), mem(3));
  Serial.println("Escribe p + Enter para ver transacciones, c + Enter para borrar.");
}

void loop() {
  static uint32_t k = 0;
  if (rd() & M_CS) {                       // reposo: CS en alto
    if ((++k & 0xFFF) == 0 && Serial.available()) {
      int c = Serial.read();
      if (c == 'p') dump();
      else if (c == 'c') { nlog = ntrans = nerr = 0; Serial.println("Contadores borrados"); }
    }
    return;
  }
  ntrans++;                                // CS bajó: atender la transacción
  portDISABLE_INTERRUPTS();
  miso_on();
  transaction();
  while (!(rd() & M_CS)) {}                // espera a que CS suba
  miso_off();
  portENABLE_INTERRUPTS();
}
