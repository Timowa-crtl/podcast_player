"""E-Ink display controller for Waveshare 2.13" V4 (250x122, 1-bit).

Completely optional — gracefully disabled if hardware or libs are missing.
Follows the same pattern as LEDController and HardwareController.
"""

import os
import sys
import time
from pathlib import Path
from typing import Optional

from utils import log

# --- Dependency detection -------------------------------------------------

# Add vendored waveshare lib to path
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

MARGIN = 6
STATUS_Y = 4  # top of status line
NAME_Y = 24  # top of name line
TITLE_Y = 48  # top of first title line
TITLE_LINE2_Y = 62  # top of second title line
BAR_Y = 82  # top of progress bar
BAR_HEIGHT = 5
BAR_WIDTH = WIDTH - 2 * MARGIN

ICON_SIZE = 24  # mode icon dimensions (square)
ICON_X = WIDTH - MARGIN - ICON_SIZE
ICON_Y = 2

PLAY_ICON_SIZE = 14  # play/pause triangle/bars size
PLAY_ICON_X = MARGIN
PLAY_ICON_Y = NAME_Y

# Checkbox dimensions
CHECK_SIZE = 10

# --- Font sizes ------------------------------------------------------------

FONT_SIZE_STATUS = 12
FONT_SIZE_NAME = 14
FONT_SIZE_TITLE = 13

