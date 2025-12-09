# Raspberry Pi Podcast Player

A reliable, minimalistic, hardware-controlled podcast player designed to run on Raspberry Pi

## 1. Hardware Setup

Connect your switches and let's go!

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
