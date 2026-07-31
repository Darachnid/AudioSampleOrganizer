"""Manage audio playback volume using one stepped change per keypress."""


class VolumeControl:
    """Manage playback volume independently from transport behavior."""

    def __init__(self, player, initial_volume=1.0):
        self.player = player

        self.volume = self._bounded_volume(initial_volume)
        self.display_percent = int(round(self.volume * 100))

        # Kept for compatibility with logic_control.py.
        # Volume keys no longer have held-key behavior.
        self.direction = 0

        self.status_message = (
            f"Volume set to {self.display_percent}%."
        )

        self.player.volume = self.volume

    @staticmethod
    def _bounded_volume(value):
        """Clamp a floating-point volume to 0.0 through 1.0."""

        return max(
            0.0,
            min(float(value), 1.0),
        )

    @staticmethod
    def get_step_percent(current_percent):
        """Return the step size based on the current volume."""

        if current_percent <= 5:
            return 1

        if current_percent <= 10:
            return 2

        if current_percent <= 30:
            return 5

        if current_percent <= 70:
            return 10

        if current_percent <= 90:
            return 5

        if current_percent <= 95:
            return 2

        return 1

    def set_volume_percent(self, percent, announce=True):
        """Set playback volume using an integer percentage."""

        bounded_percent = max(
            0,
            min(int(percent), 100),
        )

        self.display_percent = bounded_percent
        self.volume = bounded_percent / 100.0
        self.player.volume = self.volume

        if announce:
            self.status_message = (
                f"Volume set to {self.display_percent}%."
            )

    def set_volume(self, new_volume, announce=True):
        """Set playback volume using a value from 0.0 through 1.0."""

        bounded_volume = self._bounded_volume(new_volume)
        percent = int(round(bounded_volume * 100))

        self.set_volume_percent(
            percent,
            announce=announce,
        )

    def start_change(self, direction):
        """
        Apply one volume change for one keypress.

        A direction of 1 raises the volume.
        A direction of -1 lowers the volume.
        """

        if direction not in (-1, 1):
            raise ValueError(
                "Volume direction must be either -1 or 1."
            )

        step = self.get_step_percent(
            self.display_percent
        )

        new_percent = (
            self.display_percent
            + direction * step
        )

        self.set_volume_percent(
            new_percent,
            announce=True,
        )

    def update(self):
        """No update is required because key holds are disabled."""

        return

    def reset_key_state(self):
        """Compatibility method; there is no held-key state."""

        self.direction = 0