# Full refresh interval (number of partial refreshes between full refreshes)
FULL_REFRESH_INTERVAL = 50


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
        self._font_status = self._load_font(FONT_SIZE_STATUS)
        self._font_name = self._load_font(FONT_SIZE_NAME, bold=True)
        self._font_title = self._load_font(FONT_SIZE_TITLE)

        # Load mode icons
        self._load_icons(icons_dir)

    # --- Font loading ------------------------------------------------------

    def _load_font(self, size: int, bold: bool = False) -> "ImageFont":
        """Load a TTF font at the given size, falling back to default."""
        # Try common monospace fonts available on Raspberry Pi OS
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
            "/usr/share/fonts/truetype/freefont/FreeMono.ttf",
        ]

        if bold:
            # Try bold variants first
            bold_paths = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
                "/usr/share/fonts/truetype/freefont/FreeMonoBold.ttf",
            ]
            font_paths = bold_paths + font_paths

        for path in font_paths:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    continue

        log("DEBUG", f"No TTF font found, using Pillow default (size={size})")
        return ImageFont.load_default()

    # --- Icon loading ------------------------------------------------------

    def _load_icons(self, icons_dir: str):
        """Load 1-bit PNG icons from the icons directory."""
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
                img = img.resize((ICON_SIZE, ICON_SIZE), Image.NEAREST)
                self._icons[name] = img
                log("DEBUG", f"Loaded icon: {name} ({ICON_SIZE}x{ICON_SIZE})")
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
            knob_position:  1-12 (shown as "Knob: N/12")
            is_playing:     True = play icon, False = pause icon
            is_completed:   True = checked box, False = unchecked box
            icon:           optional icon key — "podcast", "music", or None
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

    # --- Rendering ---------------------------------------------------------

    def _render(
        self,
        name: str,
        title: str,
        progress: float,
        knob_position: int,
        is_playing: bool,
        is_completed: bool,
        icon: Optional[str],
    ) -> "Image":
        """Render all elements onto a 1-bit PIL Image."""
        image = Image.new("1", (WIDTH, HEIGHT), 255)  # white background
        draw = ImageDraw.Draw(image)

        # 1. Status line: checkbox + knob position
        self._draw_checkbox(draw, MARGIN, STATUS_Y, is_completed)
        status_text = f"Knob: {knob_position}/12"
        draw.text(
            (MARGIN + CHECK_SIZE + 4, STATUS_Y - 1),
            status_text,
            font=self._font_status,
            fill=0,
        )

        # 2. Mode icon (top-right)
        if icon and icon in self._icons:
            image.paste(self._icons[icon], (ICON_X, ICON_Y))

        # 3. Play/pause icon + name
        self._draw_play_pause(draw, is_playing)
        name_x = PLAY_ICON_X + PLAY_ICON_SIZE + 6
        max_name_width = WIDTH - name_x - MARGIN
        truncated_name = self._truncate_text(name, self._font_name, max_name_width)
        draw.text(
            (name_x, NAME_Y),
            truncated_name,
            font=self._font_name,
            fill=0,
        )

        # 4. Title (up to 2 lines)
        max_title_width = WIDTH - 2 * MARGIN
        lines = self._wrap_text(title, self._font_title, max_title_width, max_lines=2)
        if len(lines) >= 1:
            draw.text((MARGIN, TITLE_Y), lines[0], font=self._font_title, fill=0)
        if len(lines) >= 2:
            draw.text((MARGIN, TITLE_LINE2_Y), lines[1], font=self._font_title, fill=0)

        # 5. Progress bar
        self._draw_progress_bar(draw, progress)

        return image

    def _draw_checkbox(self, draw: "ImageDraw", x: int, y: int, checked: bool):
        """Draw a small checkbox (checked or unchecked)."""
        # Outer box
        draw.rectangle(
            [x, y, x + CHECK_SIZE, y + CHECK_SIZE], outline=0, fill=255, width=1
        )
        if checked:
            # Draw checkmark as two lines
            draw.line([(x + 2, y + 5), (x + 4, y + CHECK_SIZE - 2)], fill=0, width=1)
            draw.line(
                [(x + 4, y + CHECK_SIZE - 2), (x + CHECK_SIZE - 2, y + 2)],
                fill=0,
                width=1,
            )

    def _draw_play_pause(self, draw: "ImageDraw", is_playing: bool):
        """Draw play triangle or pause bars."""
        x = PLAY_ICON_X
        y = PLAY_ICON_Y
        s = PLAY_ICON_SIZE

        if is_playing:
            # Filled triangle pointing right
            draw.polygon([(x, y), (x, y + s), (x + s, y + s // 2)], fill=0)
        else:
            # Two vertical bars
            bar_w = s // 4
            gap = s // 5
            left_x = x + gap
            right_x = x + s - gap - bar_w
            draw.rectangle([left_x, y, left_x + bar_w, y + s], fill=0)
            draw.rectangle([right_x, y, right_x + bar_w, y + s], fill=0)

    def _draw_progress_bar(self, draw: "ImageDraw", progress: float):
        """Draw progress bar: gray background + black fill."""
        progress = max(0.0, min(1.0, progress))

        # Background (gray = dithered on 1-bit, so use outline only)
        draw.rectangle(
            [MARGIN, BAR_Y, MARGIN + BAR_WIDTH, BAR_Y + BAR_HEIGHT],
            outline=0,
            fill=255,
            width=1,
        )

        # Fill
        fill_width = int(BAR_WIDTH * progress)
        if fill_width > 0:
            draw.rectangle(
                [MARGIN, BAR_Y, MARGIN + fill_width, BAR_Y + BAR_HEIGHT],
                fill=0,
            )

    # --- Text helpers ------------------------------------------------------

    def _get_text_width(self, text: str, font: "ImageFont") -> int:
        """Get rendered width of text in pixels."""
        bbox = font.getbbox(text)
        return bbox[2] - bbox[0]

    def _truncate_text(self, text: str, font: "ImageFont", max_width: int) -> str:
        """Truncate text with '...' if it exceeds max_width."""
        if self._get_text_width(text, font) <= max_width:
            return text

        for i in range(len(text), 0, -1):
            candidate = text[:i] + "..."
            if self._get_text_width(candidate, font) <= max_width:
                return candidate

        return "..."

    def _wrap_text(
        self, text: str, font: "ImageFont", max_width: int, max_lines: int = 2
    ) -> list:
        """
        Break text into lines that fit within max_width.
        Last line is truncated with '...' if text doesn't fit.
        """
        if not text:
            return []

        words = text.split()
        lines = []
        current_line = ""

        for word in words:
            test = f"{current_line} {word}".strip()
            if self._get_text_width(test, font) <= max_width:
                current_line = test
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word

                # Hit max lines — truncate remainder into last line
                if len(lines) >= max_lines:
                    break

        # Add the last line being built
        if current_line and len(lines) < max_lines:
            lines.append(current_line)
        elif current_line and len(lines) == max_lines:
            # Remaining text didn't fit — truncate the last line
            remaining = current_line
            for w in words[words.index(current_line.split()[0]) :]:
                pass  # already consumed
            lines[-1] = self._truncate_text(
                lines[-1] + " " + current_line, font, max_width
            )

        # Truncate last line if it's too wide (e.g. single very long word)
        if lines:
            lines[-1] = self._truncate_text(lines[-1], font, max_width)

        return lines[:max_lines]

    # --- Display output ----------------------------------------------------

    def _display(self, image: "Image"):
        """Send image to the e-ink display (partial or full refresh)."""
        self._partial_count += 1

        if self._partial_count >= FULL_REFRESH_INTERVAL:
            # Periodic full refresh to reduce ghosting
            self.epd.init()
            self.epd.Clear(0xFF)
            self._partial_count = 0
            log("DEBUG", "Display full refresh (anti-ghosting)")

        self.epd.displayPartial(self.epd.getbuffer(image))


# --- Demo (requires e-ink hardware) ----------------------------------------


DEMO_SCREENS = [
    {
        "label": "Podcast playing",
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
        "label": "Podcast paused (completed)",
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
        "label": "Music playing",
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
        "label": "Music paused",
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
        "label": "Album completed",
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
        "label": "No episode available",
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
]


def _demo():
    """
    Demo mode: cycles through all display states on the real e-ink screen.
    Requires e-ink hardware — exits if not detected.
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

            # Show blank between cycles
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
