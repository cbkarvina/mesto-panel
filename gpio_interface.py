#!/usr/bin/env python3
"""
Common interface for GPIO devices.

This module defines an abstract base class that both MCP23017 (I2C expander)
and RpiGPIO (native Raspberry Pi GPIO) implement. This allows the same code
to work with either interface.
"""

from abc import ABC, abstractmethod

# Constants used across all GPIO interfaces
INPUT = 1
OUTPUT = 0
LOW = 0
HIGH = 1

PUD_OFF = 0
PUD_UP = 1


class GPIODevice(ABC):
    """
    Abstract base class for GPIO device interfaces.
    
    Defines the contract that all GPIO implementations must follow,
    enabling drop-in replacement between different GPIO providers
    (e.g., MCP23017, native RPi GPIO, other expanders).
    """

    @abstractmethod
    def close(self):
        """
        Close/cleanup the GPIO device.
        
        Should release any resources (I2C bus, GPIO cleanup, etc.)
        """
        pass

    @abstractmethod
    def pin_mode(self, pin: int, mode: int):
        """
        Configure a pin as INPUT or OUTPUT.
        
        Args:
            pin: Pin number (varies by device: 0-15 for MCP23017, BCM for RPi)
            mode: INPUT (1) or OUTPUT (0)
        """
        pass

    @abstractmethod
    def pull_up(self, pin: int, mode: int):
        """
        Configure pull-up/pull-down resistor for a pin.
        
        Args:
            pin: Pin number
            mode: PUD_UP (1) to enable, PUD_OFF (0) to disable
        """
        pass

    @abstractmethod
    def digital_read(self, pin: int) -> int:
        """
        Read the current state of a pin.
        
        Args:
            pin: Pin number
            
        Returns:
            HIGH (1) or LOW (0)
        """
        pass

    @abstractmethod
    def digital_write(self, pin: int, state: int):
        """
        Write a value to an output pin.
        
        Args:
            pin: Pin number
            state: HIGH (1) or LOW (0)
        """
        pass

    @abstractmethod
    def setup_input_pullup(self, pin: int):
        """
        Configure a pin as INPUT with pull-up enabled (convenience method).
        
        Equivalent to:
            pin_mode(pin, INPUT)
            pull_up(pin, PUD_UP)
        
        Args:
            pin: Pin number
        """
        pass

    @abstractmethod
    def setup_output(self, pin: int, initial: int = LOW):
        """
        Configure a pin as OUTPUT with initial value (convenience method).
        
        Equivalent to:
            pin_mode(pin, OUTPUT)
            digital_write(pin, initial)
        
        Args:
            pin: Pin number
            initial: Initial state, HIGH (1) or LOW (0), defaults to LOW
        """
        pass

    # Optional methods for register access (primarily for MCP23017)
    def read_pin_pair(self, pin_a: int, pin_b: int):
        """
        Read two pins as close together in time as possible.

        Returns a (state_a, state_b) tuple. The default implementation issues
        two separate reads; devices that can sample several pins in a single
        transaction (e.g. MCP23017 port register) should override this so that
        both pins are captured atomically. This matters for quadrature encoders
        where a torn read of the A/B lines looks like an illegal transition.

        Args:
            pin_a: First pin number
            pin_b: Second pin number

        Returns:
            Tuple (state_a, state_b), each HIGH (1) or LOW (0)
        """
        return self.digital_read(pin_a), self.digital_read(pin_b)

    def write_reg(self, reg: int, value: int):
        """
        Write to a device register (optional, not all devices support this).
        
        Args:
            reg: Register address
            value: Value to write
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support write_reg()"
        )

    def read_reg(self, reg: int) -> int:
        """
        Read from a device register (optional, not all devices support this).
        
        Args:
            reg: Register address
            
        Returns:
            Value read from register
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support read_reg()"
        )
