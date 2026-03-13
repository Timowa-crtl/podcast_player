# E-Ink Display Specification

## Overview

Add a Waveshare 2.13" V4 e-ink display (250×122 pixels, 1-bit black/white) to show playback status. The display is **completely optional** — the player works fine without it, same as GPIO.

---

## Hardware

- **Model**: Waveshare 2.13" V4 (epd2in13_V4)
- **Resolution**: 250×122 pixels, landscape orientation
- **Colors**: 1-bit (black and white only)
- **Interface**: SPI
- **Refresh**: partial refresh (~0.3s) for all updates

### Refresh strategy

- **Partial refresh for everything.**
- **One full refresh on startup** to clear ghosting from previous session.
- **Periodic full refresh** every ~50 partial refreshes to reduce ghosting buildup.

---

## Screen Layout

There is **one layout** used for both playing and paused states, in both podcast and music modes. The only difference between playing and paused is the icon (▶ vs ⏸).

```
┌──────────────────────────────┐
│ ☐ Knob: 3/12          [IMG] │  <- checkbox + knob position + mode icon
│ ▶ LANZ & PRECHT             │  <- play/pause icon + name (bold)
│                              │
│ Ausgabe 421: Über die        │  <- title/filename, up to 2 lines
│ Zukunft der Arbe...          │
│                              │
│ ████████████░░░░░░░░░░░░░░░ │  <- progress bar
└──────────────────────────────┘
```

### Elements top to bottom

1. **Status line**: checkbox + `Knob: N/12` + mode icon (top-right)
2. **Name line**: play (▶) or pause (⏸) icon + podcast name or album display name, bold, truncated to fit
3. **Title area**: episode title or track filename, plain, up to 2 lines, truncated with `...`
4. **Progress bar**: filled/unfilled, full width with margin, no numbers

### Mode icon (top-right corner)

- Optional 1-bit `.png` bitmap, pasted onto the canvas at top-right
- Podcast mode: `icons/podcast.png` (microphone with broadcast arcs)
- Music mode: `icons/music.png` (beamed eighth notes)
- Size: ~24×24px (tuned on real hardware)
- Icons are pre-made 1-bit PNGs stored in an `icons/` directory
- If icon file is missing: skip silently, no crash
- The `show()` method accepts an optional `icon` parameter — a string key like `"podcast"` or `"music"`, or `None` for no icon

### Checkbox

- ☑ = this episode/album has been completed before (played to the end at least once)
- ☐ = not yet completed
- Shown in both play and pause modes
- Completion tracking is a state concern handled elsewhere — the display just receives a boolean

### Progress bar

- Podcast: `position / episode_duration`
- Music: `position / track_duration`
- If duration unknown: empty bar (all unfilled)

---

## Display States

### Boot / no content → blank

On startup, one full refresh to clear display to white. Stays blank until the first mode change that has content to show. Fresh boot with nothing downloaded = blank.

### Playing (podcast or music)

- Icon: ▶
- Name: podcast name (podcast mode) or album display name (music mode)
- Title: episode title (podcast) or track filename (music)
- Progress bar: updates every 30 seconds
- Checkbox: reflects completion state of current episode/album

### Paused

- Icon: ⏸ (replaces ▶, everything else identical)
- Shows info from **last active mode** (was playing music → pause shows album; was playing podcast → pause shows podcast)
- **Knob turns while paused update the display** — preview what would play if the switch is flipped. The mode context (podcast vs music) comes from the last active mode.
- Progress bar: frozen at last position

### Paused with no prior playback

If the player has never played anything in this session (e.g. fresh boot, mode starts as PAUSED), display stays blank. First play action triggers the first draw.

---

## Update Triggers

| Event | Display action |
|-------|---------------|
| Mode switch to PLAYING | Redraw with ▶ + podcast info |
| Mode switch to MUSIC_MODE | Redraw with ▶ + album info |
| Mode switch to PAUSED | Redraw with ⏸ (keep current content) |
| Knob turn while playing | Redraw (new podcast/album selected) |
| Knob turn while paused | Redraw with preview of new selection |
| Progress update (every 30s) | Redraw progress bar only |
| Track change (music) | Show full bar briefly, then redraw with new track |
| Album completed (music) | Show ☑ + full progress bar, stay on screen |
| No episode available | Show podcast name + "Error - no episode found" |
| RSS check running/completed | No display change (LED handles this) |
| Shutdown | Put display to sleep |

---

## Fonts

Monospace `.ttf` font for clean rendering at small sizes on 1-bit display.

**Sizes (tuned on real hardware):**
- Status line (checkbox + knob): ~9px
- Name (bold): ~11px
- Title: ~10px

---

## Text Handling

- **Never scroll.** Truncate with `...` if it doesn't fit.
- **Max 2 lines** for episode title / track filename.
- **All text is static.** No animations, no marquee.

