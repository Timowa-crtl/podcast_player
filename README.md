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
sudo apt install -y mpv
```

### 3. Configure podcasts
Edit `config.json` to add your podcast RSS feeds.

### 4. Run
```bash
python main.py
```
