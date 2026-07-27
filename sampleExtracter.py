# Libraries
import curses
import json
import re
import threading
import time
from pathlib import Path

import numpy as np
import pyglet
import sounddevice as sd
import soundfile as sf


# Configure pyglet before accessing pyglet.media
pyglet.options["shadow_window"] = False


# File locations
audio_path = Path(
    input("Enter the full path to the WAV file:\n> ")
    .strip()
    .strip('"')
    .strip("'")
).expanduser().resolve()

if not audio_path.exists():
    raise FileNotFoundError(
        f"Audio file does not exist: {audio_path}"
    )

if not audio_path.is_file():
    raise ValueError(
        f"The supplied path is not a file: {audio_path}"
    )

if audio_path.suffix.lower() != ".wav":
    raise ValueError(
        "The sample exporter currently supports WAV files only."
    )

export_directory = audio_path.parent / "ExportedSamples"
export_directory.mkdir(parents=True, exist_ok=True)
metadata_path = export_directory / ".sample_metadata.json"


def load_metadata_store():
    """Load persisted source/name values keyed by audio file path."""

    if not metadata_path.exists():
        return {}

    try:
        with metadata_path.open("r", encoding="utf-8") as metadata_file:
            return json.load(metadata_file)
    except (OSError, json.JSONDecodeError):
        return {}


def save_metadata_store(metadata_store):
    """Persist source/name values keyed by audio file path."""

    with metadata_path.open("w", encoding="utf-8") as metadata_file:
        json.dump(metadata_store, metadata_file, indent=2)


def get_saved_file_metadata():
    """Return saved metadata for the current audio file."""

    metadata_store = load_metadata_store()
    return metadata_store.get(str(audio_path), {})


def save_file_metadata(sound_source, sample_name):
    """Remember only the sound source for the current audio file."""

    metadata_store = load_metadata_store()
    metadata_store[str(audio_path)] = {
        "sound_source": sound_source,
    }
    save_metadata_store(metadata_store)


# Read reliable WAV metadata, including 32-bit float WAV files.
with sf.SoundFile(str(audio_path), mode="r") as source_audio:
    audio_sample_rate = source_audio.samplerate
    audio_channels = source_audio.channels
    audio_total_frames = len(source_audio)
    audio_subtype = source_audio.subtype

audio_duration = audio_total_frames / audio_sample_rate


# General program values
is_playing = False
volume = 1.0

sample_start = None
sample_end = None

MODE_EDIT = "edit"
MODE_PREVIEW = "preview"
MODE_SOURCE = "source"
MODE_NAME = "name"
MODE_FINAL = "final"

export_mode = MODE_EDIT
sound_source_input = ""
sample_name_input = ""

status_message = "Select a start and end time."


# Marker cue tones
CUE_SAMPLE_RATE = 44100
START_CUE_HZ = 880.0
END_CUE_HZ = 660.0


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


# Volume-key values
#
# A tap changes the level by exactly one percentage point. Once keyboard
# repetition confirms that the key is held, the level follows a time-based
# ramp that traverses the complete 0%-100% range in 2.5 seconds.
VOLUME_TAP_STEP = 0.01
VOLUME_SWEEP_SECONDS = 2.5
VOLUME_HOLD_DELAY = 2.25

volume_direction = 0
volume_started_at = 0.0
volume_last_key_at = 0.0
volume_repeat_count = 0
volume_start_level = volume
volume_hold_confirmed = False
volume_display_percent = int(round(volume * 100))


# Load ordinary 1x playback through pyglet.
audio = pyglet.media.load(
    str(audio_path),
    streaming=True,
)

player = pyglet.media.Player()
player.queue(audio)
player.volume = volume


def play_marker_cue(frequency):
    """Play a short ping cue without interrupting transport."""

    duration = 0.12
    frame_count = int(CUE_SAMPLE_RATE * duration)
    time_axis = np.linspace(
        0.0,
        duration,
        frame_count,
        endpoint=False,
    )
    envelope = np.exp(-time_axis * 25.0)
    tone = (
        0.25
        * envelope
        * np.sin(2.0 * np.pi * frequency * time_axis)
    ).astype(np.float32)

    def cue_worker():
        try:
            sd.play(
                tone,
                CUE_SAMPLE_RATE,
                blocking=True,
            )
        except (OSError, RuntimeError, sd.PortAudioError):
            pass

    threading.Thread(
        target=cue_worker,
        name="marker-cue",
        daemon=True,
    ).start()


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


