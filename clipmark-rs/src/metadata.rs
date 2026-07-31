use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};

#[derive(Debug, Default, Serialize, Deserialize)]
struct FileMeta {
    sound_source: String,
}

pub struct MetadataStore {
    store_path: PathBuf,
    audio_path: String,
    pub sound_source: String,
    pub sample_name: String,
}

impl MetadataStore {
    pub fn new(store_path: impl Into<PathBuf>) -> Self {
        Self {
            store_path: store_path.into(),
            audio_path: String::new(),
            sound_source: String::new(),
            sample_name: String::new(),
        }
    }

    pub fn set_audio_path(&mut self, path: impl AsRef<Path>) {
        self.audio_path = path.as_ref().to_string_lossy().into_owned();
    }

    pub fn load_saved_source(&mut self) {
        if self.audio_path.is_empty() || !self.sound_source.trim().is_empty() {
            return;
        }
        let Ok(text) = fs::read_to_string(&self.store_path) else {
            return;
        };
        let Ok(map) = serde_json::from_str::<HashMap<String, FileMeta>>(&text) else {
            return;
        };
        if let Some(entry) = map.get(&self.audio_path) {
            self.sound_source = entry.sound_source.clone();
        }
    }

    pub fn save_file_metadata(&self) -> Result<(), String> {
        let mut map: HashMap<String, FileMeta> = fs::read_to_string(&self.store_path)
            .ok()
            .and_then(|t| serde_json::from_str(&t).ok())
            .unwrap_or_default();

        map.insert(
            self.audio_path.clone(),
            FileMeta {
                sound_source: self.sound_source.trim().to_string(),
            },
        );

        if let Some(parent) = self.store_path.parent() {
            fs::create_dir_all(parent).map_err(|e| e.to_string())?;
        }
        let text = serde_json::to_string_pretty(&map).map_err(|e| e.to_string())?;
        fs::write(&self.store_path, text).map_err(|e| e.to_string())
    }

    pub fn validate_source(&self) -> Result<(), String> {
        if self.sound_source.trim().is_empty() {
            Err("Sound source cannot be empty.".into())
        } else {
            Ok(())
        }
    }

    pub fn validate_name(&self) -> Result<(), String> {
        if self.sample_name.trim().is_empty() {
            Err("Sample name cannot be empty.".into())
        } else {
            Ok(())
        }
    }

    pub fn clear_sample_fields(&mut self) {
        self.sample_name.clear();
    }
}
