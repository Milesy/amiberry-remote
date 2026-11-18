# Tasks

## 1. Pause and Amiberry's own screenshot

- [x] 1.1 Add pause, resume and the paused block to the session, and `PAUSE`/`RESUME` to the fake Amiberry (spec `emulator-session`, design decisions 1 and 3). Verify with unit tests: pause then resume sends `PAUSE` then `RESUME`; a paused block resumes after a normal end and after a failure, and the failure is passed on; a refused `PAUSE` is an error naming it.
- [x] 1.2 Add Amiberry's own screenshot to the session (spec `screen-capture`, design decision 2). Verify with a unit test: the picture is the fake's whole 756 x 576 screenshot, saved at the path given, and it is also given when no path is named.
- [x] 1.3 Add `pause`, `resume` and `rawshot PATH` to the command (spec `command-line`). Verify with unit tests: `rawshot` saves the screenshot and prints `756 x 576`; `pause` and `resume` pause and resume the fake.

## 2. Drag (code from 59ef28a)

- [x] 2.1 Confirm the drag matches the modified `amiga-input` and `command-line` requirements: either button, several positions, a pause at each position between the first and last, and bad input refused with nothing sent. Verify: the unit tests `test_right_button_drag_holds_the_right_button` and `test_drag_through_several_positions` pass.

## 3. Documentation and the live check

- [x] 3.1 Document pausing and `raw_shot` in `README.md` (a Pausing section, the Screen section and the command list), pausing as measured on the engine machine in `NOTES.md`, and both in the Claude skill. Verify: each names the calls and commands as built.
- [x] 3.2 Add a live check: paused, exec's dispatch count (ExecBase + `$11C`) reads the same twice 0.3 s apart, and moves again after resuming; a raw shot taken while paused is at least as large as the front screen. Verify: the unit tests still pass without Amiberry (`.venv/bin/python -m unittest`, the live check skipped).
- [x] 3.3 Run the live check on a free Amiberry: `AMIBERRY_LIVE_CONFIG=~/Amiberry/Configurations/A1200-Engine.uae .venv/bin/python -m unittest tests.live_check -v`. Verify: all 4 checks pass; write the times in `NOTES.md`.

## Workflow follow-up

- Archive with spec sync.
- Commit and push only when the user asks: the code with this change, then the archive.