# Player and volume functions

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


def set_volume(new_volume, announce=True):
    """Set a bounded playback volume for all transport modes."""

    global volume
    global status_message
    global volume_display_percent

    volume = round(
        max(0.0, min(float(new_volume), 1.0)),
        2,
    )
    volume_display_percent = int(round(volume * 100))

    player.volume = volume

    if announce:
        status_message = (
            f"Volume set to {volume_display_percent}%."
        )


def reset_volume_key_state():
    """Clear held-volume key tracking without changing the volume."""

    global volume_direction
    global volume_started_at
    global volume_last_key_at
    global volume_repeat_count
    global volume_start_level
    global volume_hold_confirmed
    global volume_display_percent

    volume_direction = 0
    volume_started_at = 0.0
    volume_last_key_at = 0.0
    volume_repeat_count = 0
    volume_start_level = volume
    volume_hold_confirmed = False
    volume_display_percent = int(round(volume * 100))


def start_volume_change(direction):
    """
    Apply 1% for every distinct tap and track terminal auto-repeat.

    Curses reports key presses but not key releases. Events separated by more
    than AUTO_REPEAT_GAP are therefore treated as distinct taps. Closely spaced
    events confirm that the key is being held by terminal auto-repeat.
    """

    global volume_direction
    global volume_started_at
    global volume_last_key_at
    global volume_repeat_count
    global volume_start_level
    global volume_hold_confirmed

    now = time.monotonic()

    new_gesture = (
        volume_direction != direction
        or now - volume_last_key_at > INITIAL_HOLD_TIMEOUT
    )

    if new_gesture:
        reset_volume_key_state()

        volume_direction = direction
        volume_started_at = now
        volume_last_key_at = now
        volume_repeat_count = 1
        volume_start_level = volume

        set_volume(
            volume + direction * VOLUME_TAP_STEP,
            announce=True,
        )
        return

    gap = now - volume_last_key_at
    volume_last_key_at = now
    volume_repeat_count += 1

    if volume_hold_confirmed:
        return

    if gap <= AUTO_REPEAT_GAP:
        # Rapid events are terminal auto-repeat, not additional taps. Undo any
        # provisional repeat event and preserve only the first 1% tap.
        volume_hold_confirmed = True
        set_volume(
            volume_start_level
            + direction * VOLUME_TAP_STEP,
            announce=False,
        )
        return

    # A slower event is another deliberate press. It receives its own 1%.
    # If rapid repeat follows, the provisional increments are rolled back.
    set_volume(
        volume + direction * VOLUME_TAP_STEP,
        announce=True,
    )


def update_volume_change():
    """Run the held-volume sweep and detect key release."""

    global status_message
    global volume_display_percent

    if volume_direction == 0:
        return

    now = time.monotonic()

    if not volume_hold_confirmed:
        if now - volume_last_key_at > INITIAL_HOLD_TIMEOUT:
            reset_volume_key_state()
        return

    if now - volume_last_key_at > REPEAT_RELEASE_TIMEOUT:
        status_message = (
            f"Volume set to {volume_display_percent}%."
        )
        reset_volume_key_state()
        return

    held_for = now - volume_started_at

    if held_for < VOLUME_HOLD_DELAY:
        return

    sweep_time = held_for - VOLUME_HOLD_DELAY
    initial_tap_level = (
        volume_start_level
        + volume_direction * VOLUME_TAP_STEP
    )

    target_volume = (
        initial_tap_level
        + volume_direction
        * (sweep_time / VOLUME_SWEEP_SECONDS)
    )

    quantized_volume = round(
        max(0.0, min(float(target_volume), 1.0)),
        2,
    )

    if quantized_volume == volume:
        return

    set_volume(quantized_volume, announce=False)

    direction_name = (
        "rising"
        if volume_direction > 0
        else "falling"
    )

    status_message = (
        f"Volume {direction_name}: {volume_display_percent}%."
    )


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


