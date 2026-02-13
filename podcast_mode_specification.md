# Podcast Mode Specification

## Overview

The Raspberry Pi Podcast Player supports up to 12 podcast feeds mapped to the 12-position rotary knob. In podcast mode, the player fetches episodes via RSS, downloads audio files, and plays them with persistent position tracking. Episodes are checked periodically and old ones are cleaned up automatically.

---

## Configuration

### config.json

```json
{
  "podcasts": [
    {
      "name": "Logbuch Netzpolitik",
      "rss_url": "https://logbuch-netzpolitik.de/feed/mp3"
    },
    {
      "name": "Radiolab",
      "rss_url": "https://feeds.simplecast.com/EmVW7VGp"
    }
  ],
  "episodes_dir": "episodes",
  "max_episodes_per_podcast": 2,
  "check_interval_hours": 1,
  "position_save_interval": 1,
  "download_timeout": 30,
  "rss_timeout": 10,
  "debug_mode": false
}
```

- `podcasts`: list of up to 12 entries, mapped to knob positions 1–12 in order
  - `name`: required, display name
  - `rss_url`: required, RSS feed URL
- `episodes_dir`: where downloaded episodes are stored. **Default**: `episodes`
- `max_episodes_per_podcast`: max episodes kept per feed. **Default**: `2`
- `check_interval_hours`: how often to check RSS feeds. **Default**: `1`
- `position_save_interval`: seconds between position saves. **Default**: `5`
- `download_timeout`: seconds before download times out. **Default**: `30`
- `rss_timeout`: seconds before RSS fetch times out. **Default**: `10`
- `debug_mode`: enable verbose DEBUG-level logging. **Default**: `false`

### Validation

- `podcasts` must be present and non-empty
- Maximum 12 podcasts
- Each podcast must have `name` and `rss_url`

---

## RSS Feed Handling

### Fetching

- Standard HTTP GET with `User-Agent: PodcastPlayer/1.0`
- Supports both RSS 2.0 (`<item>`) and Atom (`<entry>`) feeds
- Timeout controlled by `rss_timeout`

### Episode extraction

From each feed item, extract:
- **Title**: from `<title>` element. Whitespace-collapsed, truncated to 100 chars
- **Audio URL**: from `<enclosure url="...">` (RSS) or `<link rel="enclosure" href="...">` (Atom)
- **GUID**: from `<guid>` or `<id>`. Falls back to audio URL if missing

Items without an enclosure URL are skipped.

### Check schedule

- First check runs immediately on startup
- Subsequent checks run every `check_interval_hours` via the `schedule` library
- Checks also run pending in the main loop (polled every 100ms)

---

## Episode Downloading

### File naming

Episodes are saved as `episode_<hash>.mp3` where `<hash>` is the first 12 hex chars of the MD5 of the episode GUID. This gives stable filenames across restarts.

### Storage layout

```
episodes/
  podcast_1/
    episode_abc123def456.mp3
  podcast_2/
    episode_789012345678.mp3
```

Each podcast gets its own subdirectory under `episodes_dir`.

### Download behavior

- Streamed download in 8KB chunks
- Progress logged at DEBUG level every 10%
- If the file already exists (same GUID hash), download is skipped
- Partial downloads are deleted on failure

### Cleanup

After updating episodes for a podcast, any files in that podcast's directory that aren't in the current episode list are deleted. This keeps storage bounded to `max_episodes_per_podcast` files per feed.

---

## Playback Behavior

### Basic flow

1. Switch to Podcast mode → start playing the podcast at the current knob position
2. Plays the current episode from the saved position
3. One episode per podcast at a time (controlled by `current_index`)

### Resume

- Switching away and back to a podcast **resumes exact position**
- Resume rewinds 2 seconds for context (`pos = max(0, ep["position"] - 2)`)
- Position saved at `position_save_interval` via a background thread in `AudioPlayer`
- If the episode is within 10 seconds of the end, it restarts from the beginning

