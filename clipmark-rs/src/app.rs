use std::path::PathBuf;
use std::time::Instant;

use eframe::egui::{self, Key, Modifiers, RichText};
use egui::WidgetText;

use crate::audio::AudioEngine;
use crate::export::{build_output_stem, export_clip};
use crate::metadata::MetadataStore;
use crate::mode::AppMode;

pub struct ClipMarkApp {
    project_root: PathBuf,
    audio: AudioEngine,
    metadata: MetadataStore,
    mode: AppMode,
    status: String,
    start: Option<f64>,
    end: Option<f64>,
    status_view: Option<StatusKind>,
    left_held_since: Option<Instant>,
    right_held_since: Option<Instant>,
    export_dir: PathBuf,
}

#[derive(Clone, Copy)]
enum StatusKind {
    Brief,
    Detail,
}

impl ClipMarkApp {
    pub fn new(project_root: PathBuf) -> Self {
        let export_dir = project_root.join("ExportedSamples");
        let metadata = MetadataStore::new(project_root.join("sample_metadata.json"));
        Self {
            project_root,
            audio: AudioEngine::default(),
            metadata,
            mode: AppMode::Edit,
            status: "Open a WAV file to begin. Press E for status, Shift+E for detail.".into(),
            start: None,
            end: None,
            status_view: None,
            left_held_since: None,
            right_held_since: None,
            export_dir,
        }
    }

    fn format_time(seconds: f64) -> String {
        let seconds = seconds.max(0.0);
        let hours = (seconds as u64) / 3600;
        let minutes = ((seconds as u64) % 3600) / 60;
        let remain = seconds % 60.0;
        if hours > 0 {
            format!("{hours:02}:{minutes:02}:{remain:04.1}")
        } else {
            format!("{minutes:02}:{remain:04.1}")
        }
    }

    fn clip_valid(&self) -> bool {
        matches!((self.start, self.end), (Some(s), Some(e)) if e > s)
    }

    fn volume_step(current: usize) -> usize {
        if current <= 5 {
            1
        } else if current <= 10 {
            2
        } else if current <= 25 {
            5
        } else {
            10
        }
    }

    fn open_file(&mut self) {
        if let Some(path) = rfd::FileDialog::new()
            .add_filter("WAV", &["wav"])
            .set_directory(&self.project_root)
            .pick_file()
        {
            match self.audio.load(&path) {
                Ok(()) => {
                    self.metadata.set_audio_path(&path);
                    self.start = None;
                    self.end = None;
                    self.mode = AppMode::Edit;
                    self.status = format!("Loaded {}.", self.audio.file_name());
                }
                Err(e) => self.status = e,
            }
        }
    }

    fn ensure_loaded(&mut self) -> bool {
        if self.audio.is_loaded() {
            true
        } else {
            self.status = "Open a WAV file first.".into();
            false
        }
    }

