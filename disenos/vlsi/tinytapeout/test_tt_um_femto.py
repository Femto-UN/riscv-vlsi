"""Simulación cocotb de tt_um_femto: procesador femtoRV32 con flash SPI, RAM SPI y UART.

Cada prueba escribe un programa corto, lo carga en la flash simulada, deja correr al
procesador hasta el final del programa y revisa el resultado: registros, contenido de
la RAM o bytes que salieron por la UART.

  execute_lui_from_cocotb_spi_flash     arranque: lee la flash y ejecuta lui
  test_hello_world                      cada letra de "Hello World" en un registro,
                                        la frase en la RAM y por la UART
  test_alu                              operaciones aritméticas y lógicas
  test_saltos                           saltos condicionales, JAL y JALR
  test_cargas_flash                     lectura de constantes de la flash
  test_ram                              escritura y lectura de palabras en la RAM
  test_uart_tx                          el procesador envía texto por la UART
  test_uart_rx                          recibe bytes, los guarda en la RAM y los reenvía
  test_interrupcion                     IRQ, rutina de atención y MRET
  test_programa_fpga                    programa de prueba de la FPGA: saludo, frase
                                        en la RAM y "IRQ n" + LED con cada IRQ

Reloj de 24 MHz, el de la placa. Con ese reloj la UART trabaja a 115200 baud.

Mapa de memoria: 0x000000 flash, 0x010000 RAM, 0x400000 UART
(UART + 0x08 dato, UART + 0x10 control al escribir / estado al leer).
"""
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, FallingEdge, First, RisingEdge, Timer
from cocotb.utils import get_sim_time

CLK_PS = 41_666                     # 24 MHz
RAM = 0x010000
UART = 0x400000
TX_BUSY, RX_AVAIL = 0x200, 0x100    # bits del registro de estado de la UART
TX_WR, LED, RX_ACK = 0x08, 0x04, 0x01   # bits del registro de control de la UART


def value(signal):
    """Valor entero de una señal, o None si tiene bits sin definir (X o Z)."""
    try:
        return int(signal.value)
    except ValueError:
        return None


# ======================================================================
# Ensamblador RV32I mínimo: cada función devuelve una instrucción de 32 bits
# ======================================================================
def R(op, rd, rs1, rs2):
    """rd = rs1 <op> rs2  (add, sub, and, or, xor, sll, srl, sra, slt, sltu)."""
    f7, f3 = {"add": (0, 0), "sub": (32, 0), "sll": (0, 1), "slt": (0, 2), "sltu": (0, 3),
              "xor": (0, 4), "srl": (0, 5), "sra": (32, 5), "or": (0, 6), "and": (0, 7)}[op]
    return (f7 << 25) | (rs2 << 20) | (rs1 << 15) | (f3 << 12) | (rd << 7) | 0x33


def I(op, rd, rs1, imm):
    """rd = rs1 <op> imm  (addi, slti, sltiu, xori, ori, andi, slli, srli, srai)."""
    f3 = {"addi": 0, "slli": 1, "slti": 2, "sltiu": 3, "xori": 4, "srli": 5, "srai": 5,
          "ori": 6, "andi": 7}[op]
    if op == "srai":
        imm |= 0x400
    return ((imm & 0xFFF) << 20) | (rs1 << 15) | (f3 << 12) | (rd << 7) | 0x13


def LOAD(op, rd, rs1, imm):
    """rd = memoria[rs1 + imm]  (lb, lh, lw, lbu, lhu)."""
    f3 = {"lb": 0, "lh": 1, "lw": 2, "lbu": 4, "lhu": 5}[op]
    return ((imm & 0xFFF) << 20) | (rs1 << 15) | (f3 << 12) | (rd << 7) | 0x03


def SW(rs2, rs1, imm):
    """memoria[rs1 + imm] = rs2  (palabra de 32 bits)."""
    i = imm & 0xFFF
    return ((i >> 5) << 25) | (rs2 << 20) | (rs1 << 15) | (2 << 12) | ((i & 31) << 7) | 0x23


def BRANCH(op, rs1, rs2, off):
    """Salta a PC + off si se cumple rs1 <op> rs2  (beq, bne, blt, bge, bltu, bgeu)."""
    f3 = {"beq": 0, "bne": 1, "blt": 4, "bge": 5, "bltu": 6, "bgeu": 7}[op]
    o = off & 0x1FFF
    return (((o >> 12) & 1) << 31) | (((o >> 5) & 0x3F) << 25) | (rs2 << 20) | (rs1 << 15) \
        | (f3 << 12) | (((o >> 1) & 0xF) << 8) | (((o >> 11) & 1) << 7) | 0x63


