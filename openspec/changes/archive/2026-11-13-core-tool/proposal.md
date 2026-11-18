# Proposal

## Why

The Amiga projects are checked in Amiberry by a person at the keyboard, one check at a time, which
is slow and easy to skip. amiga-engine showed that Amiberry's remote-control socket can do most of
it (keys, screenshots, memory), but its driver scripts were written for one program, live outside
its repository, and were rewritten for every step. octamed4 is about to need the same for
`song-list-ab`'s eleven checks. One shared tool, written once and tested, serves every project.

## What Changes

- New Python package and command `amiberry-remote`, installed into each project's virtual
  environment (`pip install -e ~/source/amiga/amiberry-remote`), so a fix reaches every project.
- Session: start Amiberry with a project's config (or use the one already running), wait until
  Workbench is up, open a Shell, run a command in it, and quit.
- Input: press, hold and release Amiga keys by name, type text (shifted characters included), put
  the pointer on a given position of the front screen and click or drag there. The pointer is
  steered by reading its position from Intuition, so Workbench's pointer speed-up and the screen's
  resolution don't matter and no Amiberry setting has to change.
- Screen: take a screenshot as a picture of the Amiga screen (Amiga pixels, Amiberry's border and
  line doubling removed), compare an area of it with an expected picture, and wait until an area
  matches. A failed comparison saves the screenshot and a picture of the differences.
- Memory: read and write bytes, words, longs and blocks; find a library by name; find where a
  running program's hunks were loaded, so a project can address its own places as hunk + offset.
- Command line: the same operations by hand, e.g. `amiberry-remote shot out.png`,
  `amiberry-remote type "dir"`, `amiberry-remote click 330 48`, `amiberry-remote hunks OctaMED`.
- Not in this change: savestates, warp speed, breakpoints, sound, and moving amiga-engine's own
  scripts onto the tool (backlog).

## Capabilities

### New Capabilities
- `emulator-session`: connecting to or starting Amiberry, waiting for Workbench, Shell commands,
  quitting.
- `amiga-input`: keys, typing, and putting the pointer on a screen position to click or drag.
- `screen-capture`: screenshots in Amiga pixels, comparing and waiting for screen areas.
- `amiga-memory`: memory reads and writes, finding libraries and a running program's hunks.
- `command-line`: the `amiberry-remote` command.

### Modified Capabilities
- None (new project).

## Impact

- New project `~/source/amiga/amiberry-remote`: package `amiberry_remote`, `pyproject.toml`
  (depends on Pillow), unit tests against a fake Amiberry socket, a README.
- Uses Amiberry 8.4.2's socket at `$XDG_RUNTIME_DIR/amiberry.sock`. Commands used: `PING`,
  `SEND_KEY`, `SEND_MOUSE`, `SCREENSHOT`, `READ_MEM`, `WRITE_MEM`, `QUIT`.
- octamed4 becomes the first user, in a change of its own there; amiga-engine can follow later.