    fn transport_label(&self) -> &'static str {
        if self.left_held_since.is_some() {
            "Seeking reverse"
        } else if self.right_held_since.is_some() {
            "Seeking forward"
        } else if self.mode == AppMode::Preview {
            if self.audio.is_playing() {
                "Previewing sample"
            } else {
                "Preview paused"
            }
        } else if self.audio.is_playing() {
            "Playing"
        } else {
            "Paused"
        }
    }

    fn controls_text(&self) -> &'static str {
        match self.mode {
            AppMode::Edit => {
                "Space play/pause. Left/Right seek. Up/Down volume. A start. D end. Enter preview. E status. Shift+E detail. Q quit."
            }
            AppMode::Preview => {
                "Enter continue. Right replay. Other key adjust. E status. Shift+E detail. Q quit."
            }
            AppMode::Source => {
                "Type source name. Enter continue. Esc/Left back. F1 status. F2 detail. Q quit."
            }
            AppMode::Name => {
                "Type sample name. Enter continue. Esc/Left back. F1 status. F2 detail. Q quit."
            }
            AppMode::Final => {
                "Enter export. Left back. Down cancel. E status. Shift+E detail. Q quit."
            }
        }
    }

    fn mode_help(&self) -> Vec<String> {
        match self.mode {
            AppMode::Edit => vec![
                "Space play or pause.".into(),
                "Left and Right seek or hold to shuttle.".into(),
                "Up and Down change playback volume.".into(),
                "A sets clip start. D sets clip end.".into(),
                "Enter previews the clip.".into(),
                "E shows status. Shift E shows detailed status and help.".into(),
                "Q quits.".into(),
            ],
            AppMode::Preview => vec![
                "Previewing the selected clip.".into(),
                "Enter continues to naming.".into(),
                "Right replays.".into(),
                "Any other key returns to editing.".into(),
                "E shows status. Shift E shows detailed help.".into(),
                "Q quits.".into(),
            ],
            AppMode::Source => vec![
                "Type the sound source name.".into(),
                "Enter continues. Left goes back.".into(),
                "F1 shows status. F2 shows detailed help.".into(),
                "Q quits.".into(),
            ],
            AppMode::Name => vec![
                "Type the sample name.".into(),
                "Enter continues. Left goes back.".into(),
                "F1 shows status. F2 shows detailed help.".into(),
                "Q quits.".into(),
            ],
            AppMode::Final => vec![
                "Final confirmation.".into(),
                "Enter exports the clip.".into(),
                "Left goes back. Down cancels.".into(),
                "E shows status. Shift E shows detailed help.".into(),
                "Q quits.".into(),
            ],
        }
    }

    fn brief_status_lines(&self) -> Vec<String> {
        vec![
            "ClipMark status".into(),
            format!("Mode: {}", self.mode.label()),
            format!("Transport: {}", self.transport_label()),
            format!(
                "Position: {} of {}",
                Self::format_time(self.audio.position_seconds()),
                Self::format_time(self.audio.duration_seconds())
            ),
            format!("Volume: {} percent", self.audio.volume_percent()),
            format!(
                "Start: {}",
                self.start
                    .map(Self::format_time)
                    .unwrap_or_else(|| "not selected".into())
            ),
            format!(
                "End: {}",
                self.end
                    .map(Self::format_time)
                    .unwrap_or_else(|| "not selected".into())
            ),
            format!("Message: {}", self.status),
            "Press Esc to return.".into(),
            "Press Shift E for detailed status and help.".into(),
        ]
    }

    fn detailed_status_lines(&self) -> Vec<String> {
        let mut lines = vec![
            "ClipMark detailed status".into(),
            format!("Mode: {}", self.mode.label()),
            format!("File: {}", self.audio.file_name()),
            format!("Transport: {}", self.transport_label()),
            format!(
                "Position: {}",
                Self::format_time(self.audio.position_seconds())
            ),
            format!("Volume: {} percent", self.audio.volume_percent()),
            format!(
                "Start: {}",
                self.start
                    .map(Self::format_time)
                    .unwrap_or_else(|| "not selected".into())
            ),
            format!(
                "End: {}",
                self.end
                    .map(Self::format_time)
                    .unwrap_or_else(|| "not selected".into())
            ),
        ];

        if let (Some(s), Some(e)) = (self.start, self.end) {
            if e > s {
                lines.push(format!("Length: {}", Self::format_time(e - s)));
            }
        }

        if matches!(
            self.mode,
            AppMode::Source | AppMode::Name | AppMode::Final
        ) {
            let source = if self.metadata.sound_source.is_empty() {
                "blank"
            } else {
                &self.metadata.sound_source
            };
            let name = if self.metadata.sample_name.is_empty() {
                "blank"
            } else {
                &self.metadata.sample_name
            };
            lines.push(format!("Source: {source}"));
            lines.push(format!("Name: {name}"));
            if self.mode == AppMode::Final {
                lines.push(format!(
                    "Export file: {}.wav",
                    build_output_stem(&self.metadata)
                ));
            }
        }

        lines.push("Help for this mode:".into());
        lines.extend(self.mode_help());
        lines.push("Press Esc to return.".into());
        lines.push("Press E for brief status.".into());
        lines
    }

    fn begin_preview(&mut self) -> bool {
        if !self.clip_valid() {
            self.status = "Set a start and end time before previewing.".into();
            return false;
        }
        let start = self.start.unwrap();
        let end = self.end.unwrap();
        self.audio.play_preview(start, end);
        self.status = "Previewing selected clip.".into();
        true
    }

    fn handle_keys(&mut self, ctx: &egui::Context) {
        let typing = matches!(self.mode, AppMode::Source | AppMode::Name);

        if ctx.input(|i| i.key_pressed(Key::F1)) {
            self.status_view = Some(StatusKind::Brief);
            return;
        }
        if ctx.input(|i| i.key_pressed(Key::F2)) {
            self.status_view = Some(StatusKind::Detail);
            return;
        }

        if !typing {
            if ctx.input(|i| i.key_pressed(Key::E) && i.modifiers.shift) {
                self.status_view = Some(StatusKind::Detail);
                return;
            }
            if ctx.input(|i| i.key_pressed(Key::E) && !i.modifiers.shift) {
                self.status_view = Some(StatusKind::Brief);
                return;
            }
        }

        if self.status_view.is_some() {
            if ctx.input(|i| i.key_pressed(Key::Escape)) {
                self.status_view = None;
                self.status = "Back to ClipMark. Press E for status, Shift E for detail.".into();
            } else if ctx.input(|i| {
                i.key_pressed(Key::E)
                    || i.key_pressed(Key::F1)
                    || i.key_pressed(Key::F2)
                    || i.key_pressed(Key::Q)
            }) {
                // handled above / quit below
            } else if ctx.input(|i| {
                i.keys_down.iter().any(|_| true) && i.events.iter().any(|e| matches!(e, egui::Event::Key { pressed: true, .. }))
            }) {
                // Close on most other key presses.
                let close = ctx.input(|i| {
                    i.events.iter().any(|e| {
                        matches!(
                            e,
                            egui::Event::Key {
                                pressed: true,
                                key,
                                ..
                            } if !matches!(key, Key::E | Key::F1 | Key::F2 | Key::Escape)
                        )
                    })
                });
                if close {
                    self.status_view = None;
                }
            }
            if ctx.input(|i| i.key_pressed(Key::Q)) {
                ctx.send_viewport_cmd(egui::ViewportCommand::Close);
            }
            return;
        }

        // Shuttle hold tracking
        let left_down = ctx.input(|i| i.key_down(Key::ArrowLeft));
        let right_down = ctx.input(|i| i.key_down(Key::ArrowRight));

        if self.mode == AppMode::Edit {
            if left_down && self.left_held_since.is_none() {
                self.left_held_since = Some(Instant::now());
            }
            if right_down && self.right_held_since.is_none() {
                self.right_held_since = Some(Instant::now());
            }
            if !left_down {
                if let Some(since) = self.left_held_since.take() {
                    if since.elapsed().as_millis() < 200 && self.ensure_loaded() {
                        self.audio.skip_seconds(-5.0);
                        self.status = "Jumped back 5 seconds.".into();
                    }
                }
            }
            if !right_down {
                if let Some(since) = self.right_held_since.take() {
                    if since.elapsed().as_millis() < 200 && self.ensure_loaded() {
                        self.audio.skip_seconds(5.0);
                        self.status = "Jumped forward 5 seconds.".into();
                    }
                }
            }
            if let Some(since) = self.left_held_since {
                if since.elapsed().as_millis() >= 200 && self.audio.is_loaded() {
                    let speed = shuttle_speed(since.elapsed().as_millis());
                    self.audio
                        .seek_seconds(self.audio.position_seconds() - 0.05 * speed);
                }
            }
            if let Some(since) = self.right_held_since {
                if since.elapsed().as_millis() >= 200 && self.audio.is_loaded() {
                    let speed = shuttle_speed(since.elapsed().as_millis());
                    self.audio
                        .seek_seconds(self.audio.position_seconds() + 0.05 * speed);
                }
            }
        }

        if ctx.input(|i| i.key_pressed(Key::Q)) {
            ctx.send_viewport_cmd(egui::ViewportCommand::Close);
            return;
        }

        match self.mode {
            AppMode::Edit => self.handle_edit_keys(ctx),
            AppMode::Preview => self.handle_preview_keys(ctx),
            AppMode::Source => self.handle_source_keys(ctx),
            AppMode::Name => self.handle_name_keys(ctx),
            AppMode::Final => self.handle_final_keys(ctx),
        }
    }

    fn handle_edit_keys(&mut self, ctx: &egui::Context) {
        if ctx.input(|i| i.key_pressed(Key::Space)) && self.ensure_loaded() {
            self.audio.toggle();
            self.status = if self.audio.is_playing() {
                "Playback started.".into()
            } else {
                "Playback paused.".into()
            };
        }
        if ctx.input(|i| i.key_pressed(Key::ArrowUp)) && self.ensure_loaded() {
            let cur = self.audio.volume_percent();
            let next = (cur + Self::volume_step(cur)).min(100);
            self.audio.set_volume_percent(next);
            self.status = format!("Volume set to {next}%.");
        }
        if ctx.input(|i| i.key_pressed(Key::ArrowDown)) && self.ensure_loaded() {
            let cur = self.audio.volume_percent();
            let step = Self::volume_step(cur);
            let next = cur.saturating_sub(step);
            self.audio.set_volume_percent(next);
            self.status = format!("Volume set to {next}%.");
        }
        if ctx.input(|i| i.key_pressed(Key::A)) && self.ensure_loaded() {
            self.start = Some(self.audio.position_seconds());
            self.status = format!("Start set to {:.1} seconds.", self.start.unwrap());
        }
        if ctx.input(|i| i.key_pressed(Key::D)) && self.ensure_loaded() {
            self.end = Some(self.audio.position_seconds());
            self.status = format!("End set to {:.1} seconds.", self.end.unwrap());
        }
        if ctx.input(|i| i.key_pressed(Key::Enter)) && self.ensure_loaded() && self.begin_preview() {
            self.mode = AppMode::Preview;
        }
    }

    fn handle_preview_keys(&mut self, ctx: &egui::Context) {
        if ctx.input(|i| i.key_pressed(Key::Enter)) {
            self.audio.pause();
            self.audio.clear_preview_end();
            self.metadata.load_saved_source();
            self.mode = AppMode::Source;
            self.status = "Enter sound source.".into();
            return;
        }
        if ctx.input(|i| i.key_pressed(Key::ArrowRight)) {
            let _ = self.begin_preview();
            self.status = "Preview replaying.".into();
            return;
        }
        // Any other key (except modifiers / status) returns to edit.
        let other = ctx.input(|i| {
            i.events.iter().any(|e| {
                matches!(
                    e,
                    egui::Event::Key {
                        pressed: true,
                        key,
                        ..
                    } if !matches!(
                        key,
                        Key::Enter
                            | Key::ArrowRight
                            | Key::E
                            | Key::F1
                            | Key::F2
                            | Key::Q
                            | Key::Escape
                    )
                )
            })
        });
        if other {
            self.audio.pause();
            self.audio.clear_preview_end();
            self.mode = AppMode::Edit;
            self.status = "Adjust start and end, then press Enter to preview.".into();
        }
    }

    fn handle_source_keys(&mut self, ctx: &egui::Context) {
        if ctx.input(|i| i.key_pressed(Key::Enter)) {
            match self.metadata.validate_source() {
                Ok(()) => {
                    self.metadata.sample_name.clear();
                    self.mode = AppMode::Name;
                    self.status = "Enter the sample name.".into();
                }
                Err(e) => self.status = e,
            }
        }
        if ctx.input(|i| i.key_pressed(Key::ArrowLeft) || i.key_pressed(Key::Escape)) {
            self.mode = AppMode::Preview;
            let _ = self.begin_preview();
        }
    }

    fn handle_name_keys(&mut self, ctx: &egui::Context) {
        if ctx.input(|i| i.key_pressed(Key::Enter)) {
            match self.metadata.validate_name() {
                Ok(()) => {
                    self.mode = AppMode::Final;
                    self.status = "Final confirmation. Enter exports.".into();
                }
                Err(e) => self.status = e,
            }
        }
        if ctx.input(|i| i.key_pressed(Key::ArrowLeft) || i.key_pressed(Key::Escape)) {
            self.mode = AppMode::Source;
        }
    }

    fn handle_final_keys(&mut self, ctx: &egui::Context) {
        if ctx.input(|i| i.key_pressed(Key::ArrowLeft)) {
            self.mode = AppMode::Name;
            return;
        }
        if ctx.input(|i| i.key_pressed(Key::ArrowDown)) {
            self.mode = AppMode::Edit;
            self.status = "Export cancelled. Markers and entries retained.".into();
            return;
        }
        if ctx.input(|i| i.key_pressed(Key::Enter)) {
            let Some(path) = self.audio.file_path() else {
                self.status = "No audio loaded.".into();
                return;
            };
            let (Some(start), Some(end)) = (self.start, self.end) else {
                self.status = "Clip start and end are not valid.".into();
                return;
            };
            match export_clip(&path, &self.export_dir, start, end, &self.metadata) {
                Ok(out) => {
                    let name = out
                        .file_name()
                        .map(|n| n.to_string_lossy().into_owned())
                        .unwrap_or_default();
                    self.start = None;
                    self.end = None;
                    self.metadata.clear_sample_fields();
                    self.audio.seek_seconds(end);
                    self.audio.play();
                    self.mode = AppMode::Edit;
                    self.status = format!("Exported: {name}. Continuing from {end:.1} seconds.");
                }
                Err(e) => self.status = e,
            }
        }
    }

    fn ui_status_overlay(&mut self, ctx: &egui::Context) {
        let Some(kind) = self.status_view else {
            return;
        };
        let lines = match kind {
            StatusKind::Brief => self.brief_status_lines(),
            StatusKind::Detail => self.detailed_status_lines(),
        };
        let title = match kind {
            StatusKind::Brief => "ClipMark Status",
            StatusKind::Detail => "ClipMark Detailed Status",
        };

        egui::Window::new(title)
            .collapsible(false)
            .resizable(true)
            .anchor(egui::Align2::CENTER_CENTER, [0.0, 0.0])
            .default_size([640.0, 480.0])
            .show(ctx, |ui| {
                ui.set_min_width(500.0);
                egui::ScrollArea::vertical().show(ui, |ui| {
                    for line in &lines {
                        ui.label(RichText::new(line).size(18.0));
                    }
                });
                ui.add_space(8.0);
                if ui
                    .button(WidgetText::from("Close status (Esc)"))
                    .on_hover_text("Return to ClipMark")
                    .clicked()
                {
                    self.status_view = None;
                }
            });
    }
}

