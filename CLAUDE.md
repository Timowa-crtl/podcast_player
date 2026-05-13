# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Hardware-controlled podcast and music player for Raspberry Pi. A 12-position rotary knob selects one of 12 podcasts (RSS feeds) or 12 album folders; a 3-position switch toggles between Podcast / Paused / Music mode. Output goes to ALSA via VLC; status is shown on red/green LEDs and a Waveshare 2.13" e-ink display.

## Commands

```bash
python3 main.py                  # Run the player (Ctrl+C to stop)
python3 main.py --skip-check     # Run without the initial RSS check on startup
python3 status.py                # Print current state, episodes, storage, disk
python3 hardware.py              # Smoke-test the GPIO switch wiring
python3 led_controller.py        # Smoke-test the LEDs
pip install -r requirements.txt  # Install deps (RPi.GPIO only installs on ARM)
```

There is no test suite. Component scripts (`hardware.py`, `led_controller.py`) double as `__main__` smoke tests on real hardware.

## Architecture

`main.py` builds a `PodcastPlayer` (in `podcast_player.py`) which owns one instance of every subsystem and runs a single 200ms polling loop. Each subsystem is a self-contained module:

- **`hardware.py`** — reads BCM GPIO pins for the 12-position rotary (one pin per position, active-low) and the 3-position mode switch. Debounces with `STABLE_READS=3` and a 200ms minimum gap. Returns `(SwitchState, podcast_index)`. Gracefully degrades to "PAUSED, no index" when `RPi.GPIO` is unavailable (development on a non-Pi).
- **`audio_player.py`** — VLC wrapper. Runs a background thread that calls `position_callback(seconds)` every `position_save_interval` seconds so the controller persists progress. Detects end-of-media via a VLC event flag polled by `has_ended()` in the main loop. If resuming within `RESUME_END_THRESHOLD=9s` of the end, restarts from 0.
- **`podcast_manager.py`** — RSS fetching (with conditional GET via cached `ETag`/`Last-Modified`), MD5-of-GUID filenames, streamed downloads, cleanup of orphan files. Supports RSS 2.0 and Atom.
- **`music_manager.py`** — Album discovery. Re-reads `config.json` on every knob turn so albums can be reconfigured without restart. Falls back to alphabetical scan of `music_dir` when `albums` is empty. Natural-sorts tracks (`2-foo.mp3` before `10-foo.mp3`).
- **`state_manager.py`** — Persists everything to `state.json` (gitignored). Save calls are throttled to ≤1/sec unless `force=True`. Top-level keys: `podcasts`, `music`, `feed_cache`, `last_check`. Podcast state is keyed by `podcast_<n>`; music state by `music_<n>`.
- **`led_controller.py`** — Owns LED state machine. `utils.log()` automatically triggers `WARNING`/`ERROR` LED patterns via a global reference set in `set_led_controller()`.
- **`eink_display.py`** — Optional. Disabled silently if `PIL` or `waveshare_epd` is missing. Uses partial refreshes with a full refresh every 100 updates.

### Main loop responsibilities (`PodcastPlayer.run`)

1. `schedule.run_pending()` — fires hourly RSS check (`check_interval_hours`). The schedule pins checks to round clock hours (`HH:00`), not interval-from-startup.
2. `audio.has_ended()` — routes to `_on_track_ended` (music) or `_on_episode_ended` (podcast).
3. Refresh e-ink progress bar every `DISPLAY_UPDATE_INTERVAL=10s` while playing.
4. Re-read hardware; call `handle_switch_change` only when state changed.

On startup, `_wait_for_rotary()` polls the hardware 20× to let debounce lock onto the real knob position before the first action (otherwise the default position 1 fires a spurious switch).

### State coordination

Podcast and music modes share `AudioPlayer` and `StateManager`, but each has its own set of `current_*` fields on the controller. Switching between modes saves the current position first, then nulls out the other mode's fields. The `_save_position` callback inspects `current_mode` and routes to the right `update_*_position` method — this is why the callback is set once in `__init__` instead of being swapped per mode.

### Config (`config.json`)

- `podcasts`: 1–12 entries, mapped to knob positions in list order. Required.
- `albums`: 0–12 entries, mapped to knob positions in list order. Optional — empty means auto-discover folders under `music_dir`.
- `debug_mode`: enables DEBUG log lines. Read once and cached by `utils._get_debug_mode()`.

Defaults live in `config.py:DEFAULTS`. Validation rejects >12 podcasts/albums and missing `name`/`rss_url`/`folder` fields.

## Conventions

- Logging goes through `utils.log(level, message)` — never `print()` for status. ERROR/WARNING auto-flash the red LED.
- `state.json` and `episodes/` are runtime artifacts, gitignored. Don't commit them.
- Specifications in `podcast_mode_specification.md`, `music_mode_specification.md`, and `eink_specification.md` are the source of truth for behavior — consult them before changing semantics.
