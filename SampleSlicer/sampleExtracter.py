"""Start the SampleSlicer terminal application."""

import curses
import time

import pyglet

from SampleSlicer.audio_import import load_audio
from SampleSlicer.clip_export import ClipExporter
from SampleSlicer.clip_selection import ClipSelection
from SampleSlicer.logic_control import LogicControl
from SampleSlicer.metadata_collection import MetadataCollection
from SampleSlicer.terminal_ui import TerminalUI
from SampleSlicer.volume_control import VolumeControl
from SampleSlicer import transport_control


def configure_transport(audio_data):
    """Supply the audio resources required by transport_control."""

    transport_control.audio_path = audio_data["path"]
    transport_control.audio_duration = audio_data["duration"]
    transport_control.audio_sample_rate = audio_data["sample_rate"]
    transport_control.audio_channels = audio_data["channels"]
    transport_control.audio_total_frames = audio_data["total_frames"]

    transport_control.player = audio_data["player"]
    transport_control.volume = 1.0
    transport_control.is_playing = False
    transport_control.status_message = "Playback ready."


def stop_transport_for_wizard():
    """Resolve pending seeks and stop active shuttle playback."""

    if transport_control.pending_shuttle_direction != 0:
        transport_control.complete_pending_jump()

    if transport_control.shuttle_direction != 0:
        transport_control.stop_shuttle(resume=False)


def run_application(screen, audio_data):
    """Create the application components and run the curses loop."""

    configure_transport(audio_data)

    player = audio_data["player"]

    export_directory = (
        audio_data["path"].parent
        / "ExportedSamples"
    )

    metadata_path = (
        export_directory
        / ".sample_metadata.json"
    )

    volume_control = VolumeControl(
        player=player,
        initial_volume=1.0,
    )

    clip_selection = ClipSelection(
        player=player,
        get_position=transport_control.get_current_position,
        stop_transport=stop_transport_for_wizard,
    )

    metadata = MetadataCollection(
        audio_path=audio_data["path"],
        metadata_path=metadata_path,
    )

    clip_exporter = ClipExporter(
        audio_path=audio_data["path"],
        audio_subtype=audio_data["subtype"],
        export_directory=export_directory,
        clip_selection=clip_selection,
        metadata=metadata,
        player=player,
    )

    logic = LogicControl(
        transport=transport_control,
        volume_control=volume_control,
        clip_selection=clip_selection,
        metadata=metadata,
        clip_exporter=clip_exporter,
    )

    ui = TerminalUI(
        screen=screen,
        audio_data=audio_data,
        logic=logic,
        transport=transport_control,
        volume_control=volume_control,
        clip_selection=clip_selection,
        metadata=metadata,
        clip_exporter=clip_exporter,
    )

    ui.configure_screen()

    try:
        while logic.running:
            key = screen.getch()

            if key != -1:
                logic.handle_key(key)

            logic.update()

            # Shuttle playback still reads its volume from the transport
            # module, so synchronize it with the separate volume controller.
            transport_control.volume = volume_control.volume

            pyglet.clock.tick()
            pyglet.app.platform_event_loop.dispatch_posted_events()
            pyglet.app.platform_event_loop.step(0)

            ui.draw()
            time.sleep(0.02)

    finally:
        logic.shutdown()
        player.pause()
        player.delete()


def main():
    """Prompt normally, then start the curses interface."""

    # This runs in the ordinary terminal before curses starts.
    audio_data = load_audio(volume=1.0)

    # Pass the loaded audio into the curses application.
    curses.wrapper(
        run_application,
        audio_data,
    )


if __name__ == "__main__":
    main()
