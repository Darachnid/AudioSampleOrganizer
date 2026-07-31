use std::path::{Path, PathBuf};

use hound::WavReader;
use regex::Regex;

use crate::metadata::MetadataStore;

pub fn sanitize_filename(name: &str) -> String {
    let re_bad = Regex::new(r"[^\w\- ]+").unwrap();
    let re_space = Regex::new(r"\s+").unwrap();
    let cleaned = re_bad.replace_all(name.trim(), "");
    let cleaned = re_space.replace_all(&cleaned, "_");
    if cleaned.is_empty() {
        "sample".into()
    } else {
        cleaned.into_owned()
    }
}

pub fn build_output_stem(meta: &MetadataStore) -> String {
    format!(
        "{}-{}",
        sanitize_filename(&meta.sound_source),
        sanitize_filename(&meta.sample_name)
    )
}

fn unique_output_path(export_dir: &Path, stem: &str) -> PathBuf {
    let mut path = export_dir.join(format!("{stem}.wav"));
    let mut counter = 2;
    while path.exists() {
        path = export_dir.join(format!("{stem}_{counter}.wav"));
        counter += 1;
    }
    path
}

pub fn export_clip(
    audio_path: &Path,
    export_dir: &Path,
    start_secs: f64,
    end_secs: f64,
    meta: &MetadataStore,
) -> Result<PathBuf, String> {
    meta.validate_source()?;
    meta.validate_name()?;
    if end_secs <= start_secs {
        return Err("Clip start and end are not valid.".into());
    }

    std::fs::create_dir_all(export_dir).map_err(|e| e.to_string())?;

    let mut reader = WavReader::open(audio_path).map_err(|e| e.to_string())?;
    let spec = reader.spec();
    let rate = f64::from(spec.sample_rate);
    let start_frame = (start_secs * rate).round() as u32;
    let end_frame = (end_secs * rate).round() as u32;
    let channels = spec.channels as usize;

    reader.seek(start_frame).map_err(|e| e.to_string())?;

    let stem = build_output_stem(meta);
    let out_path = unique_output_path(export_dir, &stem);
    let mut writer = hound::WavWriter::create(&out_path, spec).map_err(|e| e.to_string())?;

    let frames = end_frame.saturating_sub(start_frame) as usize;
    let total_samples = frames * channels;

    match spec.sample_format {
        hound::SampleFormat::Float => {
            let mut samples = reader.samples::<f32>();
            for _ in 0..total_samples {
                let s = samples
                    .next()
                    .ok_or_else(|| "Unexpected end of source audio.".to_string())?
                    .map_err(|e| e.to_string())?;
                writer.write_sample(s).map_err(|e| e.to_string())?;
            }
        }
        hound::SampleFormat::Int => {
            let mut samples = reader.samples::<i32>();
            for _ in 0..total_samples {
                let s = samples
                    .next()
                    .ok_or_else(|| "Unexpected end of source audio.".to_string())?
                    .map_err(|e| e.to_string())?;
                writer.write_sample(s).map_err(|e| e.to_string())?;
            }
        }
    }

    writer.finalize().map_err(|e| e.to_string())?;
    meta.save_file_metadata()?;
    Ok(out_path)
}
