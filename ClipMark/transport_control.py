import threading
import time

import numpy as np
import sounddevice as sd
import soundfile as sf


# Held-key timing
#
# A terminal reports a held key as an initial key event followed by repeated
# key events. The longer timeout allows time for that first repeat to arrive.
INITIAL_HOLD_TIMEOUT = 0.75
REPEAT_RELEASE_TIMEOUT = 0.18

# Once terminal auto-repeat begins, repeated events arrive much closer
# together than deliberate taps. This threshold distinguishes the two.
AUTO_REPEAT_GAP = 0.12

# A released Left or Right tap moves by this many seconds.
TAP_JUMP_SECONDS = 5.0


# Shuttle transport values
#
# shuttle_direction:
# -1 means audible reverse
#  0 means normal transport
#  1 means audible fast-forward
shuttle_direction = 0
shuttle_started_at = 0.0
shuttle_last_key_at = 0.0
shuttle_repeat_count = 0
shuttle_position = 0.0
resume_after_shuttle = False

# Before auto-repeat is confirmed, an arrow press remains pending. A released
# press becomes a 5-second jump; rapid repeat events turn it into a shuttle.
pending_shuttle_direction = 0
pending_shuttle_started_at = 0.0
pending_shuttle_last_key_at = 0.0
pending_shuttle_tap_count = 0
pending_shuttle_origin = 0.0
pending_shuttle_resume = False

SHUTTLE_BLOCK_FRAMES = 1024

shuttle_thread = None
shuttle_stop_event = threading.Event()
shuttle_position_lock = threading.Lock()
shuttle_hit_boundary = False
shuttle_error_message = None


# Position functions

def set_shuttle_position(position):
    """Set the shared shuttle position safely."""

    global shuttle_position

    bounded_position = max(
        0.0,
        min(float(position), audio_duration),
    )

    with shuttle_position_lock:
        shuttle_position = bounded_position


def get_shuttle_position():
    """Return the shared shuttle position safely."""

    with shuttle_position_lock:
        return shuttle_position


def get_current_position():
    """Return the position used by the active transport."""

    if shuttle_direction != 0:
        return get_shuttle_position()

    return max(
        0.0,
        min(float(player.time), audio_duration),
    )


# Normal player functions

def run_player(status):
    """Perform a normal playback action."""

    global is_playing
    global status_message

    if status == "play":
        player.play()
        is_playing = True
        status_message = "Playback started."

    elif status == "pause":
        player.pause()
        is_playing = False
        status_message = "Playback paused."

    else:
        raise ValueError(
            f"Unknown playback status: {status}"
        )


def toggle_playback():
    """Switch between normal playback and pause."""

    if pending_shuttle_direction != 0:
        complete_pending_jump()

    if shuttle_direction != 0:
        stop_shuttle(resume=False)

    if is_playing:
        run_player("pause")
    else:
        run_player("play")


# Shuttle functions

def get_shuttle_speed():
    """Return shuttle speed based on hold duration."""

    if shuttle_direction == 0:
        return 1.0

    held_for = time.monotonic() - shuttle_started_at

    if held_for < 1.0:
        return 1.0

    if held_for < 2.0:
        return 2.0

    if held_for < 3.0:
        return 4.0

    return 8.0


def prepare_preview_channels(audio_block):
    """Return mono or stereo data suitable for the output device."""

    if audio_block.shape[1] <= 2:
        return audio_block

    # For multichannel recordings, preview the first stereo pair.
    return audio_block[:, :2]


