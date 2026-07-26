# Libraries
import curses
import time
import wave
from pathlib import Path

import pyglet


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


export_directory = (
    audio_path.parent / "ExportedSamples"
)

export_directory.mkdir(
    parents=True,
    exist_ok=True,
)

export_directory = Path(
    "/home/manjo/pythonEnvs/SampleExtractionTool/ExportedSamples"
)

export_directory.mkdir(parents=True, exist_ok=True)


# General program values
is_playing = False
volume = 1.0

sample_start = None
sample_end = None

status_message = "Select a start and end time."


# Shuttle transport values
#
# shuttle_direction:
# -1 means reverse
#  0 means normal transport
#  1 means fast-forward

shuttle_direction = 0
shuttle_started_at = 0.0
shuttle_last_key_at = 0.0
shuttle_repeat_count = 0
shuttle_position = 0.0

resume_after_shuttle = False


# A held arrow key may not begin repeating immediately.
INITIAL_HOLD_TIMEOUT = 0.75

# Once repetition begins, a brief absence means the key was released.
REPEAT_RELEASE_TIMEOUT = 0.18


# Load audio
audio = pyglet.media.load(
    str(audio_path),
    streaming=True,
)

player = pyglet.media.Player()
player.queue(audio)
player.volume = volume


# Player functions

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

    if shuttle_direction != 0:
        stop_shuttle(resume=False)

    if is_playing:
        run_player("pause")
    else:
        run_player("play")


