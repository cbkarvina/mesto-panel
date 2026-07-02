#!/usr/bin/env python3
from typing import Dict, List

try:
    import spidev
except ImportError:
    spidev = None


class Max7219DisplayError(RuntimeError):
    pass


class Max7219Chain:
    """Shared SPI line for daisy-chained MAX7219 modules (single CS).

    Modules are wired DOUT -> DIN in series. module_index 0 is the module
    closest to the Pi's MOSI (first to receive data); the last index is the
    farthest module. To address one module the full chain must be clocked in a
    single CS pulse, sending NO-OP (0x00) to every other module.
    """

    _REG_NOOP = 0x00

    def __init__(self, bus: int = 0, device: int = 0, num_modules: int = 2,
                 max_speed_hz: int = 1000000):
        if spidev is None:
            raise Max7219DisplayError("spidev is required. Install with: pip install spidev")
        if num_modules < 1:
            raise ValueError("num_modules must be >= 1")

        self.num_modules = num_modules
        self.spi = spidev.SpiDev()
        try:
            self.spi.open(bus, device)
        except FileNotFoundError as exc:
            raise Max7219DisplayError(
                f"SPI device /dev/spidev{bus}.{device} not found. Enable SPI interface first."
            ) from exc
        except PermissionError as exc:
            raise Max7219DisplayError(
                f"No permission for /dev/spidev{bus}.{device}. Run with sudo or fix udev rules."
            ) from exc
        except OSError as exc:
            raise Max7219DisplayError(f"Failed to open SPI bus={bus} device={device}: {exc}") from exc

        self.spi.max_speed_hz = max_speed_hz
        self.spi.mode = 0
        self.spi.bits_per_word = 8

    def write(self, module_index: int, reg: int, data: int):
        if module_index < 0 or module_index >= self.num_modules:
            raise ValueError(f"module_index must be in range 0..{self.num_modules - 1}")
        frame = []
        # Farthest module is clocked first so each word ends up in its module.
        for i in reversed(range(self.num_modules)):
            if i == module_index:
                frame += [reg & 0xFF, data & 0xFF]
            else:
                frame += [self._REG_NOOP, 0x00]
        self.spi.xfer2(frame)

    def close(self):
        self.spi.close()


