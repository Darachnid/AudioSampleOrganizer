"""Load and validate the source WAV file and create the normal audio player."""

from pathlib import Path

import pyglet
import soundfile as sf


# Configure pyglet before accessing pyglet.media.
pyglet.options["shadow_window"] = False


def get_audio_path():
    """Prompt for and validate a WAV file path."""

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

    return audio_path


def read_audio_metadata(audio_path):
    """
    Read reliable WAV metadata.

    This supports WAV files using formats such as 32-bit floating point.
    """

    with sf.SoundFile(str(audio_path), mode="r") as source_audio:
        sample_rate = source_audio.samplerate
        channels = source_audio.channels
        total_frames = len(source_audio)
        subtype = source_audio.subtype

    duration = total_frames / sample_rate

    return {
        "sample_rate": sample_rate,
        "channels": channels,
        "total_frames": total_frames,
        "subtype": subtype,
        "duration": duration,
    }


def create_player(audio_path, volume=1.0):
    """Create and configure the ordinary 1x pyglet player."""

    audio = pyglet.media.load(
        str(audio_path),
        streaming=True,
    )

    player = pyglet.media.Player()
    player.queue(audio)
    player.volume = volume

    return audio, player


def load_audio(volume=1.0):
    """
    Load the selected WAV file and return all audio resources.

    Returns a dictionary so the calling application can pass the values to
    transport, selection, export, and UI modules.
    """

    audio_path = get_audio_path()
    metadata = read_audio_metadata(audio_path)
    audio, player = create_player(audio_path, volume)

    return {
        "path": audio_path,
        "audio": audio,
        "player": player,
        "sample_rate": metadata["sample_rate"],
        "channels": metadata["channels"],
        "total_frames": metadata["total_frames"],
        "subtype": metadata["subtype"],
        "duration": metadata["duration"],
    }