def control_gain(change):
    """Raise or lower playback volume."""

    global volume
    global status_message

    volume = max(
        0.0,
        min(volume + change, 1.0),
    )

    player.volume = volume

    status_message = (
        f"Volume set to {volume * 100:.0f}%."
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


def start_shuttle(direction):
    """
    Start or continue reverse or fast-forward shuttle.

    direction:
    -1 for reverse
     1 for fast-forward
    """

    global shuttle_direction
    global shuttle_started_at
    global shuttle_last_key_at
    global shuttle_repeat_count
    global shuttle_position
    global resume_after_shuttle
    global is_playing
    global status_message

    now = time.monotonic()

    # A repeated signal from the currently held key
    if shuttle_direction == direction:
        shuttle_last_key_at = now
        shuttle_repeat_count += 1
        return

    # Preserve whether normal playback should resume afterward.
    if shuttle_direction != 0:
        previous_resume_state = resume_after_shuttle
        stop_shuttle(resume=False)
    else:
        previous_resume_state = is_playing

    resume_after_shuttle = previous_resume_state

    player.pause()
    is_playing = False

    shuttle_direction = direction
    shuttle_started_at = now
    shuttle_last_key_at = now
    shuttle_repeat_count = 1
    shuttle_position = player.time

    if direction == -1:
        status_message = "Reverse shuttle started at 1x."
    else:
        status_message = "Forward shuttle started at 1x."


def update_shuttle(dt):
    """
    Move the playback position while an arrow key is held.

    dt is the amount of real time since the previous loop.
    """

    global shuttle_position
    global status_message

    if shuttle_direction == 0:
        return

    now = time.monotonic()

    # The first keyboard repeat usually takes longer to arrive.
    if shuttle_repeat_count <= 1:
        release_timeout = INITIAL_HOLD_TIMEOUT
    else:
        release_timeout = REPEAT_RELEASE_TIMEOUT

    # No more repeated key signals means the key was released.
    if now - shuttle_last_key_at > release_timeout:
        stop_shuttle()
        return

    speed = get_shuttle_speed()

    movement = shuttle_direction * speed * dt

    shuttle_position = max(
        0.0,
        min(shuttle_position + movement, audio.duration),
    )

    player.seek(shuttle_position)

    direction_name = (
        "Reverse"
        if shuttle_direction == -1
        else "Forward"
    )

    status_message = (
        f"{direction_name} shuttle at {speed:.0f}x."
    )

    # Stop automatically at either end.
    if shuttle_position <= 0.0:
        stop_shuttle(resume=False)
        status_message = "Beginning of recording reached."

    elif shuttle_position >= audio.duration:
        stop_shuttle(resume=False)
        status_message = "End of recording reached."


def stop_shuttle(resume=None):
    """Stop shuttle transport and optionally resume playback."""

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

    sample_start = player.time

    status_message = (
        f"Sample start set to "
        f"{format_time(sample_start)}."
    )


def select_end():
    """Save the current position as the sample end."""

    global sample_end
    global status_message

    sample_end = player.time

    status_message = (
        f"Sample end set to "
        f"{format_time(sample_end)}."
    )


def export_sample():
    """Export audio between the selected start and end."""

    global status_message

    if sample_start is None:
        status_message = (
            "Warning: Select a sample start before exporting."
        )
        return

    if sample_end is None:
        status_message = (
            "Warning: Select a sample end before exporting."
        )
        return

    if sample_end <= sample_start:
        status_message = (
            "Warning: The sample end must be after the start."
        )
        return

    try:
        with wave.open(str(audio_path), "rb") as source_audio:
            frame_rate = source_audio.getframerate()

            start_frame = int(
                sample_start * frame_rate
            )

            end_frame = int(
                sample_end * frame_rate
            )

            frame_count = end_frame - start_frame

            source_audio.setpos(start_frame)

            sample_frames = source_audio.readframes(
                frame_count
            )

            output_name = (
                f"sample_"
                f"{sample_start:.2f}-"
                f"{sample_end:.2f}.wav"
            )

            output_path = export_directory / output_name

            with wave.open(
                str(output_path),
                "wb",
            ) as output_audio:

                output_audio.setnchannels(
                    source_audio.getnchannels()
                )

                output_audio.setsampwidth(
                    source_audio.getsampwidth()
                )

                output_audio.setframerate(
                    frame_rate
                )

                output_audio.writeframes(
                    sample_frames
                )

        status_message = (
            f"Exported: {output_path.name}"
        )

    except (wave.Error, OSError) as error:
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

    if shuttle_direction == -1:
        speed = get_shuttle_speed()
        return f"Reverse {speed:.0f}x"

    if shuttle_direction == 1:
        speed = get_shuttle_speed()
        return f"Fast-forward {speed:.0f}x"

    if is_playing:
        return "Playing 1x"

    return "Paused"


def draw_screen(screen):
    """Draw the player information."""

    screen.erase()

    screen.addstr(
        0,
        0,
        "Sample Extraction Tool",
    )

    screen.addstr(
        1,
        0,
        f"File: {audio_path.name}",
    )

    screen.addstr(
        3,
        0,
        f"Transport: {get_transport_status()}",
    )

    screen.addstr(
        4,
        0,
        (
            f"Position:  "
            f"{format_time(player.time)} / "
            f"{format_time(audio.duration)}"
        ),
    )

    screen.addstr(
        5,
        0,
        f"Volume:    {volume * 100:.0f}%",
    )

    if sample_start is None:
        screen.addstr(
            7,
            0,
            "Start:     Not selected",
        )
    else:
        screen.addstr(
            7,
            0,
            f"Start:     {format_time(sample_start)}",
        )

    if sample_end is None:
        screen.addstr(
            8,
            0,
            "End:       Not selected",
        )
    else:
        screen.addstr(
            8,
            0,
            f"End:       {format_time(sample_end)}",
        )

    if (
        sample_start is not None
        and sample_end is not None
        and sample_end > sample_start
    ):
        selection_length = sample_end - sample_start

        screen.addstr(
            9,
            0,
            f"Length:    {format_time(selection_length)}",
        )

    screen.addstr(
        11,
        0,
        "Space       Play or pause",
    )

    screen.addstr(
        12,
        0,
        "Hold Left   Reverse shuttle: 1x, 2x, 4x, 8x",
    )

    screen.addstr(
        13,
        0,
        "Hold Right  Forward shuttle: 1x, 2x, 4x, 8x",
    )

    screen.addstr(
        14,
        0,
        "Up/Down     Raise or lower volume",
    )

    screen.addstr(
        15,
        0,
        "S           Select sample start",
    )

    screen.addstr(
        16,
        0,
        "E           Select sample end",
    )

    screen.addstr(
        17,
        0,
        "Enter       Export selected sample",
    )

    screen.addstr(
        18,
        0,
        "Q           Quit",
    )

    screen.addstr(
        20,
        0,
        f"Message: {status_message}",
    )

    screen.refresh()


# Keyboard controls

def control_transports(key):
    """Convert terminal keys into player actions."""

    if key == ord(" "):
        toggle_playback()

    elif key == curses.KEY_LEFT:
        start_shuttle(-1)

    elif key == curses.KEY_RIGHT:
        start_shuttle(1)

    elif key == curses.KEY_UP:
        control_gain(0.1)

    elif key == curses.KEY_DOWN:
        control_gain(-0.1)

    elif key in (
        ord("s"),
        ord("S"),
    ):
        select_start()

    elif key in (
        ord("e"),
        ord("E"),
    ):
        select_end()

    elif key in (
        curses.KEY_ENTER,
        10,
        13,
    ):
        if shuttle_direction != 0:
            stop_shuttle(resume=False)

        export_sample()

    elif key in (
        ord("q"),
        ord("Q"),
    ):
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
    previous_loop_time = time.monotonic()

    while running:
        current_loop_time = time.monotonic()
        dt = current_loop_time - previous_loop_time
        previous_loop_time = current_loop_time

        key = screen.getch()

        if key != -1:
            running = control_transports(key)

        update_shuttle(dt)

        pyglet.clock.tick()

        pyglet.app.platform_event_loop.dispatch_posted_events()
        pyglet.app.platform_event_loop.step(0)

        draw_screen(screen)

        time.sleep(0.02)

    player.pause()
    player.delete()


# Start program
if __name__ == "__main__":
    curses.wrapper(main)