# 8x8 glyphs, one byte per row (MSB is leftmost pixel)
GLYPHS: Dict[str, List[int]] = {
    " ": [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
    "-": [0x00, 0x00, 0x00, 0x7E, 0x00, 0x00, 0x00, 0x00],
    "0": [0x3C, 0x66, 0x6E, 0x76, 0x66, 0x66, 0x3C, 0x00],
    "1": [0x18, 0x38, 0x18, 0x18, 0x18, 0x18, 0x7E, 0x00],
    "2": [0x3C, 0x66, 0x06, 0x0C, 0x30, 0x60, 0x7E, 0x00],
    "3": [0x3C, 0x66, 0x06, 0x1C, 0x06, 0x66, 0x3C, 0x00],
    "4": [0x0C, 0x1C, 0x2C, 0x4C, 0x7E, 0x0C, 0x0C, 0x00],
    "5": [0x7E, 0x60, 0x7C, 0x06, 0x06, 0x66, 0x3C, 0x00],
    "6": [0x1C, 0x30, 0x60, 0x7C, 0x66, 0x66, 0x3C, 0x00],
    "7": [0x7E, 0x66, 0x0C, 0x18, 0x18, 0x18, 0x18, 0x00],
    "8": [0x3C, 0x66, 0x66, 0x3C, 0x66, 0x66, 0x3C, 0x00],
    "9": [0x3C, 0x66, 0x66, 0x3E, 0x06, 0x0C, 0x38, 0x00],
    "A": [0x18, 0x3C, 0x66, 0x66, 0x7E, 0x66, 0x66, 0x00],
    "B": [0x7C, 0x66, 0x66, 0x7C, 0x66, 0x66, 0x7C, 0x00],
    "C": [0x3C, 0x66, 0x60, 0x60, 0x60, 0x66, 0x3C, 0x00],
    "D": [0x78, 0x6C, 0x66, 0x66, 0x66, 0x6C, 0x78, 0x00],
    "E": [0x7E, 0x60, 0x60, 0x7C, 0x60, 0x60, 0x7E, 0x00],
    "F": [0x7E, 0x60, 0x60, 0x7C, 0x60, 0x60, 0x60, 0x00],
    "G": [0x3C, 0x66, 0x60, 0x6E, 0x66, 0x66, 0x3C, 0x00],
    "H": [0x66, 0x66, 0x66, 0x7E, 0x66, 0x66, 0x66, 0x00],
    "I": [0x3C, 0x18, 0x18, 0x18, 0x18, 0x18, 0x3C, 0x00],
    "J": [0x1E, 0x0C, 0x0C, 0x0C, 0x6C, 0x6C, 0x38, 0x00],
}


# 10 "interesting" 8x8 symbols the code encoders cycle through.
# One byte per row, MSB is the leftmost pixel. Order defines the index (0..9).
SYMBOLS: List[List[int]] = [
    [0x00, 0x66, 0xFF, 0xFF, 0x7E, 0x3C, 0x18, 0x00],  # 0 heart
    [0x3C, 0x42, 0xA5, 0x81, 0xA5, 0x99, 0x42, 0x3C],  # 1 smiley
    [0x18, 0x3C, 0xFF, 0x7E, 0x3C, 0x66, 0xC3, 0x00],  # 2 star
    [0x3C, 0x7E, 0xDB, 0xFF, 0x7E, 0x3C, 0x24, 0x00],  # 3 skull
    [0x1C, 0x38, 0x70, 0xFE, 0x0E, 0x1C, 0x38, 0x30],  # 4 lightning
    [0x18, 0x3C, 0x7E, 0xFF, 0x18, 0x18, 0x18, 0x00],  # 5 arrow up
    [0x1C, 0x22, 0x22, 0x1C, 0x08, 0x0E, 0x08, 0x0E],  # 6 key
    [0x00, 0x3C, 0x42, 0x99, 0x99, 0x42, 0x3C, 0x00],  # 7 eye
    [0xFF, 0x7E, 0x3C, 0x18, 0x18, 0x3C, 0x7E, 0xFF],  # 8 hourglass
    [0x06, 0x0E, 0x0A, 0x0A, 0x0A, 0x38, 0x78, 0x30],  # 9 music note
]


class Max7219Display:
    # MAX7219 registers
    _REG_NOOP = 0x00
    _REG_DIGIT0 = 0x01
    _REG_DECODE_MODE = 0x09
    _REG_INTENSITY = 0x0A
    _REG_SCAN_LIMIT = 0x0B
    _REG_SHUTDOWN = 0x0C
    _REG_DISPLAY_TEST = 0x0F

    def __init__(self, bus: int = 0, device: int = 0, intensity: int = 4,
                 max_speed_hz: int = 1000000, chain: "Max7219Chain" = None,
                 module_index: int = 0, rotate180: bool = False):
        self._rotate180 = rotate180
        if chain is not None:
            self._chain = chain
            self._module_index = module_index
            self._owns_spi = False
            self.spi = None
        else:
            if spidev is None:
                raise Max7219DisplayError("spidev is required. Install with: pip install spidev")

            self.spi = spidev.SpiDev()
            try:
                self.spi.open(bus, device)
            except FileNotFoundError as exc:
                raise Max7219DisplayError(
                    f"SPI device /dev/spidev{bus}.{device} not found. Enable SPI interface first."
                ) from exc
            except PermissionError as exc:
                raise Max7219DisplayError(
                    f"No permission for /dev/spidev{bus}.{device}. Run with sudo or fix udev rules."
                ) from exc
            except OSError as exc:
                raise Max7219DisplayError(f"Failed to open SPI bus={bus} device={device}: {exc}") from exc

            self.spi.max_speed_hz = max_speed_hz
            self.spi.mode = 0
            self.spi.bits_per_word = 8
            self._chain = None
            self._module_index = 0
            self._owns_spi = True

        self._rows = [0x00] * 8
        self._init_chip(intensity)

    def _write_reg(self, reg: int, data: int):
        if self._chain is not None:
            self._chain.write(self._module_index, reg, data)
        else:
            self.spi.xfer2([reg & 0xFF, data & 0xFF])

    def _init_chip(self, intensity: int):
        self._write_reg(self._REG_SHUTDOWN, 0x00)      # shutdown while configuring
        self._write_reg(self._REG_DISPLAY_TEST, 0x00)  # display test off
        self._write_reg(self._REG_DECODE_MODE, 0x00)   # matrix mode (no BCD decode)
        self._write_reg(self._REG_SCAN_LIMIT, 0x07)    # scan all 8 digits/rows
        self.set_intensity(intensity)
        self.clear(show=False)
        self._write_reg(self._REG_SHUTDOWN, 0x01)      # normal operation
        self.show()

    def set_intensity(self, value: int):
        value = max(0, min(15, value))
        self._write_reg(self._REG_INTENSITY, value)

    def clear(self, show: bool = True):
        self._rows = [0x00] * 8
        if show:
            self.show()

    def show(self):
        for row_idx, row_value in enumerate(self._rows, start=1):
            self._write_reg(self._REG_DIGIT0 + row_idx - 1, row_value)

    def set_rows(self, rows: List[int], show: bool = True):
        if len(rows) != 8:
            raise ValueError("rows must have exactly 8 values")
        rows = [r & 0xFF for r in rows]
        if self._rotate180:
            # 180° rotation = reverse row order + mirror each row horizontally.
            rows = [self._reverse_byte(r) for r in reversed(rows)]
        self._rows = rows
        if show:
            self.show()

    @staticmethod
    def _reverse_byte(value: int) -> int:
        result = 0
        for _ in range(8):
            result = (result << 1) | (value & 1)
            value >>= 1
        return result

    def set_char(self, char: str, show: bool = True):
        c = (char or " ")[0].upper()
        rows = GLYPHS.get(c, GLYPHS[" "])
        self.set_rows(rows, show=show)

    def set_index_letter(self, index: int, show: bool = True):
        # 0=A ... 9=J
        letter = chr(ord("A") + (index % 10))
        self.set_char(letter, show=show)

    def set_index_symbol(self, index: int, show: bool = True):
        # Cycle through the 10 custom SYMBOLS glyphs (0..9).
        rows = SYMBOLS[index % len(SYMBOLS)]
        self.set_rows(rows, show=show)

    def close(self):
        try:
            self.clear(show=True)
        finally:
            if self._owns_spi and self.spi is not None:
                self.spi.close()


# 7-segment bit map: DP G F E D C B A
# Bit order matches MAX7219 no-decode hardware: DP G F E D C B A -> wrong.
# Correct datasheet no-decode order is: bit7=DP, bit6=A, bit5=B, bit4=C,
# bit3=D, bit2=E, bit1=F, bit0=G.
SEGMENTS_7SEG: Dict[str, int] = {
    " ": 0x00,
    "-": 0x01,
    "_": 0x08,
    "0": 0x7E,
    "1": 0x30,
    "2": 0x6D,
    "3": 0x79,
    "4": 0x33,
    "5": 0x5B,
    "6": 0x5F,
    "7": 0x70,
    "8": 0x7F,
    "9": 0x7B,
    "A": 0x77,
    "B": 0x1F,
    "C": 0x4E,
    "D": 0x3D,
    "E": 0x4F,
    "F": 0x47,
    "G": 0x5E,
    "H": 0x37,
    "I": 0x30,
    "J": 0x3C,
    "K": 0x37,
    "L": 0x0E,
    "N": 0x15,
    "O": 0x7E,
    "P": 0x67,
    "R": 0x05,
    "S": 0x5B,
    "T": 0x0F,
    "U": 0x3E,
    "Y": 0x3B,
}


class Max7219SevenSegDisplay:
    """
    MAX7219 driver for 8-character 7-segment display modules.

    Each character has 8 controllable bits:
        - 7 segments: A, B, C, D, E, F, G
        - 1 decimal point: DP

    Bit order in each digit byte: DP A B C D E F G
    """

    # MAX7219 registers
    _REG_DIGIT0 = 0x01
    _REG_DECODE_MODE = 0x09
    _REG_INTENSITY = 0x0A
    _REG_SCAN_LIMIT = 0x0B
    _REG_SHUTDOWN = 0x0C
    _REG_DISPLAY_TEST = 0x0F

    def __init__(self, bus: int = 1, device: int = 0, intensity: int = 4,
                 max_speed_hz: int = 1000000, chain: "Max7219Chain" = None,
                 module_index: int = 0):
        if chain is not None:
            self._chain = chain
            self._module_index = module_index
            self._owns_spi = False
            self.spi = None
        else:
            if spidev is None:
                raise Max7219DisplayError("spidev is required. Install with: pip install spidev")

            self.spi = spidev.SpiDev()
            try:
                self.spi.open(bus, device)
            except FileNotFoundError as exc:
                raise Max7219DisplayError(
                    f"SPI device /dev/spidev{bus}.{device} not found. Enable SPI interface first."
                ) from exc
            except PermissionError as exc:
                raise Max7219DisplayError(
                    f"No permission for /dev/spidev{bus}.{device}. Run with sudo or fix udev rules."
                ) from exc
            except OSError as exc:
                raise Max7219DisplayError(f"Failed to open SPI bus={bus} device={device}: {exc}") from exc

            self.spi.max_speed_hz = max_speed_hz
            self.spi.mode = 0
            self.spi.bits_per_word = 8
            self._chain = None
            self._module_index = 0
            self._owns_spi = True

        self._digits = [0x00] * 8
        self._init_chip(intensity)

    def _write_reg(self, reg: int, data: int):
        if self._chain is not None:
            self._chain.write(self._module_index, reg, data)
        else:
            self.spi.xfer2([reg & 0xFF, data & 0xFF])

    def _init_chip(self, intensity: int):
        self._write_reg(self._REG_SHUTDOWN, 0x00)      # shutdown while configuring
        self.set_display_test(False)
        self.set_decode_mode(0x00)                     # raw segment mode by default
        self._write_reg(self._REG_SCAN_LIMIT, 0x07)    # all 8 digits enabled
        self.set_intensity(intensity)
        self.clear(show=False)
        self._write_reg(self._REG_SHUTDOWN, 0x01)      # normal operation
        self.show()

    def set_intensity(self, value: int):
        value = max(0, min(15, value))
        self._write_reg(self._REG_INTENSITY, value)

    def set_decode_mode(self, mask: int):
        """Set Code-B decode mask (bit per digit, 1=decode, 0=raw)."""
        self._write_reg(self._REG_DECODE_MODE, mask & 0xFF)

    def set_display_test(self, enabled: bool):
        """Enable/disable global display-test mode (all LEDs on)."""
        self._write_reg(self._REG_DISPLAY_TEST, 0x01 if enabled else 0x00)

    def clear(self, show: bool = True):
        self._digits = [0x00] * 8
        if show:
            self.show()

    def show(self):
        # Module wiring is reversed: DIGIT0 register = rightmost physical digit.
        # Map self._digits[0] to the leftmost digit so text reads left-to-right.
        for i, value in enumerate(self._digits):
            self._write_reg(self._REG_DIGIT0 + (7 - i), value)

    @staticmethod
    def _segments_to_byte(
        a: bool,
        b: bool,
        c: bool,
        d: bool,
        e: bool,
        f: bool,
        g: bool,
        dp: bool = False,
    ) -> int:
        # MAX7219 no-decode segment bit map (datasheet):
        # bit7=DP, bit6=A, bit5=B, bit4=C, bit3=D, bit2=E, bit1=F, bit0=G
        value = 0
        if a:
            value |= 0x40
        if b:
            value |= 0x20
        if c:
            value |= 0x10
        if d:
            value |= 0x08
        if e:
            value |= 0x04
        if f:
            value |= 0x02
        if g:
            value |= 0x01
        if dp:
            value |= 0x80
        return value

    def set_segments(
        self,
        position: int,
        a: bool,
        b: bool,
        c: bool,
        d: bool,
        e: bool,
        f: bool,
        g: bool,
        dp: bool = False,
        show: bool = True,
    ):
        """Set one character by raw segments (7 lines + decimal point)."""
        if position < 0 or position > 7:
            raise ValueError("position must be in range 0..7")

        self._digits[position] = self._segments_to_byte(a, b, c, d, e, f, g, dp)
        if show:
            self.show()

    def set_digit(self, position: int, char: str, dot: bool = False, show: bool = True):
        if position < 0 or position > 7:
            raise ValueError("position must be in range 0..7")

        c = (char or " ")[0].upper()
        seg = SEGMENTS_7SEG.get(c, SEGMENTS_7SEG[" "])
        if dot:
            seg |= 0x80

        self._digits[position] = seg
        if show:
            self.show()

    def set_text(self, text: str, show: bool = True, right_align: bool = False):
        chars = list((text or "")[:8])
        if right_align:
            chars = [" "] * (8 - len(chars)) + chars
        else:
            chars = chars + [" "] * (8 - len(chars))

        # Use dot as suffix: "12.34" puts dot on previous digit.
        digits: List[int] = []
        for ch in chars:
            if ch == "." and digits:
                digits[-1] |= 0x80
                continue
            seg = SEGMENTS_7SEG.get(ch.upper(), SEGMENTS_7SEG[" "])
            digits.append(seg)

        if len(digits) < 8:
            digits.extend([0x00] * (8 - len(digits)))

        self._digits = digits[:8]
        if show:
            self.show()

    def set_number(self, value: int, show: bool = True):
        self.set_text(str(value), show=show, right_align=True)

    def set_morse(self, code: str, show: bool = True):
        """Render a morse string on the 7-seg display.

        '.' -> decimal point, '-' -> middle bar (segment G). One symbol per
        digit, left-aligned across the 8 digits. Anything else is blank.
        """
        digits: List[int] = []
        for ch in (code or "")[:8]:
            if ch == "-":
                digits.append(0x01)   # segment G (middle bar)
            elif ch == ".":
                digits.append(0x80)   # decimal point
            else:
                digits.append(0x00)
        digits.extend([0x00] * (8 - len(digits)))
        self._digits = digits[:8]
        if show:
            self.show()

    def set_bcd_digit(self, position: int, value: int, dot: bool = False, show: bool = True):
        """
        Write one digit using Code-B values.
        value: 0-9, 10='-', 11='E', 12='H', 13='L', 14='P', 15=blank
        """
        if position < 0 or position > 7:
            raise ValueError("position must be in range 0..7")
        if value < 0 or value > 15:
            raise ValueError("value must be in range 0..15")

        data = value | (0x80 if dot else 0x00)
        self._digits[position] = data
        if show:
            self.show()

    def close(self):
        try:
            self.clear(show=True)
        finally:
            if self._owns_spi and self.spi is not None:
                self.spi.close()
