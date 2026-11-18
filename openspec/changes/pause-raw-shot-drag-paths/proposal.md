# Proposal

## Why

amiga-engine's checks are moving onto the tool (2026-11-18), and they need two things it lacks:
- **Pausing the emulation,** so several memory reads and a screenshot are all of one moment.
- **Amiberry's own screenshot.** The engine's game takes the display over with its own copper
  list, so the front Intuition screen that `shot` looks for isn't what is shown.

Without these, the engine's driver sent raw socket commands. A day earlier, the drag was widened
(right button, several positions, a pause at each) for menus, in commit `59ef28a`, without its
spec, so `amiga-input` no longer says what the tool does. This change brings both into the specs.

## What Changes

- **Pause and resume** the emulation, from Python and the command line, and a paused block that
  always resumes, even when the block fails.
- **Amiberry's own screenshot,** as it is (border and all), from Python and the command line
  (`rawshot PATH`), for a display that isn't an Intuition screen.
- **Drag** (already in the code since `59ef28a`, spec only):
  - with either button;
  - through any number of positions;
  - with an optional pause at each position between the first and the last;
  - on the command line as `drag X1 Y1 X2 Y2 [X Y ...] [left|right] [--pause SECONDS]`.
- **Not in this change:** single frame stepping (Amiberry's `FRAME_ADVANCE` runs no frame while
  paused, `NOTES.md`), and finding a game's picture inside the raw screenshot.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `emulator-session`: pausing and resuming the emulation.
- `screen-capture`: Amiberry's own screenshot.
- `amiga-input`: drags with either button, through several positions, with pauses.
- `command-line`: `pause`, `resume`, `rawshot`, and the wider `drag`.

## Impact

- **Code:**
  - `amiberry_remote/session.py`: `pause`, `resume`, `paused`, `raw_shot`.
  - `amiberry_remote/cli.py`: three sub-commands.
  - The fake Amiberry answers `PAUSE` and `RESUME`.
  - `tests/live_check.py`: a check that paused memory holds still.
- **Socket commands now used:** `PAUSE`, `RESUME`.
- **Docs:** `README.md` (Pausing, `raw_shot`), `NOTES.md` (pausing as measured on the engine
  machine), the Claude skill.
- **Users:** amiga-engine's `drive-4.3.py` drops its own socket calls. Nothing changes for octamed4.
