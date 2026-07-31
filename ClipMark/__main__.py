"""Start and assemble the modular ClipMark application."""

import curses
import time
from pathlib import Path

import pyglet

from ClipMark.audio_cues import play_export_success_chime
from ClipMark.audio_import import load_audio
from ClipMark.clip_export import ClipExporter
from ClipMark.clip_selection import ClipSelection
from ClipMark.logic_control import LogicControl
from ClipMark.metadata_collection import MetadataCollection
from ClipMark.speech_output import SpeechOutput
from ClipMark.terminal_ui import TerminalUI
from ClipMark.volume_control import VolumeControl
import ClipMark.transport_control as transport


def configure_transport(audio_data, initial_volume):
    """Supply the transport module with the active audio resources."""

    transport.audio_path = audio_data["path"]
    transport.audio_duration = audio_data["duration"]
    transport.audio_sample_rate = audio_data["sample_rate"]
    transport.audio_channels = audio_data["channels"]
    transport.audio_total_frames = audio_data["total_frames"]

    transport.player = audio_data["player"]

    transport.volume = initial_volume
    transport.is_playing = False
    transport.status_message = "Playback paused."


def stop_transport():
    """Resolve pending movement and stop active shuttle playback."""

    if transport.pending_shuttle_direction != 0:
        transport.complete_pending_jump()

    if transport.shuttle_direction != 0:
        transport.stop_shuttle(resume=False)


def run_application(screen, audio_data):
    """Run the curses application using the modular controllers."""

    player = audio_data["player"]

    volume_control = VolumeControl(
        player=player,
        initial_volume=1.0,
    )

    configure_transport(
        audio_data=audio_data,
        initial_volume=volume_control.volume,
    )

    project_root = Path(__file__).resolve().parent.parent

    metadata_path = (
        project_root
        / "sample_metadata.json"
    )

    export_directory = (
        project_root
        / "ExportedSamples"
    )

    metadata = MetadataCollection(
        audio_path=audio_data["path"],
        metadata_path=metadata_path,
    )

    clip_selection = ClipSelection(
        player=player,
        get_position=transport.get_current_position,
        stop_transport=stop_transport,
    )

    clip_exporter = ClipExporter(
        audio_path=audio_data["path"],
        audio_subtype=audio_data["subtype"],
        export_directory=export_directory,
        clip_selection=clip_selection,
        metadata=metadata,
        player=player,
        play_success_chime=play_export_success_chime,
    )

    speech = SpeechOutput(volume_percent=80)

    logic = LogicControl(
        transport=transport,
        volume_control=volume_control,
        clip_selection=clip_selection,
        metadata=metadata,
        clip_exporter=clip_exporter,
        speech=speech,
    )

    terminal_ui = TerminalUI(
        screen=screen,
        audio_data=audio_data,
        logic=logic,
        transport=transport,
        volume_control=volume_control,
        clip_selection=clip_selection,
        metadata=metadata,
        clip_exporter=clip_exporter,
    )

    logic.set_status_ui(terminal_ui)
    terminal_ui.configure_screen()
    speech.speak(
        "ClipMark ready. Press E for status, Shift E for detailed help."
    )

    try:
        while logic.running:
            key = screen.getch()

            if key != -1:
                logic.handle_key(key)

            logic.update()

            # Shuttle playback uses transport.volume instead of
            # pyglet's player.volume, so keep both values synchronized.
            transport.volume = volume_control.volume

            pyglet.clock.tick()
            pyglet.app.platform_event_loop.dispatch_posted_events()
            pyglet.app.platform_event_loop.step(0)

            terminal_ui.draw()
            time.sleep(0.02)

    finally:
        logic.shutdown()

        player.pause()
        player.delete()


def main():
    """Load the WAV before curses takes control of the terminal."""

    audio_data = load_audio(volume=1.0)

    curses.wrapper(
        run_application,
        audio_data,
    )


if __name__ == "__main__":
    main()
