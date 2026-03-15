# E-Ink Display Specification

## Overview

Add a Waveshare 2.13" V4 e-ink display (250×122 pixels, 1-bit black/white) to show playback status. The display is **completely optional** — the player works fine without it, same as GPIO.

---

## Hardware

- **Model**: Waveshare 2.13" V4 (epd2in13_V4)
- **Resolution**: 250×122 pixels, landscape orientation
- **Colors**: 1-bit (black and white only)
- **Interface**: SPI

---

## Screen Layout

There is **one layout** used for both playing and paused states, in both podcast and music modes. The only difference between playing and paused is the icon (▶ vs ⏸).

```
┌──────────────────────────────────────────┐
│                                  · · ·   │
│                                ·       · │
│                                ·  icon · │
│                                ·       · │
│                                  · ● ·   │
│                                          │
│ ▶ LANZ & PRECHT ☐                       │
│                                          │
│ Ausgabe 421: Über die Zukunft            │
│ der Arbeit in Deuts...                   │
│                                          │
│ ████████████████░░░░░░░░░░░░░░░░░░░░░░░ │
└──────────────────────────────────────────┘
```

### Elements top to bottom

1. **Dot circle with mode icon** (top-right): 12 dots in a circle representing the rotary knob positions, with the current position shown as a larger filled dot. A mode icon (podcast or music) is centered inside the dot circle.

2. **Name line**: play (▶) or pause (⏸) icon + podcast name or album display name (bold, truncated to fit) + completion checkbox (☐/☑) immediately after the name text.

3. **Title area**: episode title or track filename, regular weight, up to 2 lines, word-wrapped, truncated with `...` if needed.

4. **Progress bar**: full display width with margins, outlined rectangle with black fill representing progress. No text/numbers.

---

## Dot Circle (Knob Position Indicator)

A circle of 12 dots mirroring the physical 12-position rotary knob.

### Positioning

- Top-right corner of the display
- ~44px diameter (22px radius)
- Mode icon centered inside the circle

### Dot orientation

Dots are numbered 1–12 clockwise, starting from the bottom-left:

- **Position 1**: 7 o'clock (bottom-left)
- **Position 6**: 12 o'clock (top)
- **Position 12**: 6 o'clock (bottom)

### Dot rendering

- Inactive positions: small filled dot (~2px radius)
- Active position: larger filled dot (~4px radius)

### Center icon

- Podcast mode: `icons/podcast.png` (microphone with broadcast arcs)
- Music mode: `icons/music.png` (beamed eighth notes)
- Pre-made 1-bit PNGs, resized to 24×24px, stored in `icons/` directory
- If icon file is missing: skip silently, no crash

---

## Completion Checkbox

- Small checkbox (☐ unchecked / ☑ checked) drawn inline on the name line, immediately after the name text with a small gap
- ☑ = this album/podcast episode has been played to the end at least once
- ☐ = not yet completed
- The checkbox reduces the available width for the name text — name is truncated to leave room

---

## Play / Pause Icon

- **Playing**: filled triangle pointing right (▶)
- **Paused**: two vertical bars (⏸)
- Drawn at the left edge of the name line, before the name text

---

## Progress Bar

- Full display width minus left/right margins
- Thin outlined rectangle with black fill from the left representing progress (0.0–1.0)
- If duration is unknown: empty bar (outline only)

---

## Text Rendering

- **Font**: monospace TTF (DejaVu Sans Mono preferred, falls back to Liberation Mono, FreeMono, then Pillow default)
- **Name line**: bold, ~11px
- **Title lines**: regular, ~10px
- **Truncation**: names and titles truncated with `...` if they exceed available width
- **Title wrapping**: up to 2 lines, word-wrapped, last line truncated if needed
- **No scrolling, no animation, all text is static**

---

## Display States

