# Raspberry Pi Podcast Player v11

Physical switch-controlled podcast player for Raspberry Pi with automatic episode management.

## Features
- **Hardware Switch Control**: 3-position switch to select between 2 podcasts or pause
- Downloads and stores latest 2 episodes per podcast
- Checks for new episodes every hour
- Remembers playback position for each episode
- Automatic cleanup of old episodes
- **Switch position is source of truth** - program always starts in current switch position

## Hardware Setup

### Switch Wiring
Connect a 3-position ON-OFF-ON switch (Kippschalter) to the Raspberry Pi:

```
Switch Pin 1 → RPi Pin 11 (GPIO17)
Switch Pin 2 → RPi Pin 9  (GND)
Switch Pin 3 → RPi Pin 13 (GPIO27)
```

### Switch Positions
- **UP** (GPIO17=LOW, GPIO27=HIGH) → Podcast 1
- **CENTER** (both HIGH) → Paused
- **DOWN** (GPIO17=HIGH, GPIO27=LOW) → Podcast 2

## Software Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Install MPV
```bash
sudo apt install -y mpv
```

### 3. Configure podcasts
Edit `config.json` to add your podcast RSS feeds.

### 4. Test the switch
Run the test script to verify your switch wiring:
```bash
python switch_test.py
```

### 5. Run the player
```bash
python main.py
```

## Configuration

Edit `config.json`:
- `podcasts`: List of podcast RSS feeds (first = podcast_1, second = podcast_2)
- `max_episodes_per_podcast`: Number of episodes to keep (default: 2)
- `check_interval_hours`: How often to check for new episodes (default: 1)

## Debug Mode

Debug logging is enabled by default. To disable, edit `main.py`:
```python
DEBUG_MODE = False
```

## State Management

The player automatically saves:
- Current playback position (every 5 seconds)
- Downloaded episode metadata
- Last RSS check time

State is stored in `state.json` (automatically created).

**Note:** The physical switch position is always the source of truth. The program does not remember which podcast was last playing - it always starts with whatever position the switch is currently in.

## Changes in v11

- Removed persistent `current_state` from state.json
- Program now always reads and applies the physical switch position on startup
- Switch position is the single source of truth for playback state
