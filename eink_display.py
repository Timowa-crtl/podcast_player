"""E-Ink display controller for Waveshare 2.13" V4 (250x122, 1-bit).

Layout (see specs.md for full details):
  - Top-left: play/pause icon (own line)
  - Top-right: dot circle (12 dots mimicking rotary knob) with mode icon centered inside
  - Name line: name (bold) + completion checkbox, width restricted to avoid dot circle
  - Title: up to 2 lines, word-wrapped, truncated with '...'
  - Progress bar: full width, bottom

Completely optional — gracefully disabled if hardware or libs are missing.
"""

import math
import os
import sys
import time
from typing import Optional

from utils import log

# --- Dependency detection -------------------------------------------------

_libdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "lib")
if os.path.exists(_libdir):
    sys.path.insert(0, _libdir)

try:
    from PIL import Image, ImageDraw, ImageFont

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    from waveshare_epd import epd2in13_V4

    EPD_AVAILABLE = True
except ImportError:
    EPD_AVAILABLE = False

DISPLAY_AVAILABLE = PIL_AVAILABLE and EPD_AVAILABLE

if not PIL_AVAILABLE:
    log("DEBUG", "Pillow not available — e-ink display disabled")
if not EPD_AVAILABLE:
    log("DEBUG", "waveshare_epd not available — e-ink display disabled")


# --- Display dimensions ---------------------------------------------------

WIDTH = 250
HEIGHT = 122

# --- Layout constants (pixels) --------------------------------------------

MARGIN = 7

# Dot circle (top-right) — bigger radius, bigger dots
DOT_CIRCLE_RADIUS = 25
DOT_CIRCLE_CX = WIDTH - MARGIN - DOT_CIRCLE_RADIUS - 2
DOT_CIRCLE_CY = MARGIN + DOT_CIRCLE_RADIUS + 2
DOT_RADIUS_INACTIVE = 3
DOT_RADIUS_ACTIVE = 5

# Play/pause icon (top-left, own line above the name)
PLAY_ICON_SIZE = 20
PLAY_ICON_X = MARGIN
PLAY_ICON_Y = 14

# Name line (below play/pause icon, tight gap)
NAME_Y = 46

# Title (below name)
TITLE_Y = 62
TITLE_LINE2_Y = 78

# Progress bar
BAR_Y = 106
BAR_HEIGHT = 6
BAR_WIDTH = WIDTH - 2 * MARGIN

# Completion checkbox
CHECK_SIZE = 10
CHECK_GAP = 5

# Font sizes — slightly larger for readability
FONT_SIZE_NAME = 14
FONT_SIZE_TITLE = 12

# Full refresh interval (partial refreshes between full refreshes)
FULL_REFRESH_INTERVAL = 100


