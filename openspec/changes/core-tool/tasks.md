# Tasks

## 1. Facts and groundwork

- [ ] 1.1 With Amiberry running the OctaMED config (`~/Amiberry/Configurations/A1200-OctaMED.uae`), confirm through the socket and record in `NOTES.md`: every offset in design decision 3's table; whether the front screen's `MouseX`/`MouseY` follow `SEND_MOUSE` moves, and how many pixels one count moves on Workbench and on OctaMED's screen; how long one `READ_MEM` takes (100 in a row) and whether `MONITOR` can dump memory without stopping the CPU; the screenshot's size and where Workbench's and OctaMED's screens sit in it; whether `OctaMED.patched` started from a Shell is found through `cli_Module` or runs detached; how long Workbench takes to settle. If anything differs from the design, update `design.md` before going on. Verify: `NOTES.md` has each value as seen.
- [ ] 1.2 Create the package (`pyproject.toml` with Pillow, `amiberry_remote/`, `tests/`, a `README.md` with setup and a `.gitignore`), the link (design decision 2) and the fake Amiberry (design decision 9) with its memory image and command log. Verify: `pip install -e .` into a fresh `.venv` works, and unit tests show an `OK` reply returned, an error reply raised as `AmiberryError` naming the command, and a missing socket reported as "Amiberry is not running".

## 2. Memory

- [ ] 2.1 Implement memory reads and writes, block reads, the library lookup, the front screen and the active window (spec `amiga-memory`, design decision 3). Verify with unit tests against the fake: big-endian values; odd addresses refused with nothing sent; a 1,040-byte block read in order; `intuition.library` found with its version and an unknown name refused; the front screen's size and title. Add a "Memory" section to the README.
- [ ] 2.2 Implement the hunk lookup for Shell and detached programs. Verify with unit tests: a fake Shell process running `OctaMED.patched` with a 4-hunk seglist gives 4 addresses and lengths in order; the name matches whatever the case and path (`PC:OctaMED/OctaMED.patched`); not running and running in two Shells are errors saying so; a detached process is found through `pr_SegList`.

## 3. Keys

- [ ] 3.1 Implement key names, combinations and typing (spec `amiga-input`, design decision 6). Verify with unit tests: `Help` sends `$5F` down then up; `Ctrl-F2` presses in order and releases in reverse; `cd PC:OctaMED` sends Shift with exactly the shifted characters; an unknown key or a character that can't be typed is an error and nothing is sent. Add a "Keys" section to the README with the key names.

## 4. Pointer

- [ ] 4.1 Implement pointer steering, clicks and drags (design decision 7). Verify with unit tests against the fake's accelerating pointer, on a 640- and a 320-wide screen: the pointer ends exactly on the target from any start; a target off the screen is refused without moving; a pointer that can't get there is an error giving where it got to; a click is at the target; a drag passes through every position in between; buttons are released when a step fails. Add a "Mouse" section to the README, with the warning to keep the PC's mouse off Amiberry's window.

## 5. Screen

- [ ] 5.1 Implement the screenshot mapping and Amiga-pixel shots (spec `screen-capture`, design decision 8). Verify with unit tests: fake framebuffers at scales 1 x 1, 1 x 2 and 2 x 2 with different borders all give back the screen's own picture exactly; a framebuffer that fits no scale is an error naming the screen.
- [ ] 5.2 Implement comparing, waiting and pointer parking. Verify with unit tests: 0 for an equal area and no files saved; 3 for 3 changed pixels, with the first position and the two saved pictures; colours equal at 4 bits per gun by default and different at 8 bits when asked; a wrong-sized expected picture refused; a wait that succeeds when the fake screen changes partway and one that times out with its files. Add a "Screen" section to the README.

## 6. Session

- [ ] 6.1 Implement connect, start, the Workbench wait, Shell commands and quit (spec `emulator-session`, design decisions 4 and 5). Verify with unit tests: connecting uses a running fake without resetting it; the three places for the Amiberry program and the errors for a missing program or config; a fake Amiberry program that starts the fake server is started with the config and `-G`; the wait returns as soon as the fake reaches Workbench and times out with a screenshot otherwise; `run` makes the new Shell the active window before typing; quit waits until the socket is gone. Add a "Session" section to the README with the example from design decision 1.

## 7. Command line

- [ ] 7.1 Implement `amiberry-remote` and its sub-commands (spec `command-line`). Verify with unit tests: each sub-command against the fake; `$4`, `0x4` and `4` read the same address and output is `$` hex; a failure prints one line to standard error and exits non-zero. Add a "Command line" section to the README.

## 8. Live check

- [ ] 8.1 Write `tests/live_check.py`, run only when `AMIBERRY_LIVE_CONFIG` is set, and run it with the OctaMED config: start Amiberry and wait for Workbench; put the pointer on 5 positions of the Workbench screen and read each back; a screenshot in Amiga pixels has the Workbench screen's size; run `wait 60` in a Shell and find `Wait`'s hunks; quit. Then by hand with the command line: `run "cd PC:OctaMED" "OctaMED.patched"`; `hunks OctaMED.patched` gives one line per hunk with the lengths of the hunk file; `shot` of OctaMED's screen, rows 0-12, equals `OctaMED.gfx1`'s title strip in its own colours; `key Help` on an instrument with a break shows "15 slices". Record the times taken in `NOTES.md`.

## Workflow follow-up

- Archive once all tasks are done: `emulator-session`, `amiga-input`, `screen-capture`, `amiga-memory` and `command-line` become main specs.
- In octamed4, a change that uses the tool for `song-list-ab`'s Amiberry checks.
- Later (backlog): savestates for a quick start, warp speed, moving amiga-engine's scripts onto the tool.
