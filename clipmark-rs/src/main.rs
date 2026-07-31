mod app;
mod audio;
mod export;
mod metadata;
mod mode;

use std::env;
use std::path::PathBuf;

use eframe::egui;

use crate::app::ClipMarkApp;

fn project_root() -> PathBuf {
    if let Ok(manifest) = env::var("CARGO_MANIFEST_DIR") {
        let crate_dir = PathBuf::from(manifest);
        if let Some(parent) = crate_dir.parent() {
            if parent.join("CMakeLists.txt").exists() || parent.join("README.md").exists() {
                return parent.to_path_buf();
            }
        }
        return crate_dir;
    }

    env::current_dir().unwrap_or_else(|_| PathBuf::from("."))
}

fn main() -> eframe::Result<()> {
    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_inner_size([900.0, 640.0])
            .with_title("ClipMark"),
        ..Default::default()
    };

    eframe::run_native(
        "ClipMark",
        options,
        Box::new(|_cc| Ok(Box::new(ClipMarkApp::new(project_root())))),
    )
}