| State | Play/pause icon | Name | Title | Checkbox | Progress | Dot circle icon |
|-------|----------------|------|-------|----------|----------|----------------|
| Podcast playing | ▶ | podcast name | episode title | completion state | position/duration | podcast |
| Podcast paused | ⏸ | podcast name | episode title | completion state | frozen | podcast |
| Music playing | ▶ | album display name | track filename | completion state | position/duration | music |
| Music paused | ⏸ | album display name | track filename | completion state | frozen | music |
| Album completed | ⏸ | album display name | last track filename | ☑ | full | music |
| No episode | ⏸ | podcast name | "Error - no episode found" | ☐ | empty | podcast |
| Blank | — | — | — | — | — | — |

### Boot / no content → blank

On startup, one full refresh to clear display to white. Stays blank until the first mode change that has content to show.

### Paused with no prior playback

If the player has never played anything in this session, display stays blank. First play action triggers the first draw.

---

## Update Triggers

| Event | Display action |
|-------|---------------|
| Mode switch to PLAYING | Redraw with ▶ + podcast info |
| Mode switch to MUSIC_MODE | Redraw with ▶ + album info |
| Mode switch to PAUSED | Redraw with ⏸, keep current content |
| Knob turn while playing | Redraw with new podcast/album |
| Knob turn while paused | Redraw with preview of new selection |
| Progress update (every 30s) | Redraw with updated progress |
| Track change (music) | Redraw with new track info |
| Album completed (music) | Show ☑ + full progress bar |
| No episode available | Show name + error title |
| RSS check running/completed | No display change (LED handles this) |
| Shutdown | Put display to sleep |

---

## Refresh Strategy

- **Partial refresh** for all normal updates (~0.3s)
- **One full refresh on startup** to clear ghosting
- **Periodic full refresh** every ~50 partial refreshes to reduce ghosting buildup

---

## Display Controller API

```python
class EinkDisplay:
    """E-Ink display controller. Optional — disabled if hardware missing."""

    def __init__(self, icons_dir: str = "icons"):
        """Init display. Loads icon PNGs from icons_dir.
        Sets self.available = False if libs/hardware missing."""

    def clear(self):
        """Full refresh to white. Called once on startup."""

    def show(self, name: str, title: str, progress: float,
             knob_position: int, is_playing: bool, is_completed: bool,
             icon: Optional[str] = None):
        """
        Draw the screen. Single method for all states.

        Args:
            name:           podcast name or album display name
            title:          episode title or track filename
            progress:       0.0 to 1.0 (progress bar fill)
            knob_position:  1-12 (active dot in the circle)
            is_playing:     True = ▶, False = ⏸
            is_completed:   True = ☑, False = ☐
            icon:           "podcast", "music", or None
        """

    def show_blank(self):
        """Clear to white (partial refresh)."""

    def cleanup(self):
        """Put display to sleep. Called on shutdown."""
```

One render method. Callers pass data, display draws it.

---

## Graceful Degradation

Same pattern as `LEDController` and `HardwareController`:

- If Pillow or the Waveshare library is missing, or hardware init fails, `self.available = False`
- Every public method is a no-op if `self.available` is False
- No crashes, no errors — just silently disabled

---

## Integration Points

### podcast_player.py

Display updated from the main controller:

- `switch_to_podcast()` → `display.show(..., icon="podcast")`
- `switch_to_album()` → `display.show(..., icon="music")`
- `pause()` → `display.show(...)` with current info, `is_playing=False`, same icon as last active mode
- `handle_switch_change()` knob turn while paused → `display.show(...)` with preview info
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

## Demo Mode

Run `python eink_display.py` to cycle through display states on the real e-ink screen. **Requires hardware** — exits immediately if no display is detected.

- Cycles 8 screens (20 seconds each): podcast playing, podcast paused (completed), music playing, music paused, album completed, no episode error, long name truncation, position 12 test
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

---

## File Summary

| File | Change | Description |
|------|--------|-------------|
| `eink_display.py` | **NEW** | Display controller: rendering, refresh, layout, demo |
| `icons/podcast.png` | **NEW** | 1-bit podcast icon (24×24px, white background) |
| `icons/music.png` | **NEW** | 1-bit music icon (24×24px, white background) |
| `podcast_player.py` | MODIFIED | Call `display.show()` on mode/knob/progress changes |
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
- No PNG export in demo mode — demo requires real hardware