def shuttle_playback_worker(direction):
    """Play forward or backward blocks with tape-like speed changes."""

    global shuttle_hit_boundary
    global shuttle_error_message

    output_channels = min(audio_channels, 2)

    try:
        with sf.SoundFile(str(audio_path), mode="r") as shuttle_source:
            with sd.OutputStream(
                samplerate=audio_sample_rate,
                channels=output_channels,
                dtype="float32",
                blocksize=SHUTTLE_BLOCK_FRAMES,
                latency="low",
            ) as shuttle_stream:

                while not shuttle_stop_event.is_set():
                    speed = int(get_shuttle_speed())

                    current_frame = int(
                        get_shuttle_position()
                        * audio_sample_rate
                    )

                    source_frame_count = (
                        SHUTTLE_BLOCK_FRAMES * speed
                    )

                    if direction < 0:
                        if current_frame <= 0:
                            shuttle_hit_boundary = True
                            shuttle_stop_event.set()
                            break

                        start_frame = max(
                            0,
                            current_frame - source_frame_count,
                        )
                        end_frame = current_frame

                        shuttle_source.seek(start_frame)
                        audio_block = shuttle_source.read(
                            end_frame - start_frame,
                            dtype="float32",
                            always_2d=True,
                        )

                        if len(audio_block) == 0:
                            shuttle_hit_boundary = True
                            shuttle_stop_event.set()
                            break

                        # Reverse frame order without swapping channels.
                        audio_block = audio_block[::-1]
                        next_frame = start_frame

                    else:
                        if current_frame >= audio_total_frames:
                            shuttle_hit_boundary = True
                            shuttle_stop_event.set()
                            break

                        start_frame = current_frame
                        end_frame = min(
                            audio_total_frames,
                            current_frame + source_frame_count,
                        )

                        shuttle_source.seek(start_frame)
                        audio_block = shuttle_source.read(
                            end_frame - start_frame,
                            dtype="float32",
                            always_2d=True,
                        )

                        if len(audio_block) == 0:
                            shuttle_hit_boundary = True
                            shuttle_stop_event.set()
                            break

                        next_frame = end_frame

                    # Discarding frames produces the classic tape-machine
                    # shuttle effect: faster playback with a higher pitch.
                    if speed > 1:
                        audio_block = audio_block[::speed]

                    audio_block = prepare_preview_channels(audio_block)
                    audio_block = np.ascontiguousarray(
                        audio_block * volume,
                        dtype=np.float32,
                    )

                    set_shuttle_position(
                        next_frame / audio_sample_rate
                    )

                    shuttle_stream.write(audio_block)

                    if (
                        direction < 0
                        and next_frame <= 0
                    ) or (
                        direction > 0
                        and next_frame >= audio_total_frames
                    ):
                        shuttle_hit_boundary = True
                        shuttle_stop_event.set()
                        break

    except (
        OSError,
        RuntimeError,
        sd.PortAudioError,
        sf.LibsndfileError,
    ) as error:
        shuttle_hit_boundary = False
        shuttle_error_message = str(error)
        shuttle_stop_event.set()


def start_shuttle_audio(direction):
    """Start the audible shuttle worker in the requested direction."""

    global shuttle_thread
    global shuttle_hit_boundary
    global shuttle_error_message

    shuttle_stop_event.clear()
    shuttle_hit_boundary = False
    shuttle_error_message = None

    shuttle_thread = threading.Thread(
        target=shuttle_playback_worker,
        args=(direction,),
        name=(
            "reverse-shuttle"
            if direction < 0
            else "forward-shuttle"
        ),
        daemon=True,
    )
    shuttle_thread.start()


def stop_shuttle_audio():
    """Stop and join the audible shuttle worker."""

    global shuttle_thread

    shuttle_stop_event.set()

    if (
        shuttle_thread is not None
        and shuttle_thread.is_alive()
        and threading.current_thread() is not shuttle_thread
    ):
        shuttle_thread.join(timeout=0.5)

    shuttle_thread = None


def clear_pending_shuttle():
    """Clear an undecided Left/Right tap without moving playback."""

    global pending_shuttle_direction
    global pending_shuttle_started_at
    global pending_shuttle_last_key_at
    global pending_shuttle_tap_count
    global pending_shuttle_origin
    global pending_shuttle_resume

    pending_shuttle_direction = 0
    pending_shuttle_started_at = 0.0
    pending_shuttle_last_key_at = 0.0
    pending_shuttle_tap_count = 0
    pending_shuttle_origin = 0.0
    pending_shuttle_resume = False


def complete_pending_jump():
    """Turn pending Left/Right taps into one or more 5-second jumps."""

    global is_playing
    global status_message

    if pending_shuttle_direction == 0:
        return

    direction = pending_shuttle_direction
    tap_count = pending_shuttle_tap_count
    origin = pending_shuttle_origin
    should_resume = pending_shuttle_resume

    jump_seconds = (
        direction
        * TAP_JUMP_SECONDS
        * tap_count
    )

    new_position = max(
        0.0,
        min(origin + jump_seconds, audio_duration),
    )

    clear_pending_shuttle()
    player.seek(new_position)

    if should_resume:
        player.play()
        is_playing = True
    else:
        player.pause()
        is_playing = False

    direction_name = (
        "forward"
        if direction > 0
        else "backward"
    )

    status_message = (
        f"Jumped {direction_name} "
        f"{abs(jump_seconds):.0f} seconds."
    )


def begin_confirmed_shuttle(
    direction,
    start_position,
    started_at,
    last_key_at,
    should_resume,
):
    """Start audible shuttle after terminal auto-repeat is confirmed."""

    global shuttle_direction
    global shuttle_started_at
    global shuttle_last_key_at
    global shuttle_repeat_count
    global resume_after_shuttle
    global is_playing
    global status_message

    clear_pending_shuttle()

    player.pause()
    is_playing = False

    shuttle_direction = direction
    shuttle_started_at = started_at
    shuttle_last_key_at = last_key_at
    shuttle_repeat_count = 2
    resume_after_shuttle = should_resume
    set_shuttle_position(start_position)

    start_shuttle_audio(direction)

    if direction < 0:
        status_message = "Audible reverse started at 1x."
    else:
        status_message = "Audible fast-forward started at 1x."


