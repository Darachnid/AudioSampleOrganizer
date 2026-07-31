"""Route curses keypresses to the appropriate application component."""

import curses


MODE_EDIT = "edit"
MODE_PREVIEW = "preview"
MODE_SOURCE = "source"
MODE_NAME = "name"
MODE_FINAL = "final"


class LogicControl:
    """Coordinate keyboard input and application workflow state."""

    def __init__(
        self,
        transport,
        volume_control,
        clip_selection,
        metadata,
        clip_exporter,
        speech,
    ):
        self.transport = transport
        self.volume_control = volume_control
        self.clip_selection = clip_selection
        self.metadata = metadata
        self.clip_exporter = clip_exporter
        self.speech = speech
        self.status_ui = None

        self.mode = MODE_EDIT
        self.running = True
        self.status_message = (
            "Select a start and end time. "
            "Press E for status, Shift E for detail."
        )

    def set_status_ui(self, status_ui):
        """Attach the UI used to build spoken status text."""

        self.status_ui = status_ui

    def announce_status(self, detailed=False):
        """Speak brief status, or detailed status with mode help."""

        if self.status_ui is None:
            text = self.status_message
        elif detailed:
            text = self.status_ui.build_detailed_status()
        else:
            text = self.status_ui.build_brief_status()

        self.speech.speak(text)

        if detailed:
            self.status_message = (
                "Detailed status spoken. Press E for brief status."
            )
        else:
            self.status_message = text

    def adjust_voice_volume(self, direction):
        """Change spoken-voice volume and announce the new level."""

        self.speech.change_volume(direction)
        self.status_message = self.speech.status_message
        self.speech.speak(self.status_message)

    def handle_accessibility_key(self, key):
        """
        Handle status/help and voice-volume keys.

        Returns True when the key was consumed.
        """

        text_entry = self.mode in (MODE_SOURCE, MODE_NAME)

        if key == curses.KEY_F1 or (
            key == ord("e") and not text_entry
        ):
            self.announce_status(detailed=False)
            return True

        if key == curses.KEY_F2 or (
            key == ord("E") and not text_entry
        ):
            self.announce_status(detailed=True)
            return True

        if (
            key in (ord("w"), ord("W"), ord("s"), ord("S"))
            and not text_entry
        ):
            direction = 1 if key in (ord("w"), ord("W")) else -1
            self.adjust_voice_volume(direction)
            return True

        return False

    def set_status(self, message):
        """Set the message displayed by the terminal UI."""

        self.status_message = message

    def sync_status(self):
        """
        Copy the most relevant component status into application state.

        Call this after actions that may update a component's message.
        """

        if self.mode == MODE_EDIT:
            if self.transport.status_message:
                self.status_message = (
                    self.transport.status_message
                )

        elif self.mode == MODE_PREVIEW:
            if self.clip_selection.status_message:
                self.status_message = (
                    self.clip_selection.status_message
                )

        elif self.mode in (MODE_SOURCE, MODE_NAME):
            if self.metadata.status_message:
                self.status_message = (
                    self.metadata.status_message
                )

        elif self.mode == MODE_FINAL:
            if self.clip_exporter.status_message:
                self.status_message = (
                    self.clip_exporter.status_message
                )

    def enter_preview(self):
        """Begin selected-clip preview."""

        if not self.clip_selection.begin_preview():
            self.status_message = (
                self.clip_selection.status_message
            )
            return

        self.mode = MODE_PREVIEW
        self.status_message = (
            self.clip_selection.status_message
        )

    def leave_preview_to_edit(self):
        """Return from preview mode to marker editing."""

        self.clip_selection.stop_preview()
        self.mode = MODE_EDIT

        self.status_message = (
            "Adjust start and end, then press Enter "
            "to preview again."
        )

    def return_to_preview(self):
        """Return to preview confirmation without clearing metadata."""

        self.clip_selection.stop_preview()
        self.mode = MODE_PREVIEW

        self.status_message = (
            "Back at preview. Enter to continue, "
            "Right to replay, any other key to adjust."
        )

    def enter_source(self):
        """Move from preview confirmation to source entry."""

        self.clip_selection.stop_preview()
        self.metadata.load_saved_source()

        self.mode = MODE_SOURCE

        self.status_message = (
            "Enter sound source. Right replays preview, "
            "Enter continues, Left goes back."
        )

    def enter_name(self):
        """Move from source entry to sample-name entry."""

        self.clip_selection.stop_preview()
        self.metadata.sample_name = ""

        self.mode = MODE_NAME

        self.status_message = (
            "Enter the sample name. Enter continues; "
            "Left goes back; Right replays."
        )

    def enter_final(self):
        """Move to final export confirmation."""

        self.clip_selection.stop_preview()
        self.mode = MODE_FINAL

        self.status_message = (
            "Final confirmation. Enter exports, "
            "Left goes back, Down cancels."
        )

    def cancel_export(self):
        """Cancel the metadata/export workflow."""

        self.clip_selection.stop_preview()
        self.mode = MODE_EDIT

        self.status_message = (
            "Export cancelled. Markers and entries retained."
        )

    def replay_preview(self):
        """Replay the selected clip."""

        if self.clip_selection.replay_preview():
            self.status_message = (
                self.clip_selection.status_message
            )
        else:
            self.status_message = (
                self.clip_selection.status_message
            )

    def handle_preview_key(self, key):
        """Handle keys while confirming the clip preview."""

        if key in (curses.KEY_ENTER, 10, 13):
            self.enter_source()
            return

        if key == curses.KEY_RIGHT:
            self.replay_preview()
            return

        if key in (ord("q"), ord("Q")):
            self.running = False
            return

        self.leave_preview_to_edit()

    def handle_source_key(self, key):
        """Handle keys while entering the sound source."""

        if key == curses.KEY_LEFT:
            self.return_to_preview()
            return

        if key == curses.KEY_RIGHT:
            self.replay_preview()
            return

        if key in (curses.KEY_ENTER, 10, 13):
            if not self.metadata.validate_sound_source():
                self.status_message = (
                    self.metadata.status_message
                )
                return

            self.enter_name()
            return

        if key in (ord("q"), ord("Q")):
            self.running = False
            return

        self.metadata.append_to_sound_source(key)

    def handle_name_key(self, key):
        """Handle keys while entering the sample name."""

        if key == curses.KEY_LEFT:
            self.enter_source()
            return

        if key == curses.KEY_RIGHT:
            self.replay_preview()
            return

        if key in (curses.KEY_ENTER, 10, 13):
            if not self.metadata.validate_sample_name():
                self.status_message = (
                    self.metadata.status_message
                )
                return

            self.enter_final()
            return

        if key in (ord("q"), ord("Q")):
            self.running = False
            return

        self.metadata.append_to_sample_name(key)

    def handle_final_key(self, key):
        """Handle keys during final export confirmation."""

        if key in (curses.KEY_ENTER, 10, 13):
            output_path = self.clip_exporter.export()

            self.status_message = (
                self.clip_exporter.status_message
            )

            if output_path is not None:
                self.mode = MODE_EDIT

            return

        if key == curses.KEY_LEFT:
            self.enter_name()
            return

        if key == curses.KEY_RIGHT:
            self.replay_preview()
            return

        if key == curses.KEY_DOWN:
            self.cancel_export()
            return

        if key in (ord("q"), ord("Q")):
            self.running = False

    def handle_edit_key(self, key):
        """Handle keys during ordinary clip editing."""

        if key == ord(" "):
            self.transport.toggle_playback()
            self.status_message = (
                self.transport.status_message
            )

        elif key == curses.KEY_LEFT:
            self.transport.start_shuttle(-1)
            self.status_message = (
                self.transport.status_message
            )

        elif key == curses.KEY_RIGHT:
            self.transport.start_shuttle(1)
            self.status_message = (
                self.transport.status_message
            )

        elif key == curses.KEY_UP:
            self.volume_control.start_change(1)
            self.status_message = (
                self.volume_control.status_message
            )

        elif key == curses.KEY_DOWN:
            self.volume_control.start_change(-1)
            self.status_message = (
                self.volume_control.status_message
            )

        elif key in (ord("a"), ord("A")):
            self.clip_selection.select_start()
            self.status_message = (
                self.clip_selection.status_message
            )

        elif key in (ord("d"), ord("D")):
            self.clip_selection.select_end()
            self.status_message = (
                self.clip_selection.status_message
            )

        elif key in (curses.KEY_ENTER, 10, 13):
            if self.transport.shuttle_direction != 0:
                self.transport.stop_shuttle(
                    resume=False,
                )

            self.enter_preview()

        elif key in (ord("q"), ord("Q")):
            self.running = False

    def handle_key(self, key):
        """Route one curses key based on the current workflow mode."""

        if self.handle_accessibility_key(key):
            return self.running

        if self.mode == MODE_PREVIEW:
            self.handle_preview_key(key)

        elif self.mode == MODE_SOURCE:
            self.handle_source_key(key)

        elif self.mode == MODE_NAME:
            self.handle_name_key(key)

        elif self.mode == MODE_FINAL:
            self.handle_final_key(key)

        else:
            self.handle_edit_key(key)

        return self.running

    def update(self):
        """
        Update time-dependent components.

        Call this once during every iteration of the curses main loop.
        """

        self.transport.update_shuttle()
        self.volume_control.update()
        self.clip_selection.update_preview()

        if self.mode == MODE_EDIT:
            if self.transport.status_message:
                self.status_message = (
                    self.transport.status_message
                )

        if self.volume_control.direction != 0:
            self.status_message = (
                self.volume_control.status_message
            )

        if self.mode == MODE_PREVIEW:
            self.status_message = (
                self.clip_selection.status_message
            )

    def shutdown(self):
        """Stop active components before the application exits."""

        self.volume_control.reset_key_state()
        self.transport.clear_pending_shuttle()

        if self.transport.shuttle_direction != 0:
            self.transport.stop_shuttle(
                resume=False,
            )

        self.clip_selection.stop_preview()
        self.speech.stop()
