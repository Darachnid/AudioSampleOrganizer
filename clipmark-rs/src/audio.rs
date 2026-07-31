use std::path::{Path, PathBuf};
use std::sync::{
    atomic::{AtomicBool, AtomicU64, AtomicUsize, Ordering},
    Arc, Mutex,
};
use std::thread;
use std::time::Duration;

use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use cpal::{SampleFormat, StreamConfig};
use hound::{SampleFormat as HoundFormat, WavReader, WavSpec};

struct Shared {
    path: PathBuf,
    spec: WavSpec,
    total_frames: u64,
    position: AtomicU64,
    playing: AtomicBool,
    volume: AtomicUsize,
    preview_end: Mutex<Option<u64>>,
    stop_stream: AtomicBool,
}

#[derive(Clone)]
pub struct AudioEngine {
    shared: Option<Arc<Shared>>,
    _stream_keepalive: Arc<Mutex<Option<cpal::Stream>>>,
}

impl Default for AudioEngine {
    fn default() -> Self {
        Self {
            shared: None,
            _stream_keepalive: Arc::new(Mutex::new(None)),
        }
    }
}

impl AudioEngine {
    pub fn load(&mut self, path: impl AsRef<Path>) -> Result<(), String> {
        self.stop();

        let path = path.as_ref().to_path_buf();
        let reader = WavReader::open(&path).map_err(|e| format!("Open WAV failed: {e}"))?;
        let spec = reader.spec();
        let total_frames = u64::from(reader.duration());

        if spec.channels == 0 || spec.sample_rate == 0 {
            return Err("Invalid WAV header.".into());
        }

        let shared = Arc::new(Shared {
            path,
            spec,
            total_frames,
            position: AtomicU64::new(0),
            playing: AtomicBool::new(false),
            volume: AtomicUsize::new(100),
            preview_end: Mutex::new(None),
            stop_stream: AtomicBool::new(false),
        });

        let stream = start_stream(Arc::clone(&shared))?;
        *self._stream_keepalive.lock().unwrap() = Some(stream);
        self.shared = Some(shared);
        Ok(())
    }

    pub fn stop(&mut self) {
        if let Some(shared) = &self.shared {
            shared.playing.store(false, Ordering::SeqCst);
            shared.stop_stream.store(true, Ordering::SeqCst);
        }
        *self._stream_keepalive.lock().unwrap() = None;
        self.shared = None;
    }

    pub fn is_loaded(&self) -> bool {
        self.shared.is_some()
    }

    pub fn file_path(&self) -> Option<PathBuf> {
        self.shared.as_ref().map(|s| s.path.clone())
    }

    pub fn file_name(&self) -> String {
        self.shared
            .as_ref()
            .and_then(|s| {
                s.path
                    .file_name()
                    .map(|n| n.to_string_lossy().into_owned())
            })
            .unwrap_or_else(|| "(none)".into())
    }

    pub fn duration_seconds(&self) -> f64 {
        self.shared
            .as_ref()
            .map(|s| s.total_frames as f64 / f64::from(s.spec.sample_rate))
            .unwrap_or(0.0)
    }

    pub fn position_seconds(&self) -> f64 {
        self.shared
            .as_ref()
            .map(|s| {
                s.position.load(Ordering::Relaxed) as f64 / f64::from(s.spec.sample_rate)
            })
            .unwrap_or(0.0)
    }

    pub fn is_playing(&self) -> bool {
        self.shared
            .as_ref()
            .map(|s| s.playing.load(Ordering::Relaxed))
            .unwrap_or(false)
    }

    pub fn volume_percent(&self) -> usize {
        self.shared
            .as_ref()
            .map(|s| s.volume.load(Ordering::Relaxed))
            .unwrap_or(100)
    }

    pub fn set_volume_percent(&self, percent: usize) {
        if let Some(s) = &self.shared {
            s.volume.store(percent.clamp(0, 100), Ordering::Relaxed);
        }
    }

    pub fn play(&self) {
        if let Some(s) = &self.shared {
            *s.preview_end.lock().unwrap() = None;
            s.playing.store(true, Ordering::SeqCst);
        }
    }

