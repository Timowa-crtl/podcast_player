# Raspberry Pi Podcast Player

A reliable, minimalistic, hardware-controlled podcast player designed to run on Raspberry Pi

## 1. Hardware Setup

Connect you switches and let's go!

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

## Files

- `main.py` - Entry point
- `podcast_player.py` - Main controller
- `audio_player.py` - Audio player
- `podcast_manager.py` - RSS and downloads
- `state_manager.py` - Persistent state
- `hardware.py` - GPIO control
- `utils.py` - Helper functions
- `status.py` - Status display tool
- `config.json` - Configuration file

## License

MIT License - Feel free to modify and distribute.
