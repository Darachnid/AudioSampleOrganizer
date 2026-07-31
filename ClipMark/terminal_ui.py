"""Draw the curses terminal interface for ClipMark."""

import curses

from ClipMark.logic_control import (
    MODE_EDIT,
    MODE_FINAL,
    MODE_NAME,
    MODE_PREVIEW,
    MODE_SOURCE,
)


def format_time(seconds):
    """Convert seconds into MM:SS.s or HH:MM:SS.s format."""

    seconds = max(0.0, float(seconds))

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    remaining_seconds = seconds % 60

    if hours > 0:
        return (
            f"{hours:02d}:"
            f"{minutes:02d}:"
            f"{remaining_seconds:04.1f}"
        )

    return (
        f"{minutes:02d}:"
        f"{remaining_seconds:04.1f}"
    )


class TerminalUI:
    """Render application state without owning control logic."""

    def __init__(
        self,
        screen,
        audio_data,
        logic,
        transport,
        volume_control,
        clip_selection,
        metadata,
        clip_exporter,
    ):
        self.screen = screen
        self.audio_data = audio_data
        self.logic = logic
        self.transport = transport
        self.volume_control = volume_control
        self.clip_selection = clip_selection
        self.metadata = metadata
        self.clip_exporter = clip_exporter

    def configure_screen(self):
        """Configure curses for nonblocking keyboard input."""

        try:
            curses.curs_set(0)
        except curses.error:
            pass

        self.screen.nodelay(True)
        self.screen.keypad(True)

    def safe_addstr(self, row, column, text):
        """Draw text without crashing when the terminal is too small."""

        try:
            self.screen.addstr(
                row,
                column,
                str(text),
            )
        except curses.error:
            pass

    def get_current_position(self):
        """Return the transport's current playback position."""

        return self.transport.get_current_position()

    def get_transport_status(self):
        """Return a human-readable transport or workflow status."""

        if self.logic.mode == MODE_PREVIEW:
            if self.clip_selection.is_playing:
                return "Previewing sample"

            return "Preview paused"

        if self.logic.mode == MODE_SOURCE:
            return "Entering sound source"

        if self.logic.mode == MODE_NAME:
            return "Entering sample name"

        if self.logic.mode == MODE_FINAL:
            return "Final export confirmation"

        if self.transport.pending_shuttle_direction == -1:
            return "Left tap pending"

        if self.transport.pending_shuttle_direction == 1:
            return "Right tap pending"

        if self.transport.shuttle_direction == -1:
            speed = self.transport.get_shuttle_speed()
            return f"Audible reverse {speed:.0f}x"

        if self.transport.shuttle_direction == 1:
            speed = self.transport.get_shuttle_speed()
            return f"Audible fast-forward {speed:.0f}x"

        if self.transport.is_playing:
            return "Playing 1x"

        return "Paused"

    def get_mode_label(self):
        """Return a short label for the active workflow mode."""

        labels = {
            MODE_EDIT: "Edit mode",
            MODE_PREVIEW: "Preview mode",
            MODE_SOURCE: "Sound source entry",
            MODE_NAME: "Sample name entry",
            MODE_FINAL: "Final export confirmation",
        }
        return labels.get(self.logic.mode, "ClipMark")

    def get_mode_help_lines(self):
        """Return context-dependent help lines for the active mode."""

        if self.logic.mode == MODE_EDIT:
            return [
                "Space play or pause.",
                "Left and Right seek or shuttle.",
                "Up and Down change playback volume.",
                "A sets clip start. D sets clip end.",
                "Enter previews the clip.",
                "E shows status. Shift E shows detailed status and help.",
                "Q quits.",
            ]

        if self.logic.mode == MODE_PREVIEW:
            return [
                "Previewing the selected clip.",
                "Enter continues to naming.",
                "Right replays.",
                "Any other key returns to editing.",
                "E shows status. Shift E shows detailed help.",
                "Q quits.",
            ]

        if self.logic.mode == MODE_SOURCE:
            return [
                "Type the sound source name.",
                "Enter continues. Left goes back. Right replays.",
                "Backspace deletes.",
                "F1 shows status. F2 shows detailed help.",
                "Q quits.",
            ]

        if self.logic.mode == MODE_NAME:
            return [
                "Type the sample name.",
                "Enter continues. Left goes back. Right replays.",
                "Backspace deletes.",
                "F1 shows status. F2 shows detailed help.",
                "Q quits.",
            ]

        return [
            "Final confirmation.",
            "Enter exports the clip.",
            "Left goes back. Right replays. Down cancels.",
            "E shows status. Shift E shows detailed help.",
            "Q quits.",
        ]

    def format_marker(self, value):
        """Return a marker time, or not selected."""

        if value is None:
            return "not selected"

        return format_time(value)

    def build_brief_status_lines(self):
        """Return brief status as one JAWS-friendly line per fact."""

        position = format_time(self.get_current_position())
        duration = format_time(self.audio_data["duration"])
        message = self.logic.status_message.strip()

        lines = [
            "ClipMark status",
            f"Mode: {self.get_mode_label()}",
            f"Transport: {self.get_transport_status()}",
            f"Position: {position} of {duration}",
            f"Volume: {self.volume_control.display_percent} percent",
            f"Start: {self.format_marker(self.clip_selection.start)}",
            f"End: {self.format_marker(self.clip_selection.end)}",
        ]

        if (
            message
            and not message.startswith("Status open")
            and not message.startswith("Detailed status open")
        ):
            lines.append(f"Message: {message}")

        lines.append("Press any key to return.")
        lines.append("Press Shift E for detailed status and help.")
        return lines

    def build_detailed_status_lines(self):
        """Return detailed status and mode help as separate lines."""

        duration = format_time(self.audio_data["duration"])
        position = format_time(self.get_current_position())

        if (
            self.clip_selection.start is not None
            and self.clip_selection.end is not None
            and self.clip_selection.end > self.clip_selection.start
        ):
            length = format_time(
                self.clip_selection.end - self.clip_selection.start
            )
        else:
            length = "unknown"

        lines = [
            "ClipMark detailed status",
            f"Mode: {self.get_mode_label()}",
            f"Transport: {self.get_transport_status()}",
            f"File: {self.audio_data['path'].name}",
            f"Duration: {duration}",
            f"Position: {position}",
            f"Volume: {self.volume_control.display_percent} percent",
            f"Start: {self.format_marker(self.clip_selection.start)}",
            f"End: {self.format_marker(self.clip_selection.end)}",
            f"Length: {length}",
        ]

        if self.logic.mode in (MODE_SOURCE, MODE_NAME, MODE_FINAL):
            source = self.metadata.sound_source or "blank"
            name = self.metadata.sample_name or "blank"
            lines.append(f"Source: {source}")
            lines.append(f"Name: {name}")

            if self.logic.mode == MODE_FINAL:
                lines.append(
                    "Export file: "
                    f"{self.clip_exporter.build_output_stem()}.wav"
                )

        lines.append("Help for this mode:")
        lines.extend(self.get_mode_help_lines())
        lines.append("Press any key to return.")
        lines.append("Press E for brief status.")
        return lines

    def get_controls(self):
        """Return the controls appropriate for the current mode."""

        if self.logic.mode == MODE_EDIT:
            return (
                "Space       Play/pause",
                "Left/Right  seek or shuttle",
                "Up/Down     playback volume",
                "A           clip start",
                "D           clip end",
                "E           JAWS status",
                "Shift+E     JAWS detail/help",
                "Enter       preview clip",
                "Q           quit",
            )

        if self.logic.mode == MODE_PREVIEW:
            return (
                "Enter       continue",
                "Right       replay",
                "Other key   adjust clip",
                "E / Shift+E JAWS status / detail",
                "Q           quit",
            )

        if self.logic.mode in (
            MODE_SOURCE,
            MODE_NAME,
        ):
            return (
                "Enter       continue",
                "Left        back",
                "Right       replay",
                "Backspace   delete text",
                "F1 / F2     JAWS status / detail",
                "Q           quit",
            )

        return (
            "Enter       export",
            "Left        back",
            "Right       replay",
            "Down        cancel",
            "E / Shift+E JAWS status / detail",
            "Q           quit",
        )

    def build_progress_bar(self, width):
        """Build a text progress bar for the current audio position."""

        duration = self.audio_data["duration"]

        if duration <= 0:
            progress = 0.0
        else:
            progress = (
                self.get_current_position()
                / duration
            )

        progress = max(
            0.0,
            min(progress, 1.0),
        )

        bar_width = max(
            10,
            min(width - 12, 60),
        )

        filled_width = int(
            round(progress * bar_width)
        )

        filled_width = min(
            filled_width,
            bar_width,
        )

        empty_width = (
            bar_width - filled_width
        )

        bar = (
            "["
            + ("#" * filled_width)
            + ("-" * empty_width)
            + "]"
        )

        percent = int(
            round(progress * 100)
        )

        return f"{bar} {percent:3d}%"

    def draw_header(self):
        """Draw source-file and transport information."""

        height, width = self.screen.getmaxyx()

        self.safe_addstr(
            0,
            0,
            "ClipMark",
        )

        self.safe_addstr(
            1,
            0,
            f"File: {self.audio_data['path'].name}",
        )

        self.safe_addstr(
            2,
            0,
            (
                "Export to: "
                f"{self.clip_exporter.export_directory}"
            ),
        )

        self.safe_addstr(
            3,
            0,
            (
                "Transport: "
                f"{self.get_transport_status()}"
            ),
        )

        self.safe_addstr(
            4,
            0,
            (
                "Position:  "
                f"{format_time(self.get_current_position())}"
                " / "
                f"{format_time(self.audio_data['duration'])}"
            ),
        )

        self.safe_addstr(
            5,
            0,
            (
                "Volume:    "
                f"{self.volume_control.display_percent}%"
            ),
        )

        if height > 6:
            self.safe_addstr(
                6,
                0,
                self.build_progress_bar(width),
            )

    def draw_selection(self):
        """Draw clip start, end, and length."""

        if self.clip_selection.start is None:
            start_text = "Not selected"
        else:
            start_text = format_time(
                self.clip_selection.start
            )

        if self.clip_selection.end is None:
            end_text = "Not selected"
        else:
            end_text = format_time(
                self.clip_selection.end
            )

        self.safe_addstr(
            8,
            0,
            f"Start:     {start_text}",
        )

        self.safe_addstr(
            9,
            0,
            f"End:       {end_text}",
        )

        if (
            self.clip_selection.start is not None
            and self.clip_selection.end is not None
            and self.clip_selection.end
            > self.clip_selection.start
        ):
            length = (
                self.clip_selection.end
                - self.clip_selection.start
            )

            self.safe_addstr(
                10,
                0,
                f"Length:    {format_time(length)}",
            )

    def draw_controls(self):
        """Draw controls for the active workflow mode."""

        controls = self.get_controls()

        for row, line in enumerate(
            controls,
            start=12,
        ):
            self.safe_addstr(
                row,
                0,
                line,
            )

    def draw_prompt(self):
        """Draw metadata entry or final confirmation prompts."""

        height, _ = self.screen.getmaxyx()

        context_row = max(
            0,
            height - 5,
        )

        input_row = max(
            0,
            height - 4,
        )

        if self.logic.mode == MODE_SOURCE:
            self.safe_addstr(
                input_row,
                0,
                (
                    "Source: "
                    f"{self.metadata.sound_source}_"
                ),
            )

        elif self.logic.mode == MODE_NAME:
            self.safe_addstr(
                context_row,
                0,
                (
                    "Source: "
                    f"{self.metadata.sound_source}"
                ),
            )

            self.safe_addstr(
                input_row,
                0,
                (
                    "Name:   "
                    f"{self.metadata.sample_name}_"
                ),
            )

        elif self.logic.mode == MODE_FINAL:
            self.safe_addstr(
                context_row,
                0,
                (
                    f"Source: {self.metadata.sound_source}    "
                    f"Name: {self.metadata.sample_name}"
                ),
            )

            self.safe_addstr(
                input_row,
                0,
                (
                    "File: "
                    f"{self.clip_exporter.build_output_stem()}.wav"
                ),
            )

    def draw_status(self):
        """Draw the current application message."""

        height, _ = self.screen.getmaxyx()

        message_row = max(
            0,
            height - 1,
        )

        self.safe_addstr(
            message_row,
            0,
            f"Message: {self.logic.status_message}",
        )

    def draw_status_view(self):
        """
        Draw a full-screen status page for JAWS.

        One fact per line so JAWS can read the window or move line by line
        without the dense main UI.
        """

        height, width = self.screen.getmaxyx()

        if self.logic.status_view == "detail":
            lines = self.build_detailed_status_lines()
        else:
            lines = self.build_brief_status_lines()

        max_rows = max(1, height)
        max_cols = max(1, width - 1)

        for row, line in enumerate(lines[:max_rows]):
            self.safe_addstr(
                row,
                0,
                str(line)[:max_cols],
            )

    def draw(self):
        """Redraw the entire terminal interface."""

        self.screen.erase()

        if self.logic.status_view is not None:
            self.draw_status_view()
        else:
            self.draw_header()
            self.draw_selection()
            self.draw_controls()
            self.draw_prompt()
            self.draw_status()

        self.screen.refresh()