fn shuttle_speed(held_ms: u128) -> f64 {
    if held_ms > 4000 {
        8.0
    } else if held_ms > 2000 {
        4.0
    } else if held_ms > 1000 {
        2.0
    } else {
        1.0
    }
}

impl eframe::App for ClipMarkApp {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        self.handle_keys(ctx);

        // Keep UI updating while audio plays / shuttle holds.
        if self.audio.is_playing()
            || self.left_held_since.is_some()
            || self.right_held_since.is_some()
        {
            ctx.request_repaint();
        }

        egui::CentralPanel::default().show(ctx, |ui| {
            ui.heading(RichText::new("ClipMark").size(28.0).strong());
            ui.label("Accessible WAV clip marker (Rust + egui / AccessKit)");
            ui.add_space(8.0);

            if ui
                .button(WidgetText::from("Open WAV…"))
                .on_hover_text("Choose a WAV file")
                .clicked()
            {
                self.open_file();
            }

            ui.add_space(8.0);
            ui.label(format!("Mode: {}", self.mode.label()));
            ui.label(format!("File: {}", self.audio.file_name()));
            ui.label(format!("Export to: {}", self.export_dir.display()));
            ui.label(format!("Transport: {}", self.transport_label()));
            ui.label(format!(
                "Position: {} / {}",
                Self::format_time(self.audio.position_seconds()),
                Self::format_time(self.audio.duration_seconds())
            ));
            ui.label(format!("Volume: {}%", self.audio.volume_percent()));
            ui.label(format!(
                "Start: {}",
                self.start
                    .map(Self::format_time)
                    .unwrap_or_else(|| "Not selected".into())
            ));
            ui.label(format!(
                "End: {}",
                self.end
                    .map(Self::format_time)
                    .unwrap_or_else(|| "Not selected".into())
            ));
            if let (Some(s), Some(e)) = (self.start, self.end) {
                if e > s {
                    ui.label(format!("Length: {}", Self::format_time(e - s)));
                }
            }

            ui.add_space(8.0);

            if self.mode == AppMode::Source || self.mode == AppMode::Final {
                ui.label("Sound source:");
                let response = ui.text_edit_singleline(&mut self.metadata.sound_source);
                if self.mode == AppMode::Source {
                    response.request_focus();
                }
            }
            if self.mode == AppMode::Name || self.mode == AppMode::Final {
                ui.label("Sample name:");
                let response = ui.text_edit_singleline(&mut self.metadata.sample_name);
                if self.mode == AppMode::Name {
                    response.request_focus();
                }
            }
            if self.mode == AppMode::Final {
                ui.label(format!(
                    "Export file: {}.wav",
                    build_output_stem(&self.metadata)
                ));
            }

            ui.add_space(8.0);
            ui.label(format!("Controls: {}", self.controls_text()));
            ui.separator();
            ui.label(RichText::new(format!("Message: {}", self.status)).strong());
        });

        self.ui_status_overlay(ctx);

        // Avoid unused import warning for Modifiers in some builds.
        let _ = Modifiers::default();
    }
}