def LUI(rd, imm20):
    """rd = imm20 << 12."""
    return ((imm20 & 0xFFFFF) << 12) | (rd << 7) | 0x37


def AUIPC(rd, imm20):
    """rd = PC + (imm20 << 12)."""
    return ((imm20 & 0xFFFFF) << 12) | (rd << 7) | 0x17


def JAL(rd, off):
    """rd = PC + 4 y salta a PC + off."""
    o = off & 0x1FFFFF
    return (((o >> 20) & 1) << 31) | (((o >> 1) & 0x3FF) << 21) | (((o >> 11) & 1) << 20) \
        | (((o >> 12) & 0xFF) << 12) | (rd << 7) | 0x6F


def JALR(rd, rs1, imm):
    """rd = PC + 4 y salta a rs1 + imm."""
    return ((imm & 0xFFF) << 20) | (rs1 << 15) | (rd << 7) | 0x67


def CSRRW(rd, csr, rs1):
    """rd = csr; csr = rs1."""
    return (csr << 20) | (rs1 << 15) | (1 << 12) | (rd << 7) | 0x73


def CSRRS(rd, csr, rs1):
    """rd = csr; csr |= rs1 (con rs1 = x0 solo lee)."""
    return (csr << 20) | (rs1 << 15) | (2 << 12) | (rd << 7) | 0x73


MSTATUS, MTVEC, MEPC = 0x300, 0x305, 0x341
MRET = 0x30200073
NOP = 0x00000013


def LI(rd, val):
    """Carga un valor de 32 bits en rd (pseudoinstrucción li = LUI + ADDI)."""
    val &= 0xFFFFFFFF
    lo = (val & 0xFFF) - (0x1000 if val & 0x800 else 0)
    return [LUI(rd, (val - lo) >> 12), I("addi", rd, rd, lo)]


class Programa:
    """Programa para la flash: diccionario {dirección: instrucción}.

    Empieza con un NOP porque, después del reset, el procesador no ejecuta la primera
    instrucción que lee de la flash.
    """

    def __init__(self):
        self.words, self.pc = {}, 0
        self.add(NOP)

    def add(self, *instrucciones):
        """Agrega instrucciones (o listas de instrucciones, como las de LI)."""
        for ins in instrucciones:
            for w in (ins if isinstance(ins, list) else [ins]):
                self.words[self.pc] = w
                self.pc += 4

    def fin(self):
        """Agrega un salto a sí mismo (fin del programa) y devuelve su dirección."""
        direccion = self.pc
        self.add(JAL(0, 0))
        return direccion

    def putc(self, reg):
        """Envía por la UART el byte de `reg`. Usa x8 = UART y x9 como temporal.

        Espera a que la UART esté libre, escribe el dato y da un pulso en TX_WR
        (el bit es un nivel: si se queda en 1, la UART repite el byte)."""
        espera = self.pc
        self.add(LOAD("lw", 9, 8, 0x10), I("andi", 9, 9, TX_BUSY),
                 BRANCH("bne", 9, 0, espera - (self.pc + 8)))
        self.add(SW(reg, 8, 0x08), I("addi", 9, 0, TX_WR), SW(9, 8, 0x10), SW(0, 8, 0x10))

    def getc(self, reg):
        """Espera un byte de la UART y lo deja en `reg`; luego da un pulso en RX_ACK.
        Usa x8 = UART y x9 como temporal."""
        espera = self.pc
        self.add(LOAD("lw", 9, 8, 0x10), I("andi", 9, 9, RX_AVAIL),
                 BRANCH("beq", 9, 0, espera - (self.pc + 8)))
        self.add(LOAD("lw", reg, 8, 0x08), I("addi", 9, 0, RX_ACK), SW(9, 8, 0x10),
                 SW(0, 8, 0x10))

    def imagen(self, datos=None):
        """Contenido de la flash: el programa en little-endian y, opcionalmente,
        `datos` = {dirección: bytes} con constantes."""
        partes = dict(datos or {})
        partes.update({a: w.to_bytes(4, "little") for a, w in self.words.items()})
        mem = bytearray(max(a + len(d) for a, d in partes.items()))
        for a, d in partes.items():
            mem[a:a + len(d)] = d
        return mem


