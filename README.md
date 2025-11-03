# Raspberry Pi Podcast Player v12

A reliable, hardware-controlled podcast player for Raspberry Pi with automatic episode management.

## Features

✅ **Hardware Switch Control** - 3-position switch for hands-free control  
✅ **Automatic Downloads** - Fetches latest episodes hourly  
✅ **Resume Playback** - Remembers position in each episode  
✅ **Smart Cleanup** - Automatically removes old episodes  
✅ **Error Recovery** - Robust error handling and logging  
✅ **Debug Mode** - Detailed logging for troubleshooting  

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
cd podcast_player_refactored

# Install Python dependencies
pip3 install -r requirements.txt

# Install MPV player
sudo apt install -y mpv

# Test the hardware switch
python3 test_switch.py

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
- Switch position as source of truth
- Removed persistent state memory

### Previous versions
- Basic podcast playback
- Initial GPIO support