    pub fn pause(&self) {
        if let Some(s) = &self.shared {
            s.playing.store(false, Ordering::SeqCst);
        }
    }

    pub fn toggle(&self) {
        if self.is_playing() {
            self.pause();
        } else {
            self.play();
        }
    }

    pub fn seek_seconds(&self, seconds: f64) {
        if let Some(s) = &self.shared {
            let frames = (seconds.max(0.0) * f64::from(s.spec.sample_rate)).round() as u64;
            s.position
                .store(frames.min(s.total_frames), Ordering::SeqCst);
        }
    }

    pub fn skip_seconds(&self, delta: f64) {
        self.seek_seconds(self.position_seconds() + delta);
    }

    pub fn play_preview(&self, start: f64, end: f64) {
        if let Some(s) = &self.shared {
            let start_f = (start.max(0.0) * f64::from(s.spec.sample_rate)).round() as u64;
            let end_f = (end.max(0.0) * f64::from(s.spec.sample_rate)).round() as u64;
            s.position
                .store(start_f.min(s.total_frames), Ordering::SeqCst);
            *s.preview_end.lock().unwrap() = Some(end_f.min(s.total_frames));
            s.playing.store(true, Ordering::SeqCst);
        }
    }

    pub fn clear_preview_end(&self) {
        if let Some(s) = &self.shared {
            *s.preview_end.lock().unwrap() = None;
        }
    }
}

fn start_stream(shared: Arc<Shared>) -> Result<cpal::Stream, String> {
    let host = cpal::default_host();
    let device = host
        .default_output_device()
        .ok_or_else(|| "No default output device.".to_string())?;
    let config = device
        .default_output_config()
        .map_err(|e| format!("Output config error: {e}"))?;

    let sample_format = config.sample_format();
    let stream_config: StreamConfig = config.into();
    let out_channels = stream_config.channels as usize;
    let out_rate = stream_config.sample_rate.0;

    let buffer: Arc<Mutex<Vec<f32>>> = Arc::new(Mutex::new(Vec::new()));
    let buffer_writer = Arc::clone(&buffer);
    let shared_reader = Arc::clone(&shared);

    thread::Builder::new()
        .name("clipmark-decode".into())
        .spawn(move || decode_loop(shared_reader, buffer_writer, out_rate, out_channels))
        .map_err(|e| format!("Decode thread failed: {e}"))?;

    let err_fn = |e| eprintln!("Audio stream error: {e}");
    let buffer_cb = Arc::clone(&buffer);

    let stream = match sample_format {
        SampleFormat::F32 => device
            .build_output_stream(
                &stream_config,
                move |data: &mut [f32], _| fill_output_f32(data, &buffer_cb),
                err_fn,
                None,
            )
            .map_err(|e| e.to_string())?,
        SampleFormat::I16 => device
            .build_output_stream(
                &stream_config,
                move |data: &mut [i16], _| fill_output_i16(data, &buffer_cb),
                err_fn,
                None,
            )
            .map_err(|e| e.to_string())?,
        SampleFormat::U16 => device
            .build_output_stream(
                &stream_config,
                move |data: &mut [u16], _| fill_output_u16(data, &buffer_cb),
                err_fn,
                None,
            )
            .map_err(|e| e.to_string())?,
        other => return Err(format!("Unsupported sample format: {other:?}")),
    };

    stream.play().map_err(|e| e.to_string())?;
    thread::sleep(Duration::from_millis(20));
    Ok(stream)
}

fn fill_output_f32(data: &mut [f32], buffer: &Mutex<Vec<f32>>) {
    let mut guard = buffer.lock().unwrap();
    let n = data.len().min(guard.len());
    data[..n].copy_from_slice(&guard[..n]);
    guard.drain(..n);
    for sample in &mut data[n..] {
        *sample = 0.0;
    }
}

fn fill_output_i16(data: &mut [i16], buffer: &Mutex<Vec<f32>>) {
    let mut guard = buffer.lock().unwrap();
    let n = data.len().min(guard.len());
    for (i, sample) in data.iter_mut().enumerate().take(n) {
        *sample = (guard[i].clamp(-1.0, 1.0) * f32::from(i16::MAX)) as i16;
    }
    guard.drain(..n);
    for sample in &mut data[n..] {
        *sample = 0;
    }
}

