# AsTeRICS Board Editor

A GTK4/Adwaita application for creating and editing AAC (Augmentative and Alternative Communication) communication boards.

## Features

- **Grid Editor** — Visual drag-and-drop cell arrangement
- **ARASAAC Pictograms** — Search and insert pictograms from [ARASAAC](https://arasaac.org)
- **Cell Properties** — Label, image, background color, and actions (speak text or navigate to board)
- **Board Properties** — Name, rows, columns
- **Multi-board Navigation** — Link boards together for hierarchical communication
- **Import/Export** — AsTeRICS Grid compatible `.grd` format
- **Preview Mode** — Test boards with text-to-speech playback
- **Welcome Screen** — Quick access to create, open, or import projects

## Requirements

- Python 3.10+
- GTK 4
- libadwaita 1.x
- PyGObject

## Installation

```bash
pip install .
```

## Usage

```bash
asterics-board-editor
```

Or run directly:

```bash
python -m asterics_board_editor
```

## File Formats

- **Native format** (`.json`) — Full project format with all board data
- **AsTeRICS Grid** (`.grd`) — Import/export compatibility with [AsTeRICS Grid](https://grid.asterics.eu)

## Pictograms

Pictograms are sourced from [ARASAAC](https://arasaac.org) (Aragonese Centre of Augmentative and Alternative Communication). Available resolutions: 300px, 500px, 2500px.

## License

GPL-3.0-or-later

## Credits

- Pictograms by [ARASAAC](https://arasaac.org) — Creative Commons BY-NC-SA
- Built with [GTK4](https://gtk.org) and [libadwaita](https://gnome.pages.gitlab.gnome.org/libadwaita/)