# Sample selection functions

def select_start():
    """Save the current position as the sample start."""

    global sample_start
    global status_message

    sample_start = get_current_position()
    play_marker_cue(START_CUE_HZ)

    status_message = (
        f"Sample start set to "
        f"{format_time(sample_start)}."
    )


def select_end():
    """Save the current position as the sample end."""

    global sample_end
    global is_playing
    global status_message

    sample_end = get_current_position()
    play_marker_cue(END_CUE_HZ)

    player.pause()
    is_playing = False

    status_message = (
        f"Sample end set to "
        f"{format_time(sample_end)}."
    )


def validate_sample_selection():
    """Return whether start/end are ready for preview or export."""

    global status_message

    if sample_start is None:
        status_message = (
            "Warning: Select a sample start before exporting."
        )
        return False

    if sample_end is None:
        status_message = (
            "Warning: Select a sample end before exporting."
        )
        return False

    if sample_end <= sample_start:
        status_message = (
            "Warning: The sample end must be after the start."
        )
        return False

    return True


def in_export_wizard():
    """Return whether the export workflow is active."""

    return export_mode != MODE_EDIT


def sanitize_filename(name):
    """Return a filesystem-safe sample filename stem."""

    cleaned = re.sub(
        r"[^\w\- ]+",
        "",
        name.strip(),
        flags=re.UNICODE,
    )
    cleaned = re.sub(r"\s+", "_", cleaned)

    return cleaned or "sample"


def stop_transport_for_wizard():
    """Stop shuttle and preview transport before wizard steps."""

    if pending_shuttle_direction != 0:
        complete_pending_jump()

    if shuttle_direction != 0:
        stop_shuttle(resume=False)


def replay_sample_preview():
    """Replay the selected sample region."""

    global is_playing
    global status_message

    if not validate_sample_selection():
        return

    stop_transport_for_wizard()
    player.seek(sample_start)
    player.play()
    is_playing = True
    status_message = "Preview replaying."


def stop_sample_preview(seek_to_end=False):
    """Stop the selected-clip preview."""

    global preview_active
    global is_playing

    player.pause()
    preview_active = False
    is_playing = False

    if seek_to_end and sample_end is not None:
        player.seek(sample_end)


def begin_sample_preview():
    """Automatically preview the clip after the first Enter."""

    global export_mode
    global preview_active
    global is_playing
    global sample_name_input
    global status_message

    if not validate_sample_selection():
        return

    stop_transport_for_wizard()
    sample_name_input = ""
    export_mode = MODE_PREVIEW
    player.seek(sample_start)
    player.play()
    preview_active = True
    is_playing = True
    status_message = (
        "Preview playing. Enter continues; "
        "Right replays; another key returns to editing."
    )


def update_sample_preview():
    """Stop preview playback at the sample end."""

    global is_playing
    global status_message

    if export_mode != MODE_PREVIEW:
        return

    if (
        is_playing
        and get_current_position() >= sample_end
    ):
        player.pause()
        is_playing = False
        status_message = (
            "Preview complete. Enter to continue, "
            "Right to replay, any other key to adjust."
        )


def leave_preview_to_edit():
    """Return to marker editing from preview confirmation."""

    global export_mode
    global is_playing
    global status_message

    export_mode = MODE_EDIT
    player.pause()
    is_playing = False
    status_message = (
        "Adjust start and end, then press Enter to preview again."
    )


def return_to_preview_step():
    """Return to preview confirmation without clearing entries."""

    global export_mode
    global is_playing
    global status_message

    export_mode = MODE_PREVIEW
    player.pause()
    is_playing = False
    status_message = (
        "Back at preview. Enter to continue, "
        "Right to replay, any other key to adjust."
    )