# ======================================================================
# Modelos de las memorias y de la terminal
# ======================================================================
class SpiFlash:
    """Flash SPI conectada al bus compartido (spi_sck, spi_mosi, spi_miso) con su
    propio chip select (flash_cs_n). Atiende el comando de lectura 03h (32 bits de
    comando y dirección) y entrega los bytes de `contents` desde esa dirección.
    Guarda en `reads` cada (comando, dirección)."""

    def __init__(self, dut, contents):
        self.dut = dut
        self.contents = contents
        self.reads = []

    def read_byte(self, address):
        """Byte de la flash en `address` (0 fuera del contenido)."""
        if address < len(self.contents):
            return self.contents[address]
        return 0

    async def run(self):
        """Recibe comando y dirección en los flancos de subida de SCK y envía los datos
        en los flancos de bajada, hasta que su CS sube. Solo maneja MISO mientras su
        CS está activo."""
        dut = self.dut
        while True:
            await FallingEdge(dut.flash_cs_n)
            request = 0
            for _ in range(32):
                await RisingEdge(dut.spi_sck)
                request = (request << 1) | int(dut.spi_mosi.value)
            command = (request >> 24) & 0xFF
            address = request & 0xFFFFFF
            assert command == 0x03, f"Comando SPI inesperado: 0x{command:02x}"
            self.reads.append((command, address))
            bit = 0
            while True:
                await First(FallingEdge(dut.spi_sck), RisingEdge(dut.flash_cs_n))
                if int(dut.flash_cs_n.value):
                    break
                byte = self.read_byte(address + bit // 8)
                dut.spi_miso.value = (byte >> (7 - bit % 8)) & 1
                bit += 1
            dut.spi_miso.value = 0


class SpiRam:
    """RAM SPI de 32 KiB (como la FM25V02) conectada al bus compartido con su propio
    chip select (ram_cs_n). Comandos: 06h (WREN), 02h (escritura) y 03h (lectura), con
    dirección de 2 bytes. Solo acepta una escritura después de un WREN.

    `mem` es el contenido y `frames` guarda cada operación como (comando, dirección,
    bytes). Los primeros 64 bytes también se copian en flashram0.mem de la envoltura,
    para verlos en GTKWave."""

    def __init__(self, dut):
        self.dut = dut
        self.mem = bytearray(0x8000)
        self.frames = []
        self.wren = False

    def word(self, address):
        """Palabra guardada en `address` (little-endian: el byte 0 primero)."""
        return int.from_bytes(self.mem[address:address + 4], "little")

    async def run(self):
        """Por cada operación: toma MOSI en los flancos de subida de SCK (comando,
        dirección y, al escribir, los datos) y, al leer, envía los datos en los flancos
        de bajada."""
        dut = self.dut
        while True:
            await FallingEdge(dut.ram_cs_n)
            bits, command, address, byte, data = 0, 0, 0, 0, bytearray()
            while True:
                await First(RisingEdge(dut.spi_sck), FallingEdge(dut.spi_sck),
                            RisingEdge(dut.ram_cs_n))
                if int(dut.ram_cs_n.value):
                    break
                if int(dut.spi_sck.value):                       # flanco de subida
                    b = int(dut.spi_mosi.value)
                    if bits < 8:
                        command = (command << 1) | b
                    elif bits < 24:
                        address = (address << 1) | b
                    elif command == 0x02:                         # dato a escribir
                        byte = ((byte << 1) | b) & 0xFF
                        if (bits - 23) % 8 == 0:
                            pos = (address + len(data)) & 0x7FFF
                            self.mem[pos] = byte
                            data.append(byte)
                            if pos < 64:                          # copia para GTKWave
                                dut.flashram0.mem[pos].value = byte
                    bits += 1
                elif command == 0x03 and bits >= 24:              # flanco de bajada
                    k = bits - 24
                    byte = self.mem[(address + k // 8) & 0x7FFF]
                    if k % 8 == 0:
                        data.append(byte)
                    dut.spi_miso.value = (byte >> (7 - k % 8)) & 1
            dut.spi_miso.value = 0
            assert command in (0x02, 0x03, 0x06), f"RAM: comando inesperado 0x{command:02x}"
            if command == 0x06:
                self.wren = True
            elif command == 0x02:
                assert self.wren, "RAM: escritura sin WREN previo"
                self.wren = False
            self.frames.append((command, address & 0x7FFF, bytes(data)))


async def un_solo_cs(dut):
    """Revisa en todo momento que los dos chip select no estén activos a la vez y que,
    entre dos tramas, el CS quede en alto al menos DIV ciclos de reloj (el medio periodo
    de SCK): un emulador de flash lento necesita ver ese tiempo para separarlas."""
    subida = {}                                   # instante en que terminó la última trama
    anterior = {"flash_cs_n": None, "ram_cs_n": None}
    div = int(dut.dut.femto0.mapped_spi.DIV.value)
    while True:
        await First(FallingEdge(dut.flash_cs_n), FallingEdge(dut.ram_cs_n),
                    RisingEdge(dut.flash_cs_n), RisingEdge(dut.ram_cs_n))
        ahora = get_sim_time("ps")
        for nombre in anterior:
            nivel = value(getattr(dut, nombre))       # None antes del reset
            if nivel == 1 and anterior[nombre] == 0:  # fin de una trama
                subida[nombre] = ahora
            elif nivel == 0 and nombre in subida:     # comienzo de la siguiente
                alto = ahora - subida.pop(nombre)
                assert alto >= div * CLK_PS, f"{nombre} quedó en alto solo {alto} ps entre tramas"
            anterior[nombre] = nivel
        assert value(dut.flash_cs_n) != 0 or value(dut.ram_cs_n) != 0, \
            "flash y RAM seleccionadas al mismo tiempo"


class Uart:
    """Terminal serie 8N1 a 115200 baud conectada a uart_tx y uart_rx.
    Lo que transmite el procesador queda en `received`."""

    BIT_NS = 1e9 / 115_200

    def __init__(self, dut):
        self.dut = dut
        self.received = bytearray()

    def wait(self, bits):
        """Espera `bits` duraciones de bit."""
        return Timer(bits * self.BIT_NS, unit="ns", round_mode="round")

    async def monitor(self):
        """Lee uart_tx: detecta el bit de inicio y toma cada bit en su centro."""
        tx = self.dut.uart_tx
        while True:
            await FallingEdge(tx)
            await self.wait(0.5)
            if int(tx.value):
                continue
            byte = 0
            for i in range(8):
                await self.wait(1)
                byte |= int(tx.value) << i
            await self.wait(1)
            assert int(tx.value) == 1, f"UART: bit de parada en 0 (byte 0x{byte:02x})"
            self.received.append(byte)

    async def send(self, data, pause_bits=30):
        """Envía `data` por uart_rx, con una pausa entre bytes para que el programa
        alcance a leer cada uno."""
        for c in data:
            for b in [0] + [(c >> i) & 1 for i in range(8)] + [1]:
                self.dut.uart_rx.value = b
                await self.wait(1)
            await self.wait(pause_bits)


# ======================================================================
# Arranque del chip
# ======================================================================
class Chip:
    """tt_um_femto con su flash, su RAM y su terminal."""

    def __init__(self, dut, flash_contents):
        self.dut = dut
        self.cpu = dut.dut.femto0.CPU
        self.flash = SpiFlash(dut, flash_contents)
        self.ram = SpiRam(dut)
        self.uart = Uart(dut)

    def reg(self, i):
        """Valor del registro x<i> (None si nunca se escribió)."""
        return value(self.cpu.registerFile[i])

    async def run_until(self, address, max_cycles=1_000_000):
        """Avanza hasta que el procesador va a ejecutar la instrucción de `address`;
        en ese momento las instrucciones anteriores ya terminaron."""
        for _ in range(max_cycles):
            await FallingEdge(self.dut.clk)
            if value(self.cpu.state) == 0b0001 and value(self.cpu.PC) == address:
                return
        raise AssertionError(f"el PC no llegó a 0x{address:x}")

    def check(self, expected):
        """Compara registros con {número: valor esperado}."""
        bad = [f"x{r} = {self.reg(r)} (se esperaba {v & 0xFFFFFFFF})"
               for r, v in expected.items() if self.reg(r) != v & 0xFFFFFFFF]
        assert not bad, "registros incorrectos: " + "; ".join(bad)


async def start(dut, programa, datos=None):
    """Carga el programa en la flash, arranca el reloj y los modelos, suelta el reset
    y devuelve el Chip."""
    chip = Chip(dut, programa.imagen(datos))
    dut.rst_n.value, dut.uart_rx.value, dut.irq.value, dut.spi_miso.value = 0, 1, 0, 0
    cocotb.start_soon(Clock(dut.clk, CLK_PS, unit="ps").start())
    cocotb.start_soon(chip.flash.run())
    cocotb.start_soon(chip.ram.run())
    cocotb.start_soon(chip.uart.monitor())
    cocotb.start_soon(un_solo_cs(dut))
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    return chip


# ======================================================================
# Pruebas
# ======================================================================
@cocotb.test()
async def execute_lui_from_cocotb_spi_flash(dut):
    """El procesador pide sus primeras instrucciones a la flash (comando 03h en las
    direcciones 0 y 4) y ejecuta lui x6, 0x400, que deja x6 = 0x00400000."""
    p = Programa()
    p.add(LUI(6, 0x400))
    fin = p.fin()
    chip = await start(dut, p)
    await chip.run_until(fin)
    assert value(dut.debug_x6) == 0x00400000, f"x6 = {value(dut.debug_x6)}"
    assert chip.flash.reads[:2] == [(0x03, 0), (0x03, 4)], chip.flash.reads[:2]


FRASE = b"Hello World"
# Un registro por letra: los mismos que muestra la vista de GTKWave del repositorio
REGISTROS_FRASE = [10, 11, 12, 13, 14, 15, 18, 28, 29, 30, 31]


@cocotb.test()
async def test_hello_world(dut):
    """El procesador guarda cada letra de "Hello World" en un registro (x10 = 'H',
    x11 = 'e', ... x31 = 'd'), escribe la frase en la RAM (direcciones 0 a 10) y la
    envía por la UART.

    En GTKWave: el grupo "Frase" muestra la letra de cada registro en ASCII,
    flashram0.mem[0..10] muestra la frase en la RAM y uart0.tx_data muestra cada
    letra que sale por TXD.
    """
    p = Programa()
    p.add(LI(8, UART), LI(1, RAM))
    for reg, letra in zip(REGISTROS_FRASE, FRASE):          # 1) una letra por registro
        p.add(I("addi", reg, 0, letra))
    texto = FRASE.ljust(12, b" ")                           # 2) frase en la RAM
    for k in range(0, 12, 4):                               #    (4 letras por palabra)
        p.add(LI(2, int.from_bytes(texto[k:k + 4], "little")), SW(2, 1, k))
    for reg in REGISTROS_FRASE:                             # 3) frase por la UART
        p.putc(reg)
    fin = p.fin()
    chip = await start(dut, p)
    await chip.run_until(fin, max_cycles=3_000_000)
    await chip.uart.wait(12)                                # última letra en la línea
    chip.check(dict(zip(REGISTROS_FRASE, FRASE)))
    assert bytes(chip.ram.mem[:11]) == FRASE, f"en la RAM quedó {bytes(chip.ram.mem[:11])!r}"
    assert chip.uart.received == FRASE, f"por la UART salió {bytes(chip.uart.received)!r}"


@cocotb.test()
async def test_alu(dut):
    """Operaciones con registros y con inmediatos, usando x1 = 0x80000005 (negativo)
    y x2 = 7. Los valores esperados se calculan en Python."""
    a, b = 0x80000005, 7
    sa = a - (1 << 32)                            # x1 con signo
    p = Programa()
    p.add(LI(1, a), LI(2, b))
    casos = [
        (R("add", 3, 1, 2), a + b),        (R("sub", 4, 1, 2), a - b),
        (R("and", 5, 1, 2), a & b),        (R("or", 6, 1, 2), a | b),
        (R("xor", 7, 1, 2), a ^ b),        (R("sll", 8, 1, 2), a << b),
        (R("srl", 9, 1, 2), a >> b),       (R("sra", 10, 1, 2), sa >> b),
        (R("slt", 11, 1, 2), 1),           (R("sltu", 12, 1, 2), 0),
        (I("addi", 13, 1, -6), a - 6),     (I("andi", 14, 1, 0xFF), a & 0xFF),
        (I("ori", 15, 1, 0x700), a | 0x700), (I("xori", 16, 1, -1), ~a),
        (I("slti", 17, 1, 0), 1),          (I("sltiu", 18, 2, 8), 1),
        (I("slli", 19, 2, 28), b << 28),   (I("srli", 20, 1, 31), 1),
        (I("srai", 21, 1, 4), sa >> 4),    (LUI(22, 0xABCDE), 0xABCDE000),
    ]
    p.add(*[ins for ins, _ in casos])
    pc_auipc = p.pc
    p.add(AUIPC(23, 1))
    fin = p.fin()
    chip = await start(dut, p)
    await chip.run_until(fin)
    expected = {3 + k: v for k, (_, v) in enumerate(casos)}
    expected[23] = pc_auipc + 0x1000
    chip.check(expected)


@cocotb.test()
async def test_saltos(dut):
    """Los seis saltos condicionales, tomados y no tomados (x10..x21 = 1 si saltó),
    un bucle de 5 vueltas (x22 = 5), JAL y JALR (guardan PC + 4)."""
    p = Programa()
    p.add(LI(1, -1), LI(2, 1))                    # x1 = -1, x2 = 1
    casos = [("beq", 1, 1, 1), ("beq", 1, 2, 0), ("bne", 1, 2, 1), ("bne", 2, 2, 0),
             ("blt", 1, 2, 1), ("blt", 2, 1, 0), ("bge", 2, 1, 1), ("bge", 1, 2, 0),
             ("bltu", 2, 1, 1), ("bltu", 1, 2, 0), ("bgeu", 1, 2, 1), ("bgeu", 2, 1, 0)]
    expected = {}
    for k, (op, rs1, rs2, salta) in enumerate(casos):
        # rd = 1; si salta, se brinca la instrucción que lo pone en 0
        p.add(I("addi", 10 + k, 0, 1), BRANCH(op, rs1, rs2, 8), I("addi", 10 + k, 0, 0))
        expected[10 + k] = salta
    p.add(I("addi", 22, 0, 0), I("addi", 23, 0, 5))
    bucle = p.pc
    p.add(I("addi", 22, 22, 1), BRANCH("bne", 22, 23, bucle - (p.pc + 4)))
    pc_jal = p.pc
    p.add(JAL(24, 8), I("addi", 25, 0, 1))        # JAL se salta el addi
    p.add(AUIPC(26, 0), JALR(27, 26, 12), I("addi", 25, 0, 1))   # JALR también
    fin = p.fin()
    chip = await start(dut, p)
    await chip.run_until(fin)
    expected.update({22: 5, 24: pc_jal + 4, 27: pc_jal + 16})
    chip.check(expected)
    assert chip.reg(25) is None, "JAL o JALR no saltaron"


@cocotb.test()
async def test_cargas_flash(dut):
    """lw, lh, lhu, lb y lbu leen constantes guardadas en la flash (dirección 0x1000),
    con extensión de signo o de ceros."""
    datos = {0x1000: bytes.fromhex("8182ff7f78563412")}   # 0x7fff8281, 0x12345678
    p = Programa()
    p.add(LI(1, 0x1000))
    casos = [(LOAD("lw", 2, 1, 0), 0x7FFF8281), (LOAD("lw", 3, 1, 4), 0x12345678),
             (LOAD("lh", 4, 1, 0), 0xFFFF8281), (LOAD("lhu", 5, 1, 0), 0x8281),
             (LOAD("lh", 6, 1, 2), 0x7FFF), (LOAD("lb", 7, 1, 0), 0xFFFFFF81),
             (LOAD("lbu", 8, 1, 1), 0x82), (LOAD("lbu", 9, 1, 7), 0x12)]
    p.add(*[ins for ins, _ in casos])
    fin = p.fin()
    chip = await start(dut, p, datos)
    await chip.run_until(fin)
    chip.check({2 + k: v for k, (_, v) in enumerate(casos)})


@cocotb.test()
async def test_ram(dut):
    """sw guarda palabras en la RAM (incluida la última, 0x7FFC, de los 32 KiB) y lw
    las lee en x10..x13. Revisa los registros,
    el contenido de la RAM y los comandos del bus: cada escritura es WREN (06h) +
    WRITE (02h), y cada lectura es READ (03h)."""
    palabras = {0x0000: 0xCAFEBABE, 0x0004: 0x12345678, 0x0100: 0x80000001,
                0x7FFC: 0xDEADBEEF}
    p = Programa()
    for off, w in palabras.items():
        p.add(LI(2, w), LI(3, RAM + off), SW(2, 3, 0))
    for k, off in enumerate(palabras):
        p.add(LI(3, RAM + off), LOAD("lw", 10 + k, 3, 0))
    fin = p.fin()
    chip = await start(dut, p)
    await chip.run_until(fin)
    chip.check({10 + k: w for k, w in enumerate(palabras.values())})
    for off, w in palabras.items():
        assert chip.ram.word(off) == w, f"RAM[0x{off:04x}] = 0x{chip.ram.word(off):08x}"
    assert [(c, a) for c, a, _ in chip.ram.frames] == \
        [f for a in palabras for f in ((0x06, 0), (0x02, a))] + \
        [(0x03, a) for a in palabras], chip.ram.frames


@cocotb.test()
async def test_uart_tx(dut):
    """El procesador envía "Hola femto" por la UART y la terminal lo recibe completo."""
    texto = b"Hola femto\r\n"
    p = Programa()
    p.add(LI(8, UART))
    for c in texto:
        p.add(I("addi", 27, 0, c))
        p.putc(27)
    fin = p.fin()
    chip = await start(dut, p)
    await chip.run_until(fin, max_cycles=3_000_000)
    await chip.uart.wait(12)                      # último byte en la línea
    assert chip.uart.received == texto, f"se recibió {bytes(chip.uart.received)!r}"


@cocotb.test()
async def test_uart_rx(dut):
    """El procesador recibe "femto" por la UART, guarda cada byte en una palabra de la
    RAM y después los lee de la RAM y los reenvía: recibir, guardar y transmitir."""
    mensaje = b"femto"
    p = Programa()
    p.add(LI(8, UART), LI(20, RAM), I("addi", 21, 0, 4 * len(mensaje)), I("addi", 22, 0, 0))
    recibir = p.pc                                # x22 = desplazamiento en la RAM
    p.getc(27)
    p.add(R("add", 23, 20, 22), SW(27, 23, 0), I("addi", 22, 22, 4))
    p.add(BRANCH("bne", 22, 21, recibir - p.pc))
    p.add(I("addi", 22, 0, 0))
    enviar = p.pc
    p.add(R("add", 23, 20, 22), LOAD("lw", 27, 23, 0))
    p.putc(27)
    p.add(I("addi", 22, 22, 4))
    p.add(BRANCH("bne", 22, 21, enviar - p.pc))
    fin = p.fin()
    chip = await start(dut, p)
    await chip.uart.send(mensaje)
    await chip.run_until(fin, max_cycles=3_000_000)
    await chip.uart.wait(12)
    guardado = bytes(chip.ram.word(4 * k) & 0xFF for k in range(len(mensaje)))
    assert guardado == mensaje, f"en la RAM quedó {guardado!r}"
    assert chip.uart.received == mensaje, f"se reenvió {bytes(chip.uart.received)!r}"


@cocotb.test()
async def test_interrupcion(dut):
    """Con MIE = 0 un pulso en IRQ no interrumpe (queda pendiente). Al habilitar MIE
    se atiende, y un segundo pulso se atiende otra vez. La rutina (en mtvec) suma 1 a
    x11, enciende el LED, guarda mepc en x12 y vuelve con MRET."""
    isr = 0x200
    p = Programa()
    p.add(I("addi", 10, 0, 0), I("addi", 11, 0, 0), LI(8, UART), LI(5, isr),
          CSRRW(0, MTVEC, 5))
    espera = p.pc                                 # interrupciones deshabilitadas
    p.add(I("addi", 10, 10, 1), I("addi", 6, 0, 30), BRANCH("bne", 10, 6, -8))
    deshabilitadas = p.pc
    p.add(I("addi", 7, 0, 8), CSRRS(0, MSTATUS, 7))          # MIE = 1
    principal = p.pc
    p.add(I("addi", 10, 10, 1), I("addi", 6, 0, 2), BRANCH("bne", 11, 6, -8))
    fin = p.fin()
    p.pc = isr                                    # rutina de atención
    p.add(I("addi", 11, 11, 1), I("addi", 9, 0, LED), SW(9, 8, 0x10),
          CSRRS(12, MEPC, 0), MRET)

    chip = await start(dut, p)
    await chip.run_until(espera + 4)
    await pulso_irq(dut)
    await chip.run_until(deshabilitadas)
    assert chip.reg(11) == 0, "se atendió la IRQ con las interrupciones deshabilitadas"
    await chip.run_until(principal + 8)
    await ClockCycles(dut.clk, 2000)
    assert chip.reg(11) == 1, "la IRQ pendiente no se atendió al habilitar MIE"
    assert value(dut.led) == 1, "la rutina no encendió el LED"
    await pulso_irq(dut)
    await chip.run_until(fin)
    assert chip.reg(11) == 2, f"la rutina corrió {chip.reg(11)} veces, se esperaban 2"
    assert principal <= chip.reg(12) <= principal + 8, f"mepc = 0x{chip.reg(12):x}"


async def pulso_irq(dut):
    """Pulso de 4 ciclos en la entrada IRQ."""
    dut.irq.value = 1
    await ClockCycles(dut.clk, 4)
    dut.irq.value = 0


def texto(p, cadena):
    """Agrega al programa el envío por la UART de cada byte de `cadena` (usa x27)."""
    for c in cadena:
        p.add(I("addi", 27, 0, c))
        p.putc(27)


def programa_fpga():
    """Programa de prueba de la FPGA (el que se carga en el emulador de flash).

    1. Envía "femto_UN FPGA" (flash y UART).
    2. Guarda "Hello World " en la RAM (3 palabras), la vuelve a leer y la envía
       (escritura y lectura de la RAM).
    3. Habilita las interrupciones, envía "Esperando IRQ..." y queda en un bucle.
    Rutina de atención (mtvec = 0x800): suma 1 al contador x11 (de 0 a 9), envía
    "IRQ n", cambia el estado del LED (guardado en x12) y vuelve con MRET. El LED se
    escribe después del texto porque putc usa el mismo registro de control.
    """
    isr = 0x800
    p = Programa()
    p.add(LI(8, UART), LI(20, RAM), I("addi", 11, 0, 0), I("addi", 12, 0, 0),
          LI(5, isr), CSRRW(0, MTVEC, 5))
    texto(p, b"femto_UN FPGA\r\n")
    frase = b"Hello World "
    for k in range(0, 12, 4):                                    # escribe en la RAM
        p.add(LI(2, int.from_bytes(frase[k:k + 4], "little")), SW(2, 20, k))
    for k in range(12):                                          # lee y envía
        p.add(LOAD("lbu", 27, 20, k))
        p.putc(27)
    texto(p, b"\r\nEsperando IRQ...\r\n")
    p.add(I("addi", 7, 0, 8), CSRRS(0, MSTATUS, 7))              # MIE = 1
    espera = p.pc
    p.add(JAL(0, 0))                                             # bucle principal
    assert p.pc <= isr, "el programa principal se cruza con la rutina de atención"
    p.pc = isr
    p.add(I("addi", 11, 11, 1), I("addi", 6, 0, 10), BRANCH("bne", 11, 6, 8),
          I("addi", 11, 0, 0))                                   # contador de 0 a 9
    texto(p, b"IRQ ")
    p.add(I("addi", 27, 11, ord("0")))
    p.putc(27)
    texto(p, b"\r\n")
    p.add(I("xori", 12, 12, LED), SW(12, 8, 0x10), MRET)         # cambia el LED
    return p, espera


SALUDO = b"femto_UN FPGA\r\nHello World \r\nEsperando IRQ...\r\n"


@cocotb.test()
async def test_programa_fpga(dut):
    """Corre el programa de prueba de la FPGA y lo guarda en
    build/cocotb/programa_fpga.bin (para el emulador de flash del ESP32-C6).

    Revisa el saludo, la frase leída de la RAM y dos interrupciones: una larga (2 ms
    en 1, como un pulsador presionado) que debe producir una sola "IRQ 1" y encender
    el LED, y un pulso corto que produce "IRQ 2" y apaga el LED."""
    p, espera = programa_fpga()
    with open("build/cocotb/programa_fpga.bin", "wb") as f:
        f.write(p.imagen())
    chip = await start(dut, p)
    await chip.run_until(espera, max_cycles=5_000_000)
    await chip.uart.wait(12)
    assert chip.uart.received == SALUDO, bytes(chip.uart.received)

    dut.irq.value = 1                                            # pulsación larga
    await Timer(2, unit="ms")
    dut.irq.value = 0
    await chip.run_until(espera, max_cycles=3_000_000)
    await chip.uart.wait(12)
    assert chip.uart.received[len(SALUDO):] == b"IRQ 1\r\n", bytes(chip.uart.received)
    assert value(dut.led) == 1, "el LED no se encendió"

    await pulso_irq(dut)                                         # pulso corto
    await ClockCycles(dut.clk, 100)
    await chip.run_until(espera, max_cycles=3_000_000)
    await chip.uart.wait(12)
    assert chip.uart.received[len(SALUDO):] == b"IRQ 1\r\nIRQ 2\r\n", \
        bytes(chip.uart.received)
    assert value(dut.led) == 0, "el LED no se apagó"
