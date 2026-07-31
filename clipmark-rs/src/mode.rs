#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AppMode {
    Edit,
    Preview,
    Source,
    Name,
    Final,
}

impl AppMode {
    pub fn label(self) -> &'static str {
        match self {
            Self::Edit => "Edit mode",
            Self::Preview => "Preview mode",
            Self::Source => "Sound source entry",
            Self::Name => "Sample name entry",
            Self::Final => "Final export confirmation",
        }
    }
}
