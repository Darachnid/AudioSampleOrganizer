"""Export the selected clip and determine its output location."""

import re

import soundfile as sf


class ClipExporter:
    """Write selected audio frames to a new WAV file."""

    def __init__(
        self,
        audio_path,
        audio_subtype,
        export_directory,
        clip_selection,
        metadata,
        player,
        play_success_chime=None,
    ):
        self.play_success_chime = play_success_chime
        self.audio_path = audio_path
        self.audio_subtype = audio_subtype
        self.export_directory = export_directory
        self.clip_selection = clip_selection
        self.metadata = metadata
        self.player = player

        self.status_message = ""

        self.export_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

    @staticmethod
    def sanitize_filename(name):
        """Return a filesystem-safe filename stem."""

        cleaned = re.sub(
            r"[^\w\- ]+",
            "",
            name.strip(),
            flags=re.UNICODE,
        )

        cleaned = re.sub(
            r"\s+",
            "_",
            cleaned,
        )

        return cleaned or "sample"

    def build_output_stem(self):
        """Build an exported filename from source and sample name."""

        source_stem = self.sanitize_filename(
            self.metadata.sound_source
        )

        sample_stem = self.sanitize_filename(
            self.metadata.sample_name
        )

        return f"{source_stem}-{sample_stem}"

    def get_sort_directory(self):
        """
        Return the directory where the clip should be exported.

        Currently all clips go directly into ExportedSamples. This method
        provides a single place to add type and spectral sorting later.
        """

        return self.export_directory

    def get_unique_output_path(self):
        """Return an unused WAV path for the current metadata."""

        output_directory = self.get_sort_directory()

        output_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        output_stem = self.build_output_stem()
        output_path = output_directory / f"{output_stem}.wav"

        counter = 2

        while output_path.exists():
            output_path = (
                output_directory
                / f"{output_stem}_{counter}.wav"
            )
            counter += 1

        return output_path

    def validate(self):
        """Return whether clip selection and metadata are export-ready."""

        if not self.clip_selection.validate():
            self.status_message = (
                self.clip_selection.status_message
            )
            return False

        if not self.metadata.validate():
            self.status_message = (
                self.metadata.status_message
            )
            return False

        return True

    def export(self):
        """
        Export audio between the selected start and end markers.

        Returns the output path after success, otherwise None.
        """

        if not self.validate():
            return None

        output_path = self.get_unique_output_path()
        export_end = self.clip_selection.end

        try:
            with sf.SoundFile(
                str(self.audio_path),
                mode="r",
            ) as source_audio:

                start_frame = int(
                    self.clip_selection.start
                    * source_audio.samplerate
                )

                end_frame = int(
                    self.clip_selection.end
                    * source_audio.samplerate
                )

                frames_remaining = (
                    end_frame - start_frame
                )

                source_audio.seek(start_frame)

                with sf.SoundFile(
                    str(output_path),
                    mode="w",
                    samplerate=source_audio.samplerate,
                    channels=source_audio.channels,
                    format="WAV",
                    subtype=self.audio_subtype,
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

                        frames_remaining -= len(
                            sample_frames
                        )

            self.metadata.save_file_metadata()
            self.clip_selection.clear_after_export()
            self.metadata.clear_sample_fields()

            self.player.seek(export_end)
            self.player.play()

            self.status_message = (
                f"Exported: {output_path.name}. "
                f"Continuing from {export_end:.1f} seconds."
            )
            if self.play_success_chime is not None:
                self.play_success_chime()

            return output_path

        except (
            OSError,
            RuntimeError,
            sf.LibsndfileError,
        ) as error:
            self.status_message = (
                f"Export failed: {error}"
            )

            return None
