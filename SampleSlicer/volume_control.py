"""Manage playback volume and terminal tap-versus-hold behavior."""

import time


# Terminal key-repeat timing.
INITIAL_HOLD_TIMEOUT = 0.75
REPEAT_RELEASE_TIMEOUT = 0.18
AUTO_REPEAT_GAP = 0.12


# Volume behavior.
#
# A distinct tap changes volume by 1%. Once terminal auto-repeat confirms that
# a key is being held, volume sweeps across the full range in 2.5 seconds.
VOLUME_TAP_STEP = 0.01
VOLUME_SWEEP_SECONDS = 2.5
VOLUME_HOLD_DELAY = 2.25


class VolumeControl:
    """Manage playback volume independently from transport behavior."""

    def __init__(self, player, initial_volume=1.0):
        self.player = player

        self.volume = self._bounded_volume(initial_volume)
        self.display_percent = int(round(self.volume * 100))

        self.direction = 0
        self.started_at = 0.0
        self.last_key_at = 0.0
        self.repeat_count = 0
        self.start_level = self.volume
        self.hold_confirmed = False

        self.status_message = (
            f"Volume set to {self.display_percent}%."
        )

        self.player.volume = self.volume

    @staticmethod
    def _bounded_volume(value):
        """Return volume constrained to the range 0.0 through 1.0."""

        return round(
            max(0.0, min(float(value), 1.0)),
            2,
        )

    def set_volume(self, new_volume, announce=True):
        """Set a bounded playback volume."""

        self.volume = self._bounded_volume(new_volume)
        self.display_percent = int(round(self.volume * 100))

        self.player.volume = self.volume

        if announce:
            self.status_message = (
                f"Volume set to {self.display_percent}%."
            )

    def reset_key_state(self):
        """Clear held-key tracking without changing the volume."""

        self.direction = 0
        self.started_at = 0.0
        self.last_key_at = 0.0
        self.repeat_count = 0
        self.start_level = self.volume
        self.hold_confirmed = False
        self.display_percent = int(round(self.volume * 100))

    def start_change(self, direction):
        """
        Process one Up or Down key event.

        A direction of 1 raises the volume. A direction of -1 lowers it.
        Distinct taps change the volume by 1%. Closely spaced repeat events
        confirm that the key is being held.
        """

        if direction not in (-1, 1):
            raise ValueError(
                "Volume direction must be either -1 or 1."
            )

        now = time.monotonic()

        new_gesture = (
            self.direction != direction
            or now - self.last_key_at > INITIAL_HOLD_TIMEOUT
        )

        if new_gesture:
            self.reset_key_state()

            self.direction = direction
            self.started_at = now
            self.last_key_at = now
            self.repeat_count = 1
            self.start_level = self.volume

            self.set_volume(
                self.volume + direction * VOLUME_TAP_STEP,
                announce=True,
            )
            return

        gap = now - self.last_key_at
        self.last_key_at = now
        self.repeat_count += 1

        if self.hold_confirmed:
            return

        if gap <= AUTO_REPEAT_GAP:
            # Rapid events indicate terminal auto-repeat. Preserve only the
            # initial 1% tap before beginning the held-volume sweep.
            self.hold_confirmed = True
            self.set_volume(
                self.start_level
                + direction * VOLUME_TAP_STEP,
                announce=False,
            )
            return

        # A slower event is treated as another deliberate 1% tap.
        self.set_volume(
            self.volume + direction * VOLUME_TAP_STEP,
            announce=True,
        )

    def update(self):
        """
        Update a held-volume gesture.

        Call this repeatedly from the application's main loop.
        """

        if self.direction == 0:
            return

        now = time.monotonic()

        if not self.hold_confirmed:
            if (
                now - self.last_key_at
                > INITIAL_HOLD_TIMEOUT
            ):
                self.reset_key_state()

            return

        if (
            now - self.last_key_at
            > REPEAT_RELEASE_TIMEOUT
        ):
            self.status_message = (
                f"Volume set to {self.display_percent}%."
            )
            self.reset_key_state()
            return

        held_for = now - self.started_at

        if held_for < VOLUME_HOLD_DELAY:
            return

        sweep_time = held_for - VOLUME_HOLD_DELAY

        initial_tap_level = (
            self.start_level
            + self.direction * VOLUME_TAP_STEP
        )

        target_volume = (
            initial_tap_level
            + self.direction
            * (sweep_time / VOLUME_SWEEP_SECONDS)
        )

        quantized_volume = self._bounded_volume(target_volume)

        if quantized_volume == self.volume:
            return

        self.set_volume(
            quantized_volume,
            announce=False,
        )

        direction_name = (
            "rising"
            if self.direction > 0
            else "falling"
        )

        self.status_message = (
            f"Volume {direction_name}: "
            f"{self.display_percent}%."
        )