class EinkDisplay:
    """E-Ink display controller. Optional — disabled if hardware missing."""

    def __init__(self, icons_dir: str = "icons"):
        self.available = False
        self._partial_count = 0
        self._icons = {}

        if not DISPLAY_AVAILABLE:
            log("DEBUG", "E-ink display not available")
            return

        try:
            self.epd = epd2in13_V4.EPD()
            self.epd.init()
            self.epd.Clear(0xFF)
            self.available = True
            log("INFO", "E-ink display initialized (250x122)")
        except Exception as e:
            log("WARNING", f"E-ink init failed: {e}")
            return

        # Load fonts
        self._font_name = self._load_font(FONT_SIZE_NAME, bold=True)
        self._font_title = self._load_font(FONT_SIZE_TITLE)

        # Load mode icons from PNG files
        self._load_icons(icons_dir)

    # --- Font loading ------------------------------------------------------

    def _load_font(self, size: int, bold: bool = False):
        """Load a monospace TTF font, falling back to Pillow default."""
        candidates = []

        if bold:
            candidates += [
                "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
                "/usr/share/fonts/truetype/freefont/FreeMonoBold.ttf",
            ]

        candidates += [
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
            "/usr/share/fonts/truetype/freefont/FreeMono.ttf",
        ]

        for path in candidates:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    continue

        log("DEBUG", f"No TTF font found, using Pillow default (size={size})")
        return ImageFont.load_default()

    # --- Icon loading ------------------------------------------------------

    # Icon size — PNGs are resized to this square dimension to fit inside the dot circle
    ICON_SIZE = 35

    def _load_icons(self, icons_dir: str):
        """Load 1-bit PNG icons from the icons directory.

        Expected files: icons/podcast.png, icons/music.png
        Icons are resized to ICON_SIZE x ICON_SIZE and converted to 1-bit.
        Missing icons are silently skipped.
        """
        from pathlib import Path

        icons_path = Path(icons_dir)
        if not icons_path.is_dir():
            log("DEBUG", f"Icons directory not found: {icons_dir}")
            return

        for name in ("podcast", "music"):
            icon_file = icons_path / f"{name}.png"
            if not icon_file.exists():
                log("DEBUG", f"Icon not found: {icon_file}")
                continue
            try:
                img = Image.open(icon_file).convert("1")
                img = img.resize((self.ICON_SIZE, self.ICON_SIZE), Image.NEAREST)
                self._icons[name] = img
                log("DEBUG", f"Loaded icon: {name} ({self.ICON_SIZE}x{self.ICON_SIZE})")
            except Exception as e:
                log("WARNING", f"Failed to load icon {name}: {e}")

    # --- Public API --------------------------------------------------------

    def clear(self):
        """Full refresh to white. Called once on startup."""
        if not self.available:
            return
        try:
            self.epd.init()
            self.epd.Clear(0xFF)
            self._partial_count = 0
            log("DEBUG", "Display cleared (full refresh)")
        except Exception as e:
            log("ERROR", f"Display clear failed: {e}")

    def show(
        self,
        name: str,
        title: str,
        progress: float,
        knob_position: int,
        is_playing: bool,
        is_completed: bool,
        icon: Optional[str] = None,
    ):
        """
        Draw the screen. Single method for all states.

        Args:
            name:           podcast name or album display name
            title:          episode title or track filename
            progress:       0.0 to 1.0 (progress bar fill)
            knob_position:  1-12 (active dot in the circle)
            is_playing:     True = play icon, False = pause icon
            is_completed:   True = checked box, False = unchecked box
            icon:           "podcast", "music", or None
        """
        if not self.available:
            return

        try:
            image = self._render(
                name, title, progress, knob_position, is_playing, is_completed, icon
            )
            self._display(image)
        except Exception as e:
            log("ERROR", f"Display show failed: {e}")

    def show_blank(self):
        """Clear to white (partial refresh)."""
        if not self.available:
            return
        try:
            image = Image.new("1", (WIDTH, HEIGHT), 255)
            self._display(image)
        except Exception as e:
            log("ERROR", f"Display show_blank failed: {e}")

    def cleanup(self):
        """Put display to sleep. Called on shutdown."""
        if not self.available:
            return
        try:
            self.epd.sleep()
            log("DEBUG", "Display entered sleep mode")
        except Exception as e:
            log("DEBUG", f"Display cleanup: {e}")

    # --- Layout helpers ----------------------------------------------------

    def _max_text_width(self, text_y: int, text_height: int = 14) -> int:
        """Return max text width at the given Y, shrinking if the dot circle is alongside.

        Any text line that overlaps vertically with the dot circle bounding box
        is shortened so it doesn't collide. Lines fully below the circle get
        the full display width.
        """
        # Dot circle bounding box (with a small padding)
        dot_top = DOT_CIRCLE_CY - DOT_CIRCLE_RADIUS - DOT_RADIUS_ACTIVE - 4
        dot_bottom = DOT_CIRCLE_CY + DOT_CIRCLE_RADIUS + DOT_RADIUS_ACTIVE + 4
        dot_left = DOT_CIRCLE_CX - DOT_CIRCLE_RADIUS - DOT_RADIUS_ACTIVE - 6

        text_bottom = text_y + text_height
        full_width = WIDTH - 2 * MARGIN

        # If this text line overlaps vertically with the dot circle, restrict width
        if text_bottom > dot_top and text_y < dot_bottom:
            return dot_left - MARGIN
        return full_width

    # --- Rendering ---------------------------------------------------------

    def _render(
        self, name, title, progress, knob_position, is_playing, is_completed, icon
    ):
        """Render all elements onto a 1-bit PIL Image."""
        image = Image.new("1", (WIDTH, HEIGHT), 255)
        draw = ImageDraw.Draw(image)

        # 1. Dot circle with mode icon (top-right)
        # 1.1 Mode icon FIRST (background layer)
        if icon and icon in self._icons:
            self._paste_mode_icon(image, DOT_CIRCLE_CX, DOT_CIRCLE_CY, icon)
        # 1.2 Dot circle ON TOP (foreground layer)
        self._draw_dot_circle(
            draw, DOT_CIRCLE_CX, DOT_CIRCLE_CY, DOT_CIRCLE_RADIUS, knob_position
        )

        # 2. Play/pause icon (top-left, own line)
        if is_playing:
            self._draw_play_icon(draw, PLAY_ICON_X, PLAY_ICON_Y)
        else:
            self._draw_pause_icon(draw, PLAY_ICON_X, PLAY_ICON_Y)

        # 3. Name + completion checkbox (dynamically avoids dot circle)
        max_name_w = self._max_text_width(NAME_Y) - CHECK_SIZE - CHECK_GAP - 2
        truncated_name = self._truncate_text(name, self._font_name, max_name_w)
        draw.text((MARGIN, NAME_Y), truncated_name, font=self._font_name, fill=0)

        name_text_w = self._get_text_width(truncated_name, self._font_name)
        check_x = MARGIN + name_text_w + CHECK_GAP
        check_y = NAME_Y + 1
        self._draw_checkbox(draw, check_x, check_y, CHECK_SIZE, is_completed)

        # 4. Title (up to 2 lines, first line width-restricted if overlapping dot circle)
        max_title_w_line1 = self._max_text_width(TITLE_Y)
        max_title_w_line2 = self._max_text_width(TITLE_LINE2_Y)
        lines = self._wrap_text_variable(
            title, self._font_title, [max_title_w_line1, max_title_w_line2]
        )
        if len(lines) >= 1:
            draw.text((MARGIN, TITLE_Y), lines[0], font=self._font_title, fill=0)
        if len(lines) >= 2:
            draw.text((MARGIN, TITLE_LINE2_Y), lines[1], font=self._font_title, fill=0)

        # 5. Progress bar
        self._draw_progress_bar(draw, MARGIN, BAR_Y, BAR_WIDTH, BAR_HEIGHT, progress)

        return image

    # --- Drawing primitives ------------------------------------------------

    def _draw_dot_circle(self, draw, cx, cy, radius, active_position):
        """Draw 12 dots in a circle. Position 1 at 7 o'clock, clockwise to 12 at 6 o'clock.
        Inactive dots are hollow, active dot is filled with its number inside.
        """
        dot_radius = 3
        active_radius = 6
        hollow_width = 1
        font_size = 4

        try:
            num_font = ImageFont.truetype(self._font_path, font_size)
        except Exception:
            num_font = ImageFont.load_default()

        for i in range(1, 13):
            angle = (2.0 * math.pi / 3.0) + (i - 1) * (2.0 * math.pi / 12.0)
            dx = cx + math.cos(angle) * radius
            dy = cy + math.sin(angle) * radius

            if i == active_position:
                draw.ellipse(
                    [dx - active_radius, dy - active_radius,
                    dx + active_radius, dy + active_radius],
                    fill=0, outline=0
                )
                draw.text((dx, dy), str(i), font=num_font, fill=255, anchor="mm")
            else:
                draw.ellipse(
                    [dx - dot_radius, dy - dot_radius,
                    dx + dot_radius, dy + dot_radius],
                    fill=255, outline=0, width=hollow_width
                )

    def _paste_mode_icon(self, image, cx, cy, icon_key):
        """Paste a pre-loaded PNG icon centered at (cx, cy) inside the dot circle."""
        icon_img = self._icons.get(icon_key)
        if icon_img is None:
            return
        x = cx - icon_img.width // 2
        y = cy - icon_img.height // 2
        image.paste(icon_img, (x, y))

    def _draw_play_icon(self, draw, x, y):
        """Filled triangle pointing right."""
        s = PLAY_ICON_SIZE
        draw.polygon(
            [(x, y), (x, y + s), (x + s, y + s // 2)],
            fill=0,
        )

    def _draw_pause_icon(self, draw, x, y):
        """Two vertical bars."""
        s = PLAY_ICON_SIZE
        bar_w = max(s // 4, 2)
        gap = s // 5
        draw.rectangle([x + gap, y, x + gap + bar_w, y + s], fill=0)
        draw.rectangle([x + s - gap - bar_w, y, x + s - gap, y + s], fill=0)

    def _draw_checkbox(self, draw, x, y, size, checked):
        """Small checkbox: outline square, with checkmark if checked."""
        draw.rectangle([x, y, x + size, y + size], outline=0, fill=255, width=1)
        if checked:
            draw.line(
                [(x + 2, y + int(size * 0.52)), (x + int(size * 0.4), y + size - 2)],
                fill=0,
                width=1,
            )
            draw.line(
                [(x + int(size * 0.4), y + size - 2), (x + size - 2, y + 2)],
                fill=0,
                width=1,
            )

    def _draw_progress_bar(self, draw, x, y, w, h, progress):
        """Outlined bar with black fill representing progress."""
        progress = max(0.0, min(1.0, progress))
        draw.rectangle([x, y, x + w, y + h], outline=0, fill=255, width=1)
        fill_w = int(w * progress)
        if fill_w > 0:
            draw.rectangle([x, y, x + fill_w, y + h], fill=0)

    # --- Text helpers ------------------------------------------------------

    def _get_text_width(self, text, font):
        """Get rendered width of text in pixels."""
        bbox = font.getbbox(text)
        return bbox[2] - bbox[0]

    def _truncate_text(self, text, font, max_width):
        """Truncate text with '...' if it exceeds max_width."""
        if self._get_text_width(text, font) <= max_width:
            return text

        for i in range(len(text), 0, -1):
            candidate = text[:i] + "..."
            if self._get_text_width(candidate, font) <= max_width:
                return candidate

        return "..."

    def _wrap_text(self, text, font, max_width, max_lines=2):
        """Break text into lines that fit within max_width (uniform width per line)."""
        return self._wrap_text_variable(text, font, [max_width] * max_lines)

    def _wrap_text_variable(self, text, font, max_widths: list):
        """Break text into lines where each line can have a different max width.

        max_widths: list of pixel widths, one per allowed line.
        Words are kept whole when possible. The last line is truncated with '...'
        if the text doesn't fit.
        """
        if not text:
            return []

        max_lines = len(max_widths)
        words = text.split()
        lines = []
        current = ""
        word_idx = 0

        while word_idx < len(words):
            line_num = len(lines)
            if line_num >= max_lines:
                break

            max_w = max_widths[line_num]
            word = words[word_idx]
            test = f"{current} {word}".strip()

            if self._get_text_width(test, font) <= max_w:
                current = test
                word_idx += 1
            else:
                if current:
                    # Current line is full, commit it
                    lines.append(current)
                    current = ""
                    # Don't advance word_idx — retry this word on the next line
                else:
                    # Single word too long for this line — truncate it
                    if line_num >= max_lines - 1:
                        # Last allowed line: truncate with remaining words
                        remaining = " ".join(words[word_idx:])
                        lines.append(self._truncate_text(remaining, font, max_w))
                        return lines[:max_lines]
                    else:
                        lines.append(self._truncate_text(word, font, max_w))
                        word_idx += 1
                        current = ""

        # Commit whatever is left
        if current and len(lines) < max_lines:
            lines.append(current)

        # Truncate last line if it overflows
        if lines:
            line_idx = len(lines) - 1
            max_w = max_widths[min(line_idx, max_lines - 1)]
            lines[-1] = self._truncate_text(lines[-1], font, max_w)

        return lines[:max_lines]

    # --- Display output ----------------------------------------------------

    def _display(self, image):
        """Send image to the e-ink display (partial or full refresh)."""
        self._partial_count += 1

        if self._partial_count >= FULL_REFRESH_INTERVAL:
            self.epd.init()
            self.epd.Clear(0xFF)
            self._partial_count = 0
            log("DEBUG", "Display full refresh (anti-ghosting)")

        buf = self.epd.getbuffer(image)

        if self._partial_count <= 1:
            # First frame after full refresh: load into both buffers
            # so partial refresh has a correct baseline (avoids dithering)
            self.epd.displayPartBaseImage(buf)
        else:
            self.epd.displayPartial(buf)


# --- Demo -----------------------------------------------------------------

DEMO_SCREENS = [
    {
        "label": "Podcast playing (pos 3, not completed)",
        "args": dict(
            name="LANZ & PRECHT",
            title="Ausgabe 421: Über die Zukunft der Arbeit in Deutschland",
            progress=0.6,
            knob_position=3,
            is_playing=True,
            is_completed=False,
            icon="podcast",
        ),
    },
    {
        "label": "Podcast paused (pos 7, completed)",
        "args": dict(
            name="Hotel Matze",
            title="Matze Hielscher im Gespräch mit Eva Schulz",
            progress=0.85,
            knob_position=7,
            is_playing=False,
            is_completed=True,
            icon="podcast",
        ),
    },
    {
        "label": "Music playing (pos 1, not completed)",
        "args": dict(
            name="OK Computer",
            title="03 - Exit Music (For a Film).mp3",
            progress=0.25,
            knob_position=1,
            is_playing=True,
            is_completed=False,
            icon="music",
        ),
    },
    {
        "label": "Music paused (pos 4, not completed)",
        "args": dict(
            name="Stadtaffe",
            title="01 - Schwarz zu Blau.mp3",
            progress=0.0,
            knob_position=4,
            is_playing=False,
            is_completed=False,
            icon="music",
        ),
    },
    {
        "label": "Album completed (pos 3, checked)",
        "args": dict(
            name="Meteora",
            title="13 - Numb.mp3",
            progress=1.0,
            knob_position=3,
            is_playing=False,
            is_completed=True,
            icon="music",
        ),
    },
    {
        "label": "No episode available (pos 2)",
        "args": dict(
            name="Fest und Flauschig",
            title="Error - no episode found",
            progress=0.0,
            knob_position=2,
            is_playing=False,
            is_completed=False,
            icon="podcast",
        ),
    },
    {
        "label": "Long name truncation (pos 9)",
        "args": dict(
            name="Aufstand Im Schlaraffenland",
            title="01 - Remmidemmi (Yippie Yippie Yeah).mp3",
            progress=0.42,
            knob_position=9,
            is_playing=True,
            is_completed=False,
            icon="music",
        ),
    },
    {
        "label": "Position 12 (bottom dot, completed)",
        "args": dict(
            name="Radiolab",
            title="The Fact of the Matter",
            progress=1.0,
            knob_position=12,
            is_playing=False,
            is_completed=True,
            icon="podcast",
        ),
    },
]


def _demo():
    """Cycle through all display states on the real e-ink screen.

    Requires e-ink hardware — exits immediately if not detected.
    Press Ctrl+C to stop.
    """
    print("E-Ink Display Demo")
    print("=" * 40)

    SHOW_DURATION_S = 20

    display = EinkDisplay()
    if not display.available:
        print("No e-ink display detected. Demo requires hardware.")
        return

    print(
        f"Cycling {len(DEMO_SCREENS)} screens ({SHOW_DURATION_S}s each). Ctrl+C to stop.\n"
    )

    try:
        display.clear()
        time.sleep(1)

        while True:
            for screen in DEMO_SCREENS:
                print(f"  {screen['label']}")
                display.show(**screen["args"])
                time.sleep(SHOW_DURATION_S)

            print("  Blank")
            display.show_blank()
            time.sleep(2)

    except KeyboardInterrupt:
        print("\nStopping demo.")
    finally:
        display.show_blank()
        display.cleanup()
        print("Display asleep. Done.")


if __name__ == "__main__":
    _demo()
