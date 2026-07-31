"""Manage clip start/end markers and selected-clip preview behavior."""


class ClipSelection:
    """Own the clip markers and preview workflow."""

    def __init__(
        self,
        player,
        get_position,
        stop_transport,
        play_start_cue=None,
        play_end_cue=None,
    ):
        """
        Create clip-selection state.

        Args:
            player:
                The pyglet player used for ordinary playback.

            get_position:
                Callable returning the current transport position in seconds.

            stop_transport:
                Callable that resolves pending seeks and stops shuttle playback.

            play_start_cue:
                Optional callable that plays the start-marker sound.

            play_end_cue:
                Optional callable that plays the end-marker sound.
        """

        self.player = player
        self.get_position = get_position
        self.stop_transport = stop_transport
        self.play_start_cue = play_start_cue
        self.play_end_cue = play_end_cue

        self.start = None
        self.end = None

        self.preview_active = False
        self.is_playing = False

        self.status_message = (
            "Select a start and end time."
        )

    def select_start(self):
        """Save the current position as the clip start."""

        self.start = self.get_position()

        if self.play_start_cue is not None:
            self.play_start_cue()

        self.status_message = (
            f"Sample start set to {self.start:.1f} seconds."
        )

    def select_end(self):
        """Save the current position as the clip end."""

        self.end = self.get_position()

        if self.play_end_cue is not None:
            self.play_end_cue()

        self.player.pause()
        self.is_playing = False

        self.status_message = (
            f"Sample end set to {self.end:.1f} seconds."
        )

    def validate(self):
        """Return whether the selected clip is valid."""

        if self.start is None:
            self.status_message = (
                "Warning: Select a sample start before continuing."
            )
            return False

        if self.end is None:
            self.status_message = (
                "Warning: Select a sample end before continuing."
            )
            return False

        if self.end <= self.start:
            self.status_message = (
                "Warning: The sample end must be after the start."
            )
            return False

        return True

    def get_length(self):
        """Return the selected clip length in seconds."""

        if not self.validate():
            return None

        return self.end - self.start

    def replay_preview(self):
        """Replay the selected clip from its start point."""

        if not self.validate():
            return False

        self.stop_transport()

        self.player.seek(self.start)
        self.player.play()

        self.preview_active = True
        self.is_playing = True
        self.status_message = "Preview replaying."

        return True

    def begin_preview(self):
        """Start previewing the selected clip."""

        if not self.validate():
            return False

        self.stop_transport()

        self.player.seek(self.start)
        self.player.play()

        self.preview_active = True
        self.is_playing = True

        self.status_message = (
            "Preview playing. Enter continues; "
            "Right replays; another key returns to editing."
        )

        return True

    def stop_preview(self, seek_to_end=False):
        """Stop preview playback."""

        self.player.pause()

        self.preview_active = False
        self.is_playing = False

        if seek_to_end and self.end is not None:
            self.player.seek(self.end)

    def update_preview(self):
        """
        Stop preview when playback reaches the selected end.

        Call this repeatedly from the application's main loop.
        """

        if not self.preview_active:
            return

        if not self.is_playing:
            return

        if self.end is None:
            self.stop_preview()
            return

        if self.get_position() >= self.end:
            self.player.pause()

            self.preview_active = False
            self.is_playing = False

            self.status_message = (
                "Preview complete. Enter to continue, "
                "Right to replay, any other key to adjust."
            )

    def clear(self):
        """Clear both clip markers."""

        self.start = None
        self.end = None

        self.stop_preview()

        self.status_message = (
            "Select a start and end time."
        )

    def clear_after_export(self):
        """Clear markers after a successful export."""

        self.start = None
        self.end = None

        self.preview_active = False
        self.is_playing = False