### Switching podcasts

- Turning the knob while in Podcast mode → **immediately stop current, start new podcast**
- If knob is on position 3 and user switches from Music/Pause to Podcast → **immediately start podcast 3**

### Error handling

- No episodes downloaded yet → log warning, stay silent, LED off
- Episode file missing from disk → log error, stay silent, LED off
- RSS fetch timeout or parse error → log warning/error, skip that feed
- Download timeout or HTTP error → log error, clean up partial file, skip

---

## State Storage

Stored in `state.json` under the `podcasts` namespace.

```json
{
  "version": 2,
  "podcasts": {
    "podcast_1": {
      "episodes": [
        {
          "title": "Episode Title",
          "guid": "unique-episode-id",
          "file": "episode_abc123def456.mp3",
          "position": 123.4,
          "last_played": "2025-01-15T10:30:00",
          "completed": false
        }
      ],
      "current_index": 0,
      "total_time": 3600
    }
  },
  "music": { ... },
  "last_check": 1705312200
}
```

- `episodes`: ordered list of downloaded episodes
- `current_index`: which episode is active (0-based)
- `total_time`: cumulative listening time in seconds (incremented by 1 per save tick)
- `position`: seconds into the episode
- `completed`: true when episode finished
- `last_check`: Unix timestamp of last RSS check (shared across all feeds)

### Position save throttling

`StateManager.save()` is throttled to at most once per second unless `force=True`.

---

## Hardware / Switch Mapping

### 3-position mode switch

| Position | Behavior |
|----------|----------|
| Play     | Play podcast at current knob position |
| Center   | Paused (both modes) |
| Music    | Play music (see music_mode_specification.md) |

### 12-position rotary knob

- In Podcast mode: selects podcast 1–12
- Debounced: requires 3 stable reads and 200ms minimum between changes

### LED behavior

| State | LEDs |
|-------|------|
| Playing | Green solid |
| Paused | Off |
| Checking RSS | Green blink |
| Downloading | Green blink |
| Warning | Red 3× blink |
| Error | Red 5× blink |

---

## Software-only Mode (no GPIO)

Without GPIO (e.g. running on a desktop), the hardware controller returns `PAUSED` with no podcast index. Podcast mode is not reachable without hardware or manual code changes.

---

## Status Display (status.py)

```
📻 Podcasts (12):
   1. Logbuch Netzpolitik
   2. Fest und Flauschig
   ...

📚 Podcast Episodes:

   Logbuch Netzpolitik:
      ▶️ 1. LNP500: Jubiläumsfolge         | 1h 23m 45s | 45.2 MB
      ✅ 2. LNP499: Alte Folge              | 0s         | 38.1 MB

💾 Storage: 24 files, 1234.5 MB in episodes
💿 Disk: 12.3 GB free / 32.0 GB (62% used)
```

Markers: `▶️` = current episode, `✅` = completed, blank = not yet played.

---

## Scope

- One episode plays at a time per podcast (no playlist/queue)
- No episode skipping via hardware
- No per-podcast volume control
- No streaming — episodes are fully downloaded before playback
- mp3 only (determined by RSS enclosure)

---

## File Summary

| File | Role |
|------|------|
| `config.py` | Loads and validates `config.json` |
| `config.json` | Podcast list, directories, timeouts |
| `podcast_manager.py` | RSS fetching, episode downloading, cleanup |
| `audio_player.py` | VLC playback with position tracking |
| `state_manager.py` | Persistent JSON state for positions and metadata |
| `podcast_player.py` | Main controller: ties hardware → podcast/music → audio |
| `hardware.py` | GPIO rotary switch and mode switch reading |
| `led_controller.py` | Red/green LED patterns for status feedback |
| `status.py` | CLI status display tool |
| `main.py` | Entry point, signal handling, startup/shutdown |
| `utils.py` | Logging, formatting helpers |