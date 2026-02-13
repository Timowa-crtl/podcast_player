# Music Mode Specification

## Overview

Add a music playback mode to the Raspberry Pi Podcast Player. The 3-position switch becomes: **PlayPodcast / Pause / PlayMusic**. In music mode, each of the 12 rotary knob positions selects an album folder and plays it sequentially from track 1 to end, remembering position across switches.

---

## Configuration

### config.json additions

```json
{
  "music_dir": "/home/tweckerle/music",
  "albums": [
    { "folder": "Kraftklub - Mit K.-2012" },
    { "folder": "Linkin Park - Meteora", "name": "Meteora" },
    { "folder": "Peter Fox - Stadtaffe" }
  ]
}
```

- `music_dir`: base directory for album folders. **Default**: `~/music`
- `albums`: list of up to 12 entries, mapped to knob positions 1-12 in order
- `folder`: required, relative to `music_dir`
- `name`: optional display name override. **Default**: folder name

### Album discovery fallback

If `albums` is **not present or empty** in config.json, auto-discover by taking the first 12 subfolders of `music_dir` sorted alphabetically. If `albums` is configured, use only those — no auto-discovery.

### Config reading

Music config is **re-read from config.json on every knob selection** (not cached at startup). This allows editing config without restarting the player.

---

## File Handling

- **Format**: mp3 only (`.mp3` extension, case-insensitive)
- **Sorting**: natural/numeric sort (e.g., `2-song.mp3` before `10-song.mp3`)
- **Subfolder handling**: top-level files only, no recursion into subdirectories
- **Track discovery**:
  - **Fresh start / album reset**: scan folder for all mp3 files at play time
  - **Resuming saved position**: use remembered track list, do not re-scan

---

## Playback Behavior

### Basic flow

1. Switch to Music mode → start playing the album at the current knob position
2. Tracks play sequentially from track 1 to last track
3. Standard gap between tracks (no crossfade, no gapless)
4. Track changes logged at INFO level: `"Now playing track 3/12: filename.mp3"`

### Resume

- Switching away and back to an album **resumes exact track + position within track**
- Switching from Pause to Music **resumes** where it left off
- Position saved at same `position_save_interval` as podcasts (configurable, currently 1s)
- Resume rewinds 2 seconds (same as podcast behavior)

### Album completed

- After last track ends → **stop playback, go silent**
- Album marked as completed in state
- When a completed album is selected again (or switched back to) → **reset to track 1, position 0, re-scan folder for mp3 files**

### Switching albums

- Turning knob while in Music mode → **immediately stop current album, start new album**
- If knob is on position 7 and user switches from Podcast to Music → **immediately start album 7**

### Error handling

- Missing/empty album folder → log warning, play nothing
- Corrupted/unplayable mp3 → log warning, mark track as completed, skip to next track
- If all tracks fail → album goes silent (treated as completed)

### Positions 9-12 with fewer albums

- If fewer than 12 albums configured/discovered → unassigned positions do nothing (silence, log warning)

---

## State Storage

Stored in **same `state.json`** as podcasts, namespaced with `music_` prefix.

```json
{
  "podcasts": { ... },
  "music_1": {
    "folder": "Kraftklub - Mit K.-2012",
    "tracks": ["01-song.mp3", "02-song.mp3"],
    "current_track": 1,
    "position": 45.2,
    "completed": false,
    "total_time": 3600
  },
  "music_5": { ... }
}
```

- `folder`: the folder name at time of last play (to detect config changes)
- `tracks`: ordered list of mp3 files from last scan
- `current_track`: index into `tracks` (0-based)
- `position`: seconds into current track
- `completed`: true when last track finished
- `total_time`: cumulative listening time

---

## Hardware / Switch Mapping

### 3-position mode switch (updated)

| Position | Old behavior | New behavior |
|----------|-------------|--------------|
| Play     | Play podcast | **Play podcast** |
| Center   | Paused      | **Paused** (both modes) |
| Music    | Lightshow   | **Play music** |

### 12-position rotary knob

- In Podcast mode: selects podcast 1-12 (unchanged)
- In Music mode: selects album 1-12

### LED behavior (updated)

- Music mode uses **same LED behavior as podcast mode**:
  - Playing → green solid
  - Paused → off
- **Lightshow removed**

---

## Software-only mode (no GPIO)

Same behavior as podcast mode: falls back to PAUSED. Music mode not reachable without hardware (same limitation as current podcast mode).

---

## Status Display (status.py)

Show music mode info alongside podcast info:

```
🎵 Music Albums (3 configured, base: /home/tweckerle/music):
   1. Kraftklub - Mit K.-2012
      ▶️ Track 3/12 | 2m 15s | 01-intro.mp3
   2. Linkin Park - Meteora (Meteora)
      ✅ Completed
   3. Peter Fox - Stadtaffe
      (not started)
```

---

## Scope exclusions

- No track skipping (plays straight through)
- No per-mode volume control (system/VLC global volume)
- No crossfade or gapless playback
- No recursive subfolder scanning
- No file formats other than mp3

---

## Implementation constraints

- **Must not break existing podcast mode** — podcast mode is stable
- Reuse existing components where possible (`AudioPlayer`, `StateManager`, `LEDController`)
- Music state uses same `state.json`, same `position_save_interval`
- Music config re-read from `config.json` on each knob selection

---

## Implementation Summary

### Files changed

| File | Change | Description |
|------|--------|-------------|
| `music_manager.py` | **NEW** | Album discovery, track scanning, config re-reading, natural sort |
| `audio_player.py` | MODIFIED | Added VLC `MediaPlayerEndReached` event → `has_ended()` method |
| `config.py` | MODIFIED | Added `music_dir`, `albums` properties + validation |
| `config.json` | MODIFIED | Added `music_dir`, `albums` fields |
| `state_manager.py` | MODIFIED | Added `music` namespace + `get_music`, `save_music`, `update_music_position`, `mark_music_completed`, `reset_music` methods |
| `podcast_player.py` | MODIFIED | Added music mode handling: `switch_to_album`, `_play_music_track`, `_advance_music_track`, end-of-track check in main loop |
| `led_controller.py` | MODIFIED | Removed lightshow, `MUSIC_MODE` → green solid (same as `PLAYING`) |
| `status.py` | MODIFIED | Added music albums section to status display |
| `hardware.py` | UNCHANGED | `SwitchState.MUSIC_MODE` already existed |
| `main.py` | UNCHANGED | No changes needed |
| `utils.py` | UNCHANGED | No changes needed |

### Key design decisions

1. **End-of-track detection**: VLC `MediaPlayerEndReached` event sets a `threading.Event`. Main loop polls `audio.has_ended()` every 100ms to advance tracks. Avoids complex callback threading.
2. **Config re-read**: `MusicManager._read_music_config()` reads `config.json` fresh on every knob selection. This is intentional — allows editing albums without restart.
3. **State namespacing**: Music state stored under `state["music"]["music_1"]` etc., separate from `state["podcasts"]`. Clean separation.
4. **Position callback routing**: Single `_save_position` callback checks `self._is_music_mode()` to route to podcast or music save logic.
5. **Podcast mode untouched**: All podcast logic paths remain identical. Music mode is additive only.