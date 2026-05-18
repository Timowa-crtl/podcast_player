# Wiring

All pin numbers are **BCM GPIO** (not physical header positions). Use a Raspberry Pi pinout reference (e.g. `pinout` command or [pinout.xyz](https://pinout.xyz)) to map BCM numbers to physical pins.

I use dupont wires (no soldering) to keep things flexible.

## 12-Position Rotary Switch

One common pole wired to **GND**. Each of the 12 positions connects to one GPIO pin:

| Position | BCM GPIO |
| -------- | -------- |
| 1        | 4        |
| 2        | 18       |
| 3        | 22       |
| 4        | 23       |
| 5        | 9        |
| 6        | 21       |
| 7        | 5        |
| 8        | 6        |
| 9        | 12       |
| 10       | 13       |
| 11       | 16       |
| 12       | 20       |

## 3-Position Mode Switch

Common pole to **GND**. The two outer positions connect to GPIO pins; the center position leaves both pins floating (interpreted as PAUSED).

| Position | BCM GPIO | Meaning      |
| -------- | -------- | ------------ |
| Left     | 7        | Podcast play |
| Center   | —        | Paused       |
| Right    | 27       | Music mode   |

## LEDs

Wire each LED anode (long leg) to the GPIO pin through a **current-limiting resistor** (220–470 Ω typical). Cathode (short leg) to **GND**.

| LED   | BCM GPIO |
| ----- | -------- |
| Red   | 26       |
| Green | 19       |

## E-Ink Display (Waveshare 2.13" V4) — optional

Requires SPI enabled (`sudo raspi-config` → Interface Options → SPI).

| Display Pin | BCM GPIO / Function |
| ----------- | ------------------- |
| VCC         | 3.3V                |
| GND         | GND                 |
| DIN (MOSI)  | 10 (SPI MOSI)       |
| CLK (SCK)   | 11 (SPI SCLK)       |
| CS          | 8 (SPI CE0)         |
| DC          | 25                  |
| RST         | 17                  |
| BUSY        | 24                  |

## Audio Output

Audio is played through ALSA — use the Pi's 3.5mm jack.

## Test the Wiring

```bash
python3 hardware.py      # Live readout of switch states
python3 led_controller.py # Cycle through LED patterns
```
