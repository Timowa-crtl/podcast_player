# Raspberry Pi Podcast Player

A reliable, minimalistic, hardware-controlled podcast player designed to run on Raspberry Pi

## 3D-Printed Enclosure

A custom enclosure designed specifically for this project.
The box includes a mounting point and port cutouts compatible with Raspberry Pi 3 (B/B+), Pi 2 B, and Pi 1 B+.
The lid features cutouts for a 3-way switch, an R26 turning knob, and two LEDs.

Download the STL files from **[Thingiverse](https://www.thingiverse.com/thing:7228464)**, or grab them from [`enclosure/`](enclosure/).

<img src="pictures/podcast_box_front.png" width="600" alt="frontview of 3D-printed enclosure">

## Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/Timowa-crtl/podcast_player.git
   cd podcast_player
   ```

2. **Install system dependencies**

   ```bash
   sudo apt update
   sudo apt install vlc
   ```

3. **Install Python packages** (system-wide via apt)

   ```bash
   sudo apt install python3-requests python3-schedule python3-vlc python3-pil python3-rpi.gpio
   ```

   If `python3-schedule` is unavailable on your Raspberry Pi OS release, fall back to `sudo pip install schedule`.

4. **(Optional) E-ink display setup**
   - Enable SPI: `sudo raspi-config` → Interface Options → SPI → Enable
   - Install extras: `sudo apt install python3-spidev python3-numpy`
   - The `waveshare_epd` driver is vendored in this repo — no separate install needed
   - If `PIL` or `waveshare_epd` is missing, the display is silently disabled and the rest of the player works normally

## Hardware Setup

- [HARDWARE.md](HARDWARE.md) — bill of materials (Pi model, switches, LEDs, e-ink, enclosure, wiring supplies)
- [WIRING.md](WIRING.md) — GPIO pin assignments for the rotary switch, mode switch, LEDs, and optional e-ink display

**Audio output:** the recommended setup is a 3.5 mm in-car FM transmitter plugged into the Pi's aux output, broadcasting to a nearby FM radio. This keeps the box self-contained and turns any radio into the speaker.

## Configuration

Edit `config.json` to customize

## Usage

### Basic Operation

1. **Start the player:** `python3 main.py`
2. **Stop:** Press Ctrl+C

### Check Status

```bash
python3 status.py
```

### Test Hardware

```bash
python3 hardware.py
```

### Autostart Service Setup

To autostart the podcast_player whenever booting the Raspi, i recommend to create a systemctl-service as follows:

1. Create `/etc/systemd/system/podcast.service` with:

   ```ini
   [Unit]
   Description=Podcast Player
   After=network.target

   [Service]
   ExecStart=/usr/bin/python3 -u /home/user/podcast_player/main.py
   WorkingDirectory=/home/user/podcast_player
   User=user
   Restart=always

   StandardOutput=append:/home/user/podcast_player/podcast.log
   StandardError=append:/home/user/podcast_player/podcast.log

   [Install]
   WantedBy=multi-user.target

   ```

2. Reload systemd:

   ```bash
   sudo systemctl daemon-reload
   ```

3. Enable autostart:

   ```bash
   sudo systemctl enable podcast.service
   ```

4. Start service:

   ```bash
   sudo systemctl start podcast.service
   ```

5. View logs:

   ```bash
   tail -f ~/podcast_player/podcast.log
   ```

## Gallery

<img src="pictures/raspi_box_the_box.png" width="600" alt="enclosure box render">

<img src="pictures/raspi_box_top_plate.png" width="600" alt="top plate render">

<img src="pictures/raspi_inside.jpg" width="600" alt="Raspberry Pi wired inside the enclosure">

<img src="pictures/red_and_wood.jpg" width="600" alt="finished player, red knob with wood top">

<img src="pictures/wood_top.jpg" width="600" alt="wood top plate detail">