def start_shuttle(direction):
    """
    Start an arrow-key gesture.

    A released tap jumps five seconds. Closely spaced terminal repeat events
    confirm a hold and begin audible reverse or fast-forward.
    """

    global pending_shuttle_direction
    global pending_shuttle_started_at
    global pending_shuttle_last_key_at
    global pending_shuttle_tap_count
    global pending_shuttle_origin
    global pending_shuttle_resume
    global shuttle_last_key_at
    global shuttle_repeat_count
    global is_playing
    global status_message

    now = time.monotonic()

    # Continue an already confirmed audible shuttle.
    if shuttle_direction == direction:
        shuttle_last_key_at = now
        shuttle_repeat_count += 1
        return

    # Changing direction while shuttling stops the old direction first.
    if shuttle_direction != 0:
        stop_shuttle()

    if pending_shuttle_direction == direction:
        gap = now - pending_shuttle_last_key_at
        pending_shuttle_last_key_at = now

        if gap <= AUTO_REPEAT_GAP:
            begin_confirmed_shuttle(
                direction=direction,
                start_position=pending_shuttle_origin,
                started_at=pending_shuttle_started_at,
                last_key_at=now,
                should_resume=pending_shuttle_resume,
            )
            return

        # Another slower press is another five-second tap. If rapid repeat
        # follows, these provisional taps are discarded in favor of shuttle.
        pending_shuttle_tap_count += 1
        status_message = (
            f"{pending_shuttle_tap_count} "
            f"five-second jump taps pending."
        )
        return

    # Resolve a pending gesture in the opposite direction before starting.
    if pending_shuttle_direction != 0:
        complete_pending_jump()

    pending_shuttle_direction = direction
    pending_shuttle_started_at = now
    pending_shuttle_last_key_at = now
    pending_shuttle_tap_count = 1
    pending_shuttle_origin = get_current_position()
    pending_shuttle_resume = is_playing

    # Pause at the exact origin while deciding whether this is a tap or hold.
    player.pause()
    is_playing = False

    if direction < 0:
        status_message = "Left tap pending: jump back 5 seconds."
    else:
        status_message = "Right tap pending: jump forward 5 seconds."


def update_shuttle():
    """Resolve taps, update shuttle status, and detect key release."""

    global status_message

    now = time.monotonic()

    if shuttle_direction == 0:
        if (
            pending_shuttle_direction != 0
            and now - pending_shuttle_last_key_at
            > INITIAL_HOLD_TIMEOUT
        ):
            complete_pending_jump()

        return

    # A confirmed shuttle receives rapid repeat events. Their absence means
    # the arrow was released.
    if now - shuttle_last_key_at > REPEAT_RELEASE_TIMEOUT:
        stop_shuttle()
        return

    speed = get_shuttle_speed()
    direction = shuttle_direction

    if direction < 0:
        status_message = (
            f"Audible reverse at {speed:.0f}x."
        )
    else:
        status_message = (
            f"Audible fast-forward at {speed:.0f}x."
        )

    if shuttle_hit_boundary:
        stop_shuttle(resume=False)

        if direction < 0:
            status_message = "Beginning of recording reached."
        else:
            status_message = "End of recording reached."

    elif shuttle_stop_event.is_set():
        error_message = shuttle_error_message
        stop_shuttle(resume=False)

        if error_message:
            status_message = (
                f"Shuttle playback failed: {error_message}"
            )


def stop_shuttle(resume=None):
    """Stop shuttle transport and optionally resume normal playback."""

    global shuttle_direction
    global shuttle_started_at
    global shuttle_last_key_at
    global shuttle_repeat_count
    global resume_after_shuttle
    global is_playing
    global status_message

    if shuttle_direction == 0:
        return

    if resume is None:
        should_resume = resume_after_shuttle
    else:
        should_resume = resume

    stop_shuttle_audio()

    final_position = get_shuttle_position()
    player.seek(final_position)

    shuttle_direction = 0
    shuttle_started_at = 0.0
    shuttle_last_key_at = 0.0
    shuttle_repeat_count = 0
    resume_after_shuttle = False

    if should_resume:
        player.play()
        is_playing = True
        status_message = "Normal playback resumed."

    else:
        player.pause()
        is_playing = False
        status_message = "Shuttle stopped."
