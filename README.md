# Raspberry Pi Podcast Player

## Features
- Downloads and stores latest 2 episodes per podcast
- Checks for new episodes every hour
- Remembers playback position for each episode
- Switch between 2 podcasts or pause
- Automatic cleanup of old episodes

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Install MPV
```bash
# Ubuntu/Debian/Raspberry Pi
sudo apt-get install mpv

# Or compile from source if needed
```

### 3. Configure podcasts
Edit `config.json` to add your podcast RSS feeds.

### 4. Run
```bash
python main.py
```

## Testing (Simulated GPIO)

While running, open another terminal and edit the `BUTTON_STATE` variable in `main.py`:

```python
BUTTON_STATE = "podcast_0"  # Play podcast 1
BUTTON_STATE = "podcast_1"  # Play podcast 2  
BUTTON_STATE = "paused"     # Pause
```

Or use Python to change it:
```bash
# In another terminal while main.py is running
python -c "import main; main.BUTTON_STATE = 'podcast_0'"
```

## GPIO Setup (Production)

Replace the simulation section in `main.py` with:

```python
from gpiozero import Button

button_podcast_0 = Button(2)
button_podcast_1 = Button(3)
button_pause = Button(4)

button_podcast_0.when_pressed = lambda: player.handle_state_change("podcast_0")
button_podcast_1.when_pressed = lambda: player.handle_state_change("podcast_1")
button_pause.when_pressed = lambda: player.handle_state_change("paused")
```

## File Structure
```
podcast_player/
├── main.py              # Main orchestrator
├── audio_player.py      # MPV wrapper
├── podcast_manager.py   # RSS & downloads
├── state_manager.py     # State persistence
├── config.json          # Configuration
├── state.json           # Runtime state (auto-generated)
└── episodes/            # Downloaded episodes (auto-generated)
    ├── podcast_0/
    └── podcast_1/
```

## State File Format

`state.json` stores:
- Current playback state
- Episodes per podcast (max 2)
- Playback position for each episode
- Last RSS check timestamp

Example:
```json
{
  "podcasts": {
    "podcast_0": {
      "episodes": [
        {
          "title": "Episode Title",
          "guid": "unique-id",
          "file": "episode_abc123.mp3",
          "position": 145.2
        }
      ],
      "current_index": 0
    }
  },
  "current_state": "podcast_0",
  "last_check": 1234567890
}
```
