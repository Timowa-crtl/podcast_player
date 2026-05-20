# Hardware

Bill of materials for building the player. For how to wire them up, see [WIRING.md](WIRING.md).

## Compute

- Raspberry Pi 3 B, Pi 2 B, Pi 1 B+. Any model with a 40-pin GPIO header should work.
- **MicroSD card** — 16 GB or larger

## Controls

### Rotary Switch (podcast / album selector)

- **RS26 1-pole 12-position rotary switch**, panel mount, 6 mm shaft
- **Knob** — R26-style aluminum knob with 6 mm collet (matches the enclosure cutout)

### Mode Switch (podcast / paused / music)

- **3-position SPDT toggle switch**, center-off (ON-OFF-ON), panel mount

### Status LEDs

- **2× 3 mm LEDs** — one red, one green
- **resistor** — 1000 Ω 

### Audio Output (recommended)

- **3.5 mm in-car FM transmitter** — plugs into the Pi's 3.5 mm aux output and broadcasts on an FM frequency you tune your radio to. This my recommended setup. Feel free to adapt!

### E-Ink Display (optional)

- **Waveshare 2.13" e-Paper HAT (V4)** — 250×122, SPI interface
  - The vendored driver in `waveshare_epd/` targets the V4 specifically; older V1/V2/V3 panels might need a different driver

## Connections & Prototyping

- **T-type GPIO breakout board for Raspberry Pi** — with 40-pin ribbon cable, to bring the Pi header onto a breadboard or prototype board
- **Breadboard** - must fit breakout board and cables and fit into the enclosure
- **Dupont jumper wires** — 20-pin assorted set with M-M, F-M, and F-F (Pi header → breakout → switches/LEDs)

## Enclosure

- **3D-printed case** with cutouts for the rotary knob, 3-position switch, and two LEDs
  - STL files: [thingiverse.com/thing:7228464](https://www.thingiverse.com/thing:7228464)
  - Compatible with Pi 3 B/B+, Pi 2 B, Pi 1 B+

## Wiring

See [WIRING.md](WIRING.md) for the full GPIO pin assignment table.