def enter_source_step():
    """Move from preview confirmation to sound-source entry."""

    global export_mode
    global sound_source_input
    global is_playing
    global status_message

    saved_metadata = get_saved_file_metadata()

    if not sound_source_input:
        sound_source_input = saved_metadata.get(
            "sound_source",
            "",
        )

    export_mode = MODE_SOURCE
    player.pause()
    is_playing = False
    status_message = (
        "Enter sound source. Right replays preview, "
        "Enter continues, Left goes back."
    )


def enter_name_step():
    """Move to a blank sample-name field without autofill."""

    global export_mode
    global sample_name_input
    global status_message

    stop_sample_preview()
    sample_name_input = ""
    export_mode = MODE_NAME
    status_message = (
        "Enter the sample name. Enter continues; "
        "Left goes back; Right replays."
    )


def enter_final_step():
    """Move from name entry to final export confirmation."""

    global export_mode
    global status_message

    export_mode = MODE_FINAL
    status_message = (
        "Final confirmation. Enter exports, Left goes back, "
        "Down cancels."
    )


def cancel_export_wizard():
    """Cancel export workflow and keep all entered values."""

    global export_mode
    global is_playing
    global status_message

    export_mode = MODE_EDIT
    player.pause()
    is_playing = False
    status_message = (
        "Export cancelled. Markers and entries retained."
    )


def append_text_input(current_value, key):
    """Append printable text or apply backspace."""

    if key in (curses.KEY_BACKSPACE, 127, 8):
        return current_value[:-1]

    if 32 <= key <= 126:
        return current_value + chr(key)

    return current_value


def export_sample():
    """Export audio between the selected start and end."""

    global sample_start
    global sample_end
    global export_mode
    global is_playing
    global status_message
    global sample_name_input

    if not validate_sample_selection():
        return

    if not sound_source_input.strip():
        status_message = (
            "Warning: Enter a sound source before exporting."
        )
        export_mode = MODE_SOURCE
        return

    if not sample_name_input.strip():
        status_message = (
            "Warning: Enter a sample name before exporting."
        )
        export_mode = MODE_NAME
        return

    output_stem = sanitize_filename(sample_name_input)
    output_name = f"{output_stem}.wav"
    output_path = export_directory / output_name
    export_end = sample_end

    if output_path.exists():
        counter = 2
        while output_path.exists():
            output_name = f"{output_stem}_{counter}.wav"
            output_path = export_directory / output_name
            counter += 1

    try:
        with sf.SoundFile(str(audio_path), mode="r") as source_audio:
            start_frame = int(
                sample_start * source_audio.samplerate
            )
            end_frame = int(
                sample_end * source_audio.samplerate
            )
            frames_remaining = end_frame - start_frame

            source_audio.seek(start_frame)

            with sf.SoundFile(
                str(output_path),
                mode="w",
                samplerate=source_audio.samplerate,
                channels=source_audio.channels,
                format="WAV",
                subtype=audio_subtype,
            ) as output_audio:

                while frames_remaining > 0:
                    block_size = min(
                        65_536,
                        frames_remaining,
                    )

                    sample_frames = source_audio.read(
                        block_size,
                        dtype="float32",
                        always_2d=True,
                    )

                    if len(sample_frames) == 0:
                        break

                    output_audio.write(sample_frames)
                    frames_remaining -= len(sample_frames)

        save_file_metadata(
            sound_source_input.strip(),
            sample_name_input.strip(),
        )

        sample_start = None
        sample_end = None
        sample_name_input = ""
        export_mode = MODE_EDIT

        player.seek(export_end)
        player.play()
        is_playing = True
        status_message = (
            f"Exported: {output_path.name}. "
            f"Continuing from {format_time(export_end)}."
        )

    except (OSError, RuntimeError, sf.LibsndfileError) as error:
        status_message = (
            f"Export failed: {error}"
        )


# Display functions

def format_time(seconds):
    """Convert seconds into HH:MM:SS.s format."""

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