fn fill_output_u16(data: &mut [u16], buffer: &Mutex<Vec<f32>>) {
    let mut guard = buffer.lock().unwrap();
    let n = data.len().min(guard.len());
    for (i, sample) in data.iter_mut().enumerate().take(n) {
        let x = (guard[i].clamp(-1.0, 1.0) * 0.5 + 0.5) * f32::from(u16::MAX);
        *sample = x as u16;
    }
    guard.drain(..n);
    for sample in &mut data[n..] {
        *sample = u16::MAX / 2;
    }
}

fn read_block_f32(reader: &mut WavReader<std::io::BufReader<std::fs::File>>, frames: usize) -> Vec<f32> {
    let channels = reader.spec().channels as usize;
    let is_float = reader.spec().sample_format == HoundFormat::Float;
    let bits = reader.spec().bits_per_sample;
    let mut block = Vec::with_capacity(frames * channels);

    if is_float {
        let mut samples = reader.samples::<f32>();
        for _ in 0..frames * channels {
            match samples.next() {
                Some(Ok(s)) => block.push(s),
                _ => break,
            }
        }
    } else {
        let max_amp = (1i64 << (bits.saturating_sub(1))) as f32;
        let mut samples = reader.samples::<i32>();
        for _ in 0..frames * channels {
            match samples.next() {
                Some(Ok(s)) => block.push(s as f32 / max_amp),
                _ => break,
            }
        }
    }
    block
}

fn decode_loop(
    shared: Arc<Shared>,
    buffer: Arc<Mutex<Vec<f32>>>,
    out_rate: u32,
    out_channels: usize,
) {
    let Ok(mut reader) = WavReader::open(&shared.path) else {
        return;
    };

    let in_rate = shared.spec.sample_rate;
    let in_channels = shared.spec.channels as usize;
    let mut last_seek = u64::MAX;

    while !shared.stop_stream.load(Ordering::Relaxed) {
        let target = (out_rate as usize * out_channels) / 10;
        {
            let guard = buffer.lock().unwrap();
            if guard.len() >= target {
                drop(guard);
                thread::sleep(Duration::from_millis(5));
                continue;
            }
        }

        if !shared.playing.load(Ordering::Relaxed) {
            thread::sleep(Duration::from_millis(10));
            continue;
        }

        let pos = shared.position.load(Ordering::Relaxed);
        if let Some(end) = *shared.preview_end.lock().unwrap() {
            if pos >= end {
                shared.playing.store(false, Ordering::SeqCst);
                continue;
            }
        }
        if pos >= shared.total_frames {
            shared.playing.store(false, Ordering::SeqCst);
            continue;
        }

        if pos != last_seek {
            if reader.seek(pos as u32).is_err() {
                thread::sleep(Duration::from_millis(5));
                continue;
            }
            last_seek = pos;
        }

        let want_frames = 1024usize;
        let block = read_block_f32(&mut reader, want_frames);
        let frames_got = block.len() / in_channels.max(1);
        if frames_got == 0 {
            shared.playing.store(false, Ordering::SeqCst);
            continue;
        }

        let vol = shared.volume.load(Ordering::Relaxed) as f32 / 100.0;
        let ratio = f64::from(out_rate) / f64::from(in_rate);
        let out_frames = ((frames_got as f64) * ratio).round().max(1.0) as usize;
        let mut out = Vec::with_capacity(out_frames * out_channels);

        for of in 0..out_frames {
            let src_f = of as f64 / ratio;
            let i0 = (src_f.floor() as usize).min(frames_got - 1);
            let i1 = (i0 + 1).min(frames_got - 1);
            let t = (src_f - i0 as f64) as f32;

            for ch in 0..out_channels {
                let in_ch = ch.min(in_channels.saturating_sub(1));
                let a = block[i0 * in_channels + in_ch];
                let b = block[i1 * in_channels + in_ch];
                out.push((a + (b - a) * t) * vol);
            }
        }

        buffer.lock().unwrap().extend_from_slice(&out);

        let new_pos = pos + frames_got as u64;
        shared.position.store(new_pos, Ordering::Relaxed);
        last_seek = new_pos;
    }
}
