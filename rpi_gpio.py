#!/usr/bin/env python3
"""
RPi GPIO wrapper that provides the same interface as MCP23017.
This allows the same code to work with either MCP23017 or native RPi GPIO pins.

Supports Raspberry Pi 400 and other RPi models.
"""

try:
    import RPi.GPIO as GPIO
except ImportError:
    raise ImportError(
        "RPi.GPIO is required. Install with: pip install RPi.GPIO"
    )

from gpio_interface import GPIODevice, INPUT, OUTPUT, LOW, HIGH, PUD_OFF, PUD_UP


class RpiGPIOError(RuntimeError):
    pass


class RpiGPIO(GPIODevice):
    """
    A GPIO wrapper for Raspberry Pi that provides the same interface as MCP23017.
    This enables code to work with either native GPIO or the MCP23017 expander.
    """

    def __init__(self, address=None, busnum=None):
        """
        Initialize RPi GPIO.
        
        Args:
            address: Ignored, kept for API compatibility with MCP23017
            busnum: Ignored, kept for API compatibility with MCP23017
        """
        try:
            # Set up GPIO in BCM mode
            if GPIO.getmode() is None:
                GPIO.setmode(GPIO.BCM)
        except RuntimeError as exc:
            raise RpiGPIOError(
                f"Failed to initialize GPIO: {exc}. "
                "This typically means the script needs to be run as root/sudo."
            ) from exc

        # Track pin configuration to manage state
        self._pin_modes = {}  # pin -> INPUT/OUTPUT
        self._pin_pullups = {}  # pin -> PUD_UP/PUD_OFF
        self._pin_states = {}  # pin -> LOW/HIGH (for output pins)

    def close(self):
        """Clean up GPIO resources."""
        try:
            GPIO.cleanup()
        except RuntimeError as exc:
            raise RpiGPIOError(f"Failed to cleanup GPIO: {exc}") from exc

    def write_reg(self, reg, value):
        """
        Not used for direct GPIO. Kept for API compatibility.
        Raises NotImplementedError.
        """
        raise NotImplementedError(
            "write_reg is not applicable to native GPIO. "
            "Use digital_write() instead."
        )

    def read_reg(self, reg):
        """
        Not used for direct GPIO. Kept for API compatibility.
        Raises NotImplementedError.
        """
        raise NotImplementedError(
            "read_reg is not applicable to native GPIO. "
            "Use digital_read() instead."
        )

    def pin_mode(self, pin, mode):
        """
        Configure a GPIO pin as INPUT or OUTPUT.
        
        Args:
            pin: GPIO pin number (BCM numbering)
            mode: INPUT (1) or OUTPUT (0)
        """
        if mode not in (INPUT, OUTPUT):
            raise ValueError(f"Invalid mode: {mode}. Use INPUT (1) or OUTPUT (0)")

        try:
            if mode == INPUT:
                GPIO.setup(pin, GPIO.IN)
            else:
                GPIO.setup(pin, GPIO.OUT)
            self._pin_modes[pin] = mode
        except RuntimeError as exc:
            raise RpiGPIOError(
                f"Failed to set pin {pin} mode: {exc}"
            ) from exc

    def pull_up(self, pin, mode):
        """
        Configure pull-up/pull-down resistor for a GPIO pin.
        
        Args:
            pin: GPIO pin number (BCM numbering)
            mode: PUD_UP (1) to enable pull-up, PUD_OFF (0) to disable
        """
        if mode not in (PUD_UP, PUD_OFF):
            raise ValueError(
                f"Invalid pull-up mode: {mode}. Use PUD_UP (1) or PUD_OFF (0)"
            )

        try:
            # Re-setup pin with pull-up configuration
            if self._pin_modes.get(pin) == INPUT:
                if mode == PUD_UP:
                    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                else:
                    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_OFF)
            self._pin_pullups[pin] = mode
        except RuntimeError as exc:
            raise RpiGPIOError(
                f"Failed to set pull-up for pin {pin}: {exc}"
            ) from exc

    def digital_read(self, pin):
        """
        Read the current state of a GPIO pin.
        
        Args:
            pin: GPIO pin number (BCM numbering)
            
        Returns:
            HIGH (1) or LOW (0)
        """
        try:
            state = GPIO.input(pin)
            return HIGH if state else LOW
        except RuntimeError as exc:
            raise RpiGPIOError(
                f"Failed to read pin {pin}: {exc}"
            ) from exc

    def digital_write(self, pin, state):
        """
        Write a value to a GPIO output pin.
        
        Args:
            pin: GPIO pin number (BCM numbering)
            state: HIGH (1) or LOW (0)
        """
        if state not in (HIGH, LOW):
            raise ValueError(f"Invalid state: {state}. Use HIGH (1) or LOW (0)")

        try:
            GPIO.output(pin, state)
            self._pin_states[pin] = state
        except RuntimeError as exc:
            raise RpiGPIOError(
                f"Failed to write to pin {pin}: {exc}"
            ) from exc

    def setup_input_pullup(self, pin):
        """
        Configure a GPIO pin as INPUT with pull-up enabled.
        
        This is a convenience method combining pin_mode and pull_up.
        
        Args:
            pin: GPIO pin number (BCM numbering)
        """
        self.pin_mode(pin, INPUT)
        self.pull_up(pin, PUD_UP)

    def setup_output(self, pin, initial=LOW):
        """
        Configure a GPIO pin as OUTPUT with an initial value.
        
        This is a convenience method combining pin_mode and digital_write.
        
        Args:
            pin: GPIO pin number (BCM numbering)
            initial: Initial state, HIGH (1) or LOW (0), defaults to LOW
        """
        self.pin_mode(pin, OUTPUT)
        self.digital_write(pin, initial)
