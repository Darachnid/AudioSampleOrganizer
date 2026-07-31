#pragma once

enum class AppMode {
    Edit,
    Preview,
    Source,
    Name,
    Final
};

inline const char *appModeLabel(AppMode mode)
{
    switch (mode) {
    case AppMode::Edit:
        return "Edit mode";
    case AppMode::Preview:
        return "Preview mode";
    case AppMode::Source:
        return "Sound source entry";
    case AppMode::Name:
        return "Sample name entry";
    case AppMode::Final:
        return "Final export confirmation";
    }
    return "ClipMark";
}
