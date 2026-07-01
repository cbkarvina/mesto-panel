#!/usr/bin/env python3
import errno

from smbus2 import SMBus
from gpio_interface import GPIODevice, INPUT, OUTPUT, LOW, HIGH, PUD_OFF, PUD_UP

# MCP23017 I/O Expander Register Map (BANK=0 mode)
# The MCP23017 has 16 GPIO pins split into two 8-bit ports: A and B
IODIRA = 0x00  # I/O Direction Register A: 1=input, 0=output
IODIRB = 0x01  # I/O Direction Register B: 1=input, 0=output
IOCON  = 0x0A  # I/O Configuration Register
GPPUA  = 0x0C  # GPIO Pull-Up Resistor A: 1=enabled, 0=disabled
GPPUB  = 0x0D  # GPIO Pull-Up Resistor B: 1=enabled, 0=disabled
GPIOA  = 0x12  # GPIO Register A: Read current pin states
GPIOB  = 0x13  # GPIO Register B: Read current pin states
OLATA  = 0x14  # Output Latch A: Write to set output values
OLATB  = 0x15  # Output Latch B: Write to set output values


class MCP23017Error(RuntimeError):
    pass


class MCP23017(GPIODevice):
    def __init__(self, address=0x20, busnum=1):
        """Initialize MCP23017 on specified I2C address and bus."""
        self.address = address
        self.busnum = busnum

        # Connect to I2C bus
        try:
            self.bus = SMBus(busnum)
        except OSError as exc:
            raise MCP23017Error(
                f"Failed to open I2C bus {busnum}: {self._format_oserror(exc)}"
            ) from exc

        # Configure MCP23017:
        # 0x20: SEQOP bit - disable sequential mode (address auto-increment)
        # 0x40: MIRROR bit - mirror interrupts to both INT pins
        IOCON_INIT = 0x20 | 0x40
        self.write_reg(IOCON, IOCON_INIT)

        # Cache the current output state of both ports to avoid read-modify-write errors
        # This ensures digital_write() uses the correct current state
        self.olat_a = self.read_reg(OLATA)
        self.olat_b = self.read_reg(OLATB)

    def close(self):
        self.bus.close()

    def _format_oserror(self, exc: OSError) -> str:
        details = f"[Errno {exc.errno}] {exc.strerror}"

        if exc.errno in (errno.EIO, errno.EREMOTEIO):
            return (
                f"{details}. Check that the MCP23017 is powered, wired to SDA/SCL, "
                f"visible on I2C bus {self.busnum}, and configured at address 0x{self.address:02X}. "
                f"Probe with: i2cdetect -y {self.busnum}"
            )

        return details

    def _raise_io_error(self, operation: str, reg: int, exc: OSError):
        raise MCP23017Error(
            f"MCP23017 {operation} failed at address 0x{self.address:02X}, "
            f"register 0x{reg:02X} on I2C bus {self.busnum}: {self._format_oserror(exc)}"
        ) from exc

    def write_reg(self, reg, value):
        try:
            self.bus.write_byte_data(self.address, reg, value & 0xFF)
        except OSError as exc:
            self._raise_io_error("write", reg, exc)

    def read_reg(self, reg):
        try:
            return self.bus.read_byte_data(self.address, reg)
        except OSError as exc:
            self._raise_io_error("read", reg, exc)

    def _pin_to_reg_and_bit(self, pin, reg_a, reg_b):
        """Convert pin number (0-15) to port register and bit position.
        
        Pins 0-7 use port A, pins 8-15 use port B.
        """
        if not (0 <= pin <= 15):
            raise ValueError("Pin must be 0..15")
        if pin < 8:
            return reg_a, pin  # Port A: bits 0-7
        return reg_b, pin - 8  # Port B: bits 0-7 (pin 8-15 map to bits 0-7)

    def pin_mode(self, pin, mode):
        """Set pin as INPUT (1) or OUTPUT (0)."""
        reg, bit = self._pin_to_reg_and_bit(pin, IODIRA, IODIRB)
        mask = 1 << bit
        value = self.read_reg(reg)
        if mode == OUTPUT:
            # Clear bit = output
            value &= ~mask
        else:
            # Set bit = input
            value |= mask
        self.write_reg(reg, value)

    def pull_up(self, pin, mode):
        reg, bit = self._pin_to_reg_and_bit(pin, GPPUA, GPPUB)
        mask = 1 << bit
        value = self.read_reg(reg)
        if mode == PUD_UP:
            value |= mask
        else:
            value &= ~mask
        self.write_reg(reg, value)

    def digital_read(self, pin):
        """Read current state of a pin: HIGH (1) or LOW (0)."""
        reg, bit = self._pin_to_reg_and_bit(pin, GPIOA, GPIOB)
        value = self.read_reg(reg)  # Read entire port register
        # Extract the bit for this pin
        return HIGH if (value & (1 << bit)) else LOW

    def read_pin_pair(self, pin_a, pin_b):
        """Read two pins atomically when they share a port.

        Both pins on the same MCP23017 port are captured in a single register
        read, so the A/B lines of a quadrature encoder are sampled at the same
        instant (no torn reads). Falls back to two reads when the pins are on
        different ports.
        """
        reg_a, bit_a = self._pin_to_reg_and_bit(pin_a, GPIOA, GPIOB)
        reg_b, bit_b = self._pin_to_reg_and_bit(pin_b, GPIOA, GPIOB)
        if reg_a == reg_b:
            value = self.read_reg(reg_a)
            return (
                HIGH if (value & (1 << bit_a)) else LOW,
                HIGH if (value & (1 << bit_b)) else LOW,
            )
        return self.digital_read(pin_a), self.digital_read(pin_b)

    def digital_write(self, pin, state):
        """Write a value to an output pin: HIGH (1) or LOW (0)."""
        if pin < 8:
            # Port A (pins 0-7)
            bit = 1 << pin
            value = self.olat_a
            if state:
                value |= bit  # Set bit high
            else:
                value &= ~bit  # Set bit low
            self.write_reg(GPIOA, value)
            self.olat_a = value  # Cache for next write
        else:
            # Port B (pins 8-15)
            bit = 1 << (pin - 8)
            value = self.olat_b
            if state:
                value |= bit  # Set bit high
            else:
                value &= ~bit  # Set bit low
            self.write_reg(GPIOB, value)
            self.olat_b = value  # Cache for next write

    def setup_input_pullup(self, pin):
        self.pin_mode(pin, INPUT)
        self.pull_up(pin, PUD_UP)

    def setup_output(self, pin, initial=LOW):
        self.pin_mode(pin, OUTPUT)
        self.digital_write(pin, initial)