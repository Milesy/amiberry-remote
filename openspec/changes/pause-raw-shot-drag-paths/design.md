# Design

## Context

See proposal.md for why. What exists:
- Amiberry answers `PAUSE` and `RESUME` with `OK` (`NOTES.md`, "Pausing").
- `Screenshots.raw` already takes Amiberry's own screenshot, inside `shot`. It isn't offered on
  its own.
- The drag (`59ef28a`) is already built and unit-tested. Only its spec is behind.

## Goals / Non-Goals

**Goals:**
- A caller can read a consistent moment without sending socket lines itself.
- A game's own display can be captured.

**Non-Goals:**
- Frame stepping. `FRAME_ADVANCE` doesn't run a frame while paused.
- Locating a game's picture in the raw screenshot. Its place depends on the program's display
  window, which only the project knows.
- Tracking whether Amiberry is paused across sessions.

## Decisions

### 1. Pause as two calls plus a block

`pause()` and `resume()` are plain calls, because a check may pause, test a condition and resume
early. `with amiga.paused():` covers the usual case and always resumes.

Alternative considered: only the block. Rejected, because amiga-engine's polling loops resume on a
condition part-way through.

### 2. A separate raw screenshot, not a smarter `shot`

`raw_shot` gives Amiberry's screenshot untouched. `shot` stays "the front Intuition screen in its
own pixels".

Alternative considered: teach `shot` to fall back to the whole display when the front screen
isn't shown. Rejected:
- The tool can't tell a game's display from a screen it failed to find.
- A silent fallback would hide real failures.
- Cropping a custom display needs the program's own knowledge.

### 3. No paused state kept by the tool

The tool sends `PAUSE`/`RESUME` and keeps no flag. Another process could pause or resume
Amiberry too, and `GET_STATUS` already reports `Paused=`.

## Risks / Trade-offs

- **A check that dies between `pause` and `resume` leaves Amiberry paused.** Mitigation: the
  `paused` block. By hand, `amiberry-remote resume`.
- **Keys sent while paused are lost.** Mitigation: documented in `README.md` and the skill.
- **`raw_shot`'s size and border depend on Amiberry's window settings** (756 x 576 here).
  Mitigation: documented as Amiberry's screenshot as it is. Callers crop it themselves.
