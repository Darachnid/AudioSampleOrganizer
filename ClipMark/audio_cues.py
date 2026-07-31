"""Play interface sounds for ClipMark."""

import threading
from pathlib import Path

import sounddevice as sd
import soundfile as sf


SUCCESS_CHIME_PATH = (
    Path(__file__).resolve().parent.parent / "success.opus"
)


def _play_audio_file(path):
    """Load and play one audio cue."""

    try:
        audio_data, sample_rate = sf.read(
            str(path),
            dtype="float32",
            always_2d=True,
        )

        sd.play(
            audio_data,
            samplerate=sample_rate,
            blocking=True,
        )

    except (
        OSError,
        RuntimeError,
        sd.PortAudioError,
        sf.LibsndfileError,
    ):
        # A missing or failed cue must not interrupt exporting.
        pass


def play_export_success_chime():
    """Play the successful-export cue without blocking the interface."""

    thread = threading.Thread(
        target=_play_audio_file,
        args=(SUCCESS_CHIME_PATH,),
        name="export-success-chime",
        daemon=True,
    )

    thread.start()
