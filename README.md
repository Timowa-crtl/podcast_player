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

### Running as a Service

Create a systemd service to start automatically on boot:

1. Create service file:
```bash
sudo nano /etc/systemd/system/podcast-player.service
```

2. Add configuration:
```ini
[Unit]
Description=Podcast Player
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/podcast_player_refactored
ExecStart=/usr/bin/python3 /home/pi/podcast_player_refactored/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

3. Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable podcast-player.service
sudo systemctl start podcast-player.service
```

## Troubleshooting

### Enable Debug Mode

Set `"debug_mode": true` in config.json for detailed logging.

### Check Status

```bash
python3 status.py
```

Shows current state, episodes, and storage usage.

### Common Issues

**No audio:**
- Check MPV installation: `which mpv`
- Verify audio output: `speaker-test -t sine -f 1000`
- Check file permissions in episodes directory

**Switch not working:**
- Run hardware test: `python3 test_switch.py`
- Check GPIO permissions: add user to gpio group
- Verify wiring connections

**Episodes not downloading:**
- Check internet connection
- Verify RSS URLs are correct
- Check available disk space
- Review debug logs for errors

**Player crashes:**
- Enable debug mode
- Check system logs: `journalctl -u podcast-player`
- Verify Python version (3.7+ required)

## Advanced Usage

### Manual Episode Management

```python
# Python script to manually manage episodes
from podcast_manager import PodcastManager
from config import Config

config = Config()
manager = PodcastManager(config)

# Force download of specific podcast
episodes = manager.fetch_episodes("https://example.com/feed.xml", count=5)
for ep in episodes:
    manager.download_episode(ep, "podcast_1")
```

### State Inspection

```python
# View saved state
from state_manager import StateManager

state = StateManager()
print(state.export_state())
print(state.get_statistics())
```

## Development

### Running Tests

```bash
# Test switch hardware
python3 test_switch.py

# Test without hardware (simulation mode)
python3 main.py  # Will auto-detect missing GPIO
```

### Project Structure

The code is organized into modules:
- **Config**: Validates and manages configuration
- **Hardware**: Abstracts GPIO operations with fallback
- **Audio**: Controls MPV with IPC socket
- **Podcast**: Handles RSS parsing and downloads
- **State**: Manages persistent storage
- **Utils**: Common utilities and logging

### Contributing

Feel free to submit issues and pull requests!

## License

MIT License - See LICENSE file for details

## Credits

Developed for Raspberry Pi podcast enthusiasts who prefer hardware controls.

## Changelog

### v12 (Current)
- Complete refactor for reliability and maintainability
- Improved error handling and recovery
- Better logging and debugging
- Modular architecture
- Configuration validation
- Progress indicators
- Storage management

### v11
- Switch position as source of truth
- Removed persistent state memory

### Previous versions
- Basic podcast playback
- Initial GPIO support