def get_transport_status():
    """Return the currently displayed transport status."""

    if export_mode == MODE_PREVIEW:
        if is_playing:
            return "Previewing sample"

        return "Preview paused"

    if export_mode == MODE_SOURCE:
        return "Entering sound source"

    if export_mode == MODE_NAME:
        return "Entering sample name"

    if export_mode == MODE_FINAL:
        return "Final export confirmation"

    if pending_shuttle_direction == -1:
        return "Left tap pending"

    if pending_shuttle_direction == 1:
        return "Right tap pending"

    if shuttle_direction == -1:
        speed = get_shuttle_speed()
        return f"Audible reverse {speed:.0f}x"

    if shuttle_direction == 1:
        speed = get_shuttle_speed()
        return f"Audible fast-forward {speed:.0f}x"

    if is_playing:
        return "Playing 1x"

    return "Paused"


def safe_addstr(screen, row, column, text):
    """Draw text without crashing in a terminal that is too small."""

    try:
        screen.addstr(row, column, text)
    except curses.error:
        pass


def build_output_stem():
    """Build the exported filename as source-name."""

    source_stem = sanitize_filename(sound_source_input)
    sample_stem = sanitize_filename(sample_name_input)
    return f"{source_stem}-{sample_stem}"


def draw_screen(screen):
    """Draw a compact interface with text entry at the bottom."""

    screen.erase()
    height, _ = screen.getmaxyx()

    safe_addstr(screen, 0, 0, "Sample Extraction Tool")
    safe_addstr(screen, 1, 0, f"File: {audio_path.name}")
    safe_addstr(screen, 2, 0, f"Export to: {export_directory.name}/")
    safe_addstr(screen, 3, 0, f"Transport: {get_transport_status()}")
    safe_addstr(
        screen,
        4,
        0,
        (
            f"Position:  {format_time(get_current_position())} / "
            f"{format_time(audio_duration)}"
        ),
    )
    safe_addstr(screen, 5, 0, f"Volume:    {volume_display_percent}%")

    if sample_start is None:
        safe_addstr(screen, 7, 0, "Start:     Not selected")
    else:
        safe_addstr(screen, 7, 0, f"Start:     {format_time(sample_start)}")

    if sample_end is None:
        safe_addstr(screen, 8, 0, "End:       Not selected")
    else:
        safe_addstr(screen, 8, 0, f"End:       {format_time(sample_end)}")

    if (
        sample_start is not None
        and sample_end is not None
        and sample_end > sample_start
    ):
        safe_addstr(
            screen,
            9,
            0,
            f"Length:    {format_time(sample_end - sample_start)}",
        )

    if export_mode == MODE_EDIT:
        controls = (
            "Space       Play/pause",
            "Left/Right  transport controls",
            "Up/Down     volume",
            "S           clip start",
            "E           clip end",
            "Enter       commit",
            "Q           Quit",
        )
    elif export_mode == MODE_PREVIEW:
        controls = (
            "Enter       continue",
            "Right       replay",
            "Other key   adjust clip",
            "Q           Quit",
        )
    elif export_mode in (MODE_SOURCE, MODE_NAME):
        controls = (
            "Enter       continue",
            "Left        back",
            "Right       replay",
            "Q           Quit",
        )
    else:
        controls = (
            "Enter       export",
            "Left        back",
            "Right       replay",
            "Down        cancel",
            "Q           Quit",
        )

    for row, line in enumerate(controls, start=11):
        safe_addstr(screen, row, 0, line)

    context_row = max(0, height - 4)
    input_row = max(0, height - 3)
    message_row = max(0, height - 1)

    if export_mode == MODE_SOURCE:
        safe_addstr(screen, input_row, 0, f"Source: {sound_source_input}_")
    elif export_mode == MODE_NAME:
        safe_addstr(screen, context_row, 0, f"Source: {sound_source_input}")
        safe_addstr(screen, input_row, 0, f"Name:   {sample_name_input}_")
    elif export_mode == MODE_FINAL:
        safe_addstr(
            screen,
            context_row,
            0,
            f"Source: {sound_source_input}    Name: {sample_name_input}",
        )
        safe_addstr(screen, input_row, 0, f"File: {build_output_stem()}.wav")

    safe_addstr(screen, message_row, 0, f"Message: {status_message}")
    screen.refresh()


# Keyboard controls

