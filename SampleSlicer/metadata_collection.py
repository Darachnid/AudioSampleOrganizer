"""Collect, validate, and persist sample metadata."""

import json


class MetadataCollection:
    """Own metadata entry and saved source values for the current audio file."""

    def __init__(self, audio_path, metadata_path):
        self.audio_path = audio_path
        self.metadata_path = metadata_path

        self.sound_source = ""
        self.sample_name = ""

        # Reserved for later classification fields.
        self.sample_type = ""
        self.spectral_classification = ""
        self.additional_metadata = {}

        self.status_message = ""

    def load_store(self):
        """Load the complete persisted metadata store."""

        if not self.metadata_path.exists():
            return {}

        try:
            with self.metadata_path.open(
                "r",
                encoding="utf-8",
            ) as metadata_file:
                return json.load(metadata_file)

        except (OSError, json.JSONDecodeError):
            return {}

    def save_store(self, metadata_store):
        """Write the complete metadata store to disk."""

        self.metadata_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with self.metadata_path.open(
            "w",
            encoding="utf-8",
        ) as metadata_file:
            json.dump(
                metadata_store,
                metadata_file,
                indent=2,
            )

    def get_saved_file_metadata(self):
        """Return saved metadata for the current source recording."""

        metadata_store = self.load_store()

        return metadata_store.get(
            str(self.audio_path),
            {},
        )

    def load_saved_source(self):
        """Load the remembered sound source for this recording."""

        saved_metadata = self.get_saved_file_metadata()

        if not self.sound_source:
            self.sound_source = saved_metadata.get(
                "sound_source",
                "",
            )

        return self.sound_source

    def save_file_metadata(self):
        """
        Save reusable metadata for the current source recording.

        The sample name is not persisted because every exported clip should
        receive a new name. The sound source can be reused across clips from
        the same long recording.
        """

        metadata_store = self.load_store()

        metadata_store[str(self.audio_path)] = {
            "sound_source": self.sound_source.strip(),
        }

        self.save_store(metadata_store)

    def set_sound_source(self, value):
        """Set the current sound-source text."""

        self.sound_source = value

    def set_sample_name(self, value):
        """Set the current sample-name text."""

        self.sample_name = value

    def append_to_sound_source(self, key):
        """Apply one text-input key to the sound-source field."""

        self.sound_source = self.append_text_input(
            self.sound_source,
            key,
        )

    def append_to_sample_name(self, key):
        """Apply one text-input key to the sample-name field."""

        self.sample_name = self.append_text_input(
            self.sample_name,
            key,
        )

    @staticmethod
    def append_text_input(current_value, key):
        """
        Append printable ASCII text or apply Backspace.

        The caller should pass the integer key value returned by curses.
        """

        if key in (127, 8):
            return current_value[:-1]

        if 32 <= key <= 126:
            return current_value + chr(key)

        return current_value

    def validate_sound_source(self):
        """Return whether the sound-source field contains text."""

        if not self.sound_source.strip():
            self.status_message = (
                "Warning: Enter a sound source to continue."
            )
            return False

        return True

    def validate_sample_name(self):
        """Return whether the sample-name field contains text."""

        if not self.sample_name.strip():
            self.status_message = (
                "Warning: Enter a sample name to continue."
            )
            return False

        return True

    def validate(self):
        """Return whether all currently required metadata is present."""

        if not self.validate_sound_source():
            return False

        if not self.validate_sample_name():
            return False

        return True

    def set_classification(self, name, value):
        """Store a future classification field by name."""

        self.additional_metadata[name] = value

    def get_classification(self, name, default=None):
        """Return a future classification value."""

        return self.additional_metadata.get(
            name,
            default,
        )

    def as_dict(self):
        """Return all current metadata as a dictionary."""

        return {
            "sound_source": self.sound_source.strip(),
            "sample_name": self.sample_name.strip(),
            "sample_type": self.sample_type.strip(),
            "spectral_classification": (
                self.spectral_classification.strip()
            ),
            **self.additional_metadata,
        }

    def clear_sample_fields(self):
        """
        Clear fields that belong to one exported sample.

        Keep the sound source because multiple clips may come from the same
        source recording.
        """

        self.sample_name = ""
        self.sample_type = ""
        self.spectral_classification = ""
        self.additional_metadata = {}

    def clear_all(self):
        """Clear all current metadata fields."""

        self.sound_source = ""
        self.clear_sample_fields()
        self.status_message = ""