---

## Display Controller API

```python
class EinkDisplay:
    """E-Ink display controller. Optional — disabled if hardware missing."""

    def __init__(self, icons_dir: str = "icons"):
        """Init display. Loads icon bitmaps from icons_dir.
        Sets self.available = False if libs/hardware missing."""

    def clear(self):
        """Full refresh to white. Called once on startup."""

    def show(self, name: str, title: str, progress: float,
             knob_position: int, is_playing: bool, is_completed: bool,
             icon: str | None = None):
        """
        Draw the screen. Single method for all states.

        Args:
            name:           podcast name or album display name
            title:          episode title or track filename
            progress:       0.0 to 1.0 (progress bar fill)
            knob_position:  1-12 (shown as "Knob: N/12")
            is_playing:     True = ▶, False = ⏸
            is_completed:   True = ☑, False = ☐
            icon:           optional icon key — "podcast", "music", or None
        """

    def show_blank(self):
        """Clear to white (partial refresh)."""

    def cleanup(self):
        """Put display to sleep. Called on shutdown."""
```

One render method. Callers pass data, display draws it.

---

## Integration Points

### podcast_player.py

Display updated from the main controller:

- `switch_to_podcast()` → `display.show(..., icon="podcast")`
- `switch_to_album()` → `display.show(..., icon="music")`
- `pause()` → `display.show(...)` with current info, `is_playing=False`, same icon as last active mode
- `handle_switch_change()` knob turn while paused → `display.show(...)` with preview info, same icon as last active mode
- `_on_track_ended()` → redraw with new track info
- Main loop every 30s during playback → `display.show(...)` with updated progress

### Progress update in main loop

```python
# In run(), alongside existing polling:
if self.audio.is_playing() and time.time() - last_display_update > 30:
    self._update_display()
    last_display_update = time.time()
```

---

## Graceful Degradation

Same pattern as `LEDController` and `HardwareController`:

```python
DISPLAY_AVAILABLE = PIL_AVAILABLE and EPD_AVAILABLE

class EinkDisplay:
    def __init__(self):
        self.available = False
        if not DISPLAY_AVAILABLE:
            log("DEBUG", "E-ink display not available")
            return
        try:
            self.epd = epd2in13_V4.EPD()
            self.epd.init()
            self.available = True
        except Exception as e:
            log("WARNING", f"E-ink init failed: {e}")

    def show(self, name, title, progress, knob_position, is_playing, is_completed, icon=None):
        if not self.available:
            return
        # ... render and display
```

Every public method is a no-op if `self.available` is False.

---

## Demo Mode

Run `python eink_display.py` to cycle through all display states on the real e-ink screen. **Requires hardware** — exits immediately if no display is detected.

- Cycles 6 screens (3 seconds each): podcast playing, podcast paused (completed), music playing, music paused, album completed, no episode error
- Loops until Ctrl+C
- Blank screen shown between cycles
- On exit: clears display and puts it to sleep

---

## Edge Cases

### Album completed

When the last track finishes, the player goes silent. The display stays on and shows the completed album with ☑ checkbox, album name, last track filename, and a **full progress bar**. Remains until the user switches away.

### No episode available

If a podcast position has no downloaded episode, the display shows the podcast name with title `"Error - no episode found"` and an empty progress bar.

### Music track change

When one track ends and the next begins, the display briefly shows the **completed track with a full progress bar** (one refresh cycle), then redraws with the new track's filename and an empty progress bar.

### RSS check

Display ignores RSS checks entirely. LED handles that feedback.

### Pause / resume timing

No immediate redraw on pause/resume. The main loop polls at ~100ms which is fast enough — the display updates on the next cycle.

---

## File Summary

| File | Change | Description |
|------|--------|-------------|
| `eink_display.py` | **NEW** | Display controller: rendering, refresh, layout, demo |
| `icons/podcast.png` | **NEW** | 1-bit podcast icon (24×24px, white background) |
| `icons/music.png` | **NEW** | 1-bit music icon (24×24px, white background) |
| `podcast_player.py` | MODIFIED | Call `display.show()` on mode/knob/progress changes |
| `main.py` | UNCHANGED | Display init happens inside PodcastPlayer |
| `config.py` | UNCHANGED | No config needed |
| `requirements.txt` | MODIFIED | Add `Pillow` (waveshare lib is vendored) |

---

## Scope Exclusions

- No clock
- No scrolling text
- No animations
- No overview/list screen
- No configuration options for display
- No different layouts per mode (one layout fits all)
- No track number display (just filename)
- No display feedback for RSS checks, warnings, or errors (LED handles those)
- No immediate redraw on pause/resume — main loop polling (~100ms) is fast enough
- No PNG export in demo mode — demo requires real hardware