def handle_preview_keys(key):
    """Handle preview confirmation keys."""

    if key in (curses.KEY_ENTER, 10, 13):
        enter_source_step()
        return True

    if key == curses.KEY_RIGHT:
        replay_sample_preview()
        return True

    if key in (ord("q"), ord("Q")):
        return False

    leave_preview_to_edit()
    return True


def handle_source_keys(key):
    """Handle sound-source text entry."""

    global sound_source_input
    global status_message

    if key == curses.KEY_LEFT:
        return_to_preview_step()
        return True

    if key == curses.KEY_RIGHT:
        replay_sample_preview()
        return True

    if key in (curses.KEY_ENTER, 10, 13):
        if not sound_source_input.strip():
            status_message = (
                "Warning: Enter a sound source to continue."
            )
            return True

        enter_name_step()
        return True

    if key in (ord("q"), ord("Q")):
        return False

    updated_value = append_text_input(
        sound_source_input,
        key,
    )

    if updated_value != sound_source_input:
        sound_source_input = updated_value

    return True


def handle_name_keys(key):
    """Handle sample-name text entry."""

    global sample_name_input
    global status_message

    if key == curses.KEY_LEFT:
        enter_source_step()
        return True

    if key == curses.KEY_RIGHT:
        replay_sample_preview()
        return True

    if key in (curses.KEY_ENTER, 10, 13):
        if not sample_name_input.strip():
            status_message = (
                "Warning: Enter a sample name to continue."
            )
            return True

        enter_final_step()
        return True

    if key in (ord("q"), ord("Q")):
        return False

    updated_value = append_text_input(
        sample_name_input,
        key,
    )

    if updated_value != sample_name_input:
        sample_name_input = updated_value

    return True


def handle_final_keys(key):
    """Handle final export confirmation."""

    if key in (curses.KEY_ENTER, 10, 13):
        export_sample()
        return True

    if key == curses.KEY_LEFT:
        enter_name_step()
        return True

    if key == curses.KEY_DOWN:
        cancel_export_wizard()
        return True

    if key == curses.KEY_RIGHT:
        replay_sample_preview()
        return True

    if key in (ord("q"), ord("Q")):
        return False

    return True


def control_transports(key):
    """Convert terminal keys into player actions."""

    if export_mode == MODE_PREVIEW:
        return handle_preview_keys(key)

    if export_mode == MODE_SOURCE:
        return handle_source_keys(key)

    if export_mode == MODE_NAME:
        return handle_name_keys(key)

    if export_mode == MODE_FINAL:
        return handle_final_keys(key)

    if key == ord(" "):
        toggle_playback()

    elif key == curses.KEY_LEFT:
        start_shuttle(-1)

    elif key == curses.KEY_RIGHT:
        start_shuttle(1)

    elif key == curses.KEY_UP:
        start_volume_change(1)

    elif key == curses.KEY_DOWN:
        start_volume_change(-1)

    elif key in (ord("s"), ord("S")):
        select_start()

    elif key in (ord("e"), ord("E")):
        select_end()

    elif key in (curses.KEY_ENTER, 10, 13):
        if shuttle_direction != 0:
            stop_shuttle(resume=False)

        begin_sample_preview()

    elif key in (ord("q"), ord("Q")):
        return False

    return True


# Main loop

def main(screen):
    """Run the terminal player."""

    try:
        curses.curs_set(0)
    except curses.error:
        pass

    screen.nodelay(True)
    screen.keypad(True)

    running = True

    try:
        while running:
            key = screen.getch()

            if key != -1:
                running = control_transports(key)

            update_shuttle()
            update_volume_change()
            update_sample_preview()

            pyglet.clock.tick()
            pyglet.app.platform_event_loop.dispatch_posted_events()
            pyglet.app.platform_event_loop.step(0)

            draw_screen(screen)
            time.sleep(0.02)

    finally:
        global export_mode

        reset_volume_key_state()
        clear_pending_shuttle()
        export_mode = MODE_EDIT

        if shuttle_direction != 0:
            stop_shuttle(resume=False)

        player.pause()
        player.delete()


# Start program
if __name__ == "__main__":
    curses.wrapper(main)
