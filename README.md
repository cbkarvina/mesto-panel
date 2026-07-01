## Elements

- RPI3B
- WS2812B - adresace led pasku
- 74AHCT125 - power shift pro led
- MCP23017 - i2c port expander
- MAX7219 - 8x8 panel (MAT)

# RPI GPIO pinout

| Pin | Value  | Connected  | Pin | Value  | Connected   |
| --- | ------ | ---------- | --- | ------ | ----------- |
| 1   | 3V3    | MCP + (r)  | 2   | 5V     | MAT VCC (r) |
| 3   | GPIO2  | MCP SDA 13 | 4   | 5V     | -           |
| 5   | GPIO3  | MCP SCL 12 | 6   | GND    | MCP GND (K) |
| 7   | GPIO4  | -          | 8   | GPIO14 | -           |
| 9   | GND    | -          | 10  | GPIO15 | -           |
| 11  | GPIO17 | -          | 12  | GPIO18 | LED +       |
| 13  | GPIO27 | -          | 14  | GND    | LED GND     |
| 15  | GPIO22 | -          | 16  | GPIO23 | -           |
| 17  | 3V3    | -          | 18  | GPIO24 | -           |
| 19  | GPIO10 | MAT Din(o) | 20  | GND    | MAT GND (b) |
| 21  | GPIO9  | -          | 22  | GPIO25 | -           |
| 23  | GPIO11 | MAT Clk(g) | 24  | GPIO8  | MAT Cs (y)  |
| 25  | GND    | -          | 26  | GPIO7  | -           |
| 27  | GPIO0  | -          | 28  | GPIO1  | -           |
| 29  | GPIO5  | -          | 30  | GND    | -           |
| 31  | GPIO6  | -          | 32  | GPIO12 | -           |
| 33  | GPIO19 | -          | 34  | GND    | -           |
| 35  | GPIO19 | -          | 36  | GPIO16 | -           |
| 37  | GPIO26 | -          | 38  | GPIO20 | -           |
| 39  | GND    | -          | 40  | GPIO21 | -           |

# Install

```
apt install python3-pip python3-venv i2c-tools
python -m venv env --system-site-packages
source env/bin/activate
pip3 install rpi_ws281x adafruit-circuitpython-neopixel adafruit-blinka smbus2
```

## Test matrix - MAX7219

```
sudo -E env PATH=$PATH python3 test_chain.py
sudo -E env PATH=$PATH python3 test_led2.py - not OK
```

## Test LED - single wire WS2812B protocol via 74AHCT125

see https://learn.adafruit.com/neopixels-on-raspberry-pi

```
vi /boot/config.txt (boot/firmware/config)
change dtparam=audio=on => off
sudo -E env PATH=$PATH python3 test_city_leds.py
```

## Test buttons - i2c

Default MCP23017 address: 0x20

Address lines A0, A1, A2 can be used to daisy-chain up to 8 MCP23017s:

```
0x20 (A0=0, A1=0, A2=0)
0x21 (A0=1, A1=0, A2=0)
0x22 (A0=0, A1=1, A2=0)
...
0x27 (A0=1, A1=1, A2=1)

i2cdetect -y 1
sudo -E env PATH=$PATH python3 testbuttons.py
```

## Quick run

```
cd ....
source env/bin/activate
sudo -E env PATH="$PATH" python3 main.py
```

# WIRING NOTES

- If using pull-up resistors: Set pullup=True (default)
  → Unpressed/open = HIGH (1)
  → Pressed/closed = LOW (0)

- If using external pull-up: Set pullup=False
  → Wire button between pin and GND
  → Wire 10kΩ pull-up from pin to +3.3V

- All inputs should connect to the input pin and GND for active-low logic
