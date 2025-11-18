# Raspberry Pi Podcast Player v13

A reliable, hardware-controlled podcast player for Raspberry Pi with automatic episode management using mpg123.

## Features

✅ **Hardware Switch Control** - Control your podcasts without annoying screens, just physical switches!
✅ **Automatic Downloads** - Fetches latest episodes hourly  
✅ **Resume Playback** - Remembers position in each episode  
✅ **Smart Cleanup** - Automatically removes old episodes  
✅ **Lightweight Audio** - Uses mpg123 for minimal resource usage and quick resume

## Quick Start

### 1. Hardware Setup

Connect you switches and let's go!

### 2. Software Installation

```bash
# Clone or download the project
cd podcast_player_mpg123

# Install Python dependencies
pip3 install -r requirements.txt

# Install mpg123 player
sudo apt install -y mpg123

# Test the hardware switch (optional)
python3 hardware.py

# Run the player
python3 main.py
```

## Configuration

Edit `config.json` to customize

### Configuration Options

| Option                     | Description                        | Default    |
| -------------------------- | ---------------------------------- | ---------- |
| `podcasts`                 | List of podcasts                   | Required   |
| `episodes_dir`             | Directory for downloaded episodes  | "episodes" |
| `max_episodes_per_podcast` | Episodes to keep per podcast       | 2          |
| `check_interval_hours`     | Hours between RSS checks           | 1          |
| `debug_mode`               | Enable detailed logging            | false      |
| `position_save_interval`   | Seconds between position saves     | 5          |
| `download_timeout`         | Episode download timeout (seconds) | 30         |
| `rss_timeout`              | RSS fetch timeout (seconds)        | 10         |

## Usage

### Basic Operation

1. **Start the player:** `python3 main.py`
2. **Stop:** Press Ctrl+C

### Check Status

```bash
python3 status.py
```

Shows:

- Downloaded episodes
- Current positions
- Storage usage
- Last RSS check time

### Test Hardware

```bash
python3 hardware.py
```

Interactive tool to verify switch wiring.

### GPIO permissions

```bash
sudo usermod -a -G gpio $USER
# Log out and log back in
```

### Audio output

```bash
# Test mpg123
mpg123 test.mp3

# Set default audio device
sudo raspi-config
# System Options → Audio
```

## Files

- `main.py` - Entry point
- `podcast_player.py` - Main controller
- `audio_player.py` - **NEW: mpg123 integration**
- `podcast_manager.py` - RSS and downloads
- `state_manager.py` - Persistent state
- `hardware.py` - GPIO control
- `utils.py` - Helper functions
- `status.py` - Status display tool
- `config.json` - Configuration file

## License

MIT License - Feel free to modify and distribute.
