# Raspberry Pi Podcast Player v13

A reliable, hardware-controlled podcast player for Raspberry Pi with automatic episode management using mpg123.

## Features

✅ **Hardware Switch Control** - 3-position switch for hands-free control  
✅ **Automatic Downloads** - Fetches latest episodes hourly  
✅ **Resume Playback** - Remembers position in each episode  
✅ **Smart Cleanup** - Automatically removes old episodes  
✅ **Error Recovery** - Robust error handling and logging  
✅ **Debug Mode** - Detailed logging for troubleshooting  
✅ **Lightweight Audio** - Uses mpg123 for minimal resource usage

## Quick Start

### 1. Hardware Setup

Connect a 3-position ON-OFF-ON switch (Kippschalter):

```
Switch Pin 1 → RPi Pin 11 (GPIO17)
Switch Pin 2 → RPi Pin 9  (GND)
Switch Pin 3 → RPi Pin 13 (GPIO27)
```

**Switch Positions:**
- UP → Podcast 1
- CENTER → Paused
- DOWN → Podcast 2

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

Edit `config.json` to customize:

```json
{
  "podcasts": [
    {
      "name": "Your First Podcast",
      "rss_url": "https://example.com/feed.xml"
    },
    {
      "name": "Your Second Podcast", 
      "rss_url": "https://example.com/feed2.xml"
    }
  ],
  "episodes_dir": "episodes",
  "max_episodes_per_podcast": 2,
  "check_interval_hours": 1,
  "debug_mode": false,
  "position_save_interval": 5,
  "download_timeout": 30,
  "rss_timeout": 10
}
```

### Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `podcasts` | List of podcasts (max 2) | Required |
| `episodes_dir` | Directory for downloaded episodes | "episodes" |
| `max_episodes_per_podcast` | Episodes to keep per podcast | 2 |
| `check_interval_hours` | Hours between RSS checks | 1 |
| `debug_mode` | Enable detailed logging | false |
| `position_save_interval` | Seconds between position saves | 5 |
| `download_timeout` | Episode download timeout (seconds) | 30 |
| `rss_timeout` | RSS fetch timeout (seconds) | 10 |

## Usage

### Basic Operation

1. **Start the player:** `python3 main.py`
2. **Switch control:**
   - Move switch UP for Podcast 1
   - Move switch CENTER to pause
   - Move switch DOWN for Podcast 2
3. **Stop:** Press Ctrl+C

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

## Changes from v12

- **Migrated from MPV to mpg123** for better performance and reliability
- Simpler audio backend with remote control interface
- Reduced resource usage
- More stable position tracking

## Troubleshooting

### mpg123 not found
```bash
sudo apt install mpg123
```

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
