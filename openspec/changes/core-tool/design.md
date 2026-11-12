# Design

## Context

See proposal.md for why. What exists:

- Amiberry 8.4.2 (`~/amiga/emu/Amiberry-8.4.2-x86_64.AppImage`) listens on a Unix socket,
  `$XDG_RUNTIME_DIR/amiberry.sock` (another instance gets a numbered name). One command per line,
  tab-separated; the reply is one line starting `OK` (values tab-separated, numbers in decimal) or
  an error. From the binary's own help: `SEND_KEY <code> <0|1>`, `SEND_MOUSE <dx> <dy> <buttons>`
  (relative), `SEND_MOUSE_ABS` (only with the tablet mouse driver), `SCREENSHOT <path>`,
  `READ_MEM <addr> <1|2|4>`, `WRITE_MEM <addr> <1|2|4> <value>`, `MONITOR <text>` (debugger
  command, lines returned as fields), `PING`, `QUIT`, and many settings commands.
- amiga-engine's scripts (`~/amiga/local-engine/drive-3.x.py`) used it from 2026-11-05: start with
  `--config <file> -G`, wait for `PING`, sleep 25 s for Workbench, Right Amiga+E then `newshell`
  for a Shell, keys 50 ms down and 50 ms apart, `READ_MEM` 4 bytes at a time. Lessons there: a
  click on Workbench takes the keyboard from the Shell; Amiberry's keyboard joystick can't be
  driven; its screenshots were 756 x 576 with the picture at 2x and an offset the script searched
  for.

## Goals / Non-Goals

**Goals:**
- Exact: pointer positions and screen comparisons in the Amiga's own pixels, not window pixels.
- Fast enough for a dozen checks in a minute or two, with no fixed sleeps where a state can be read.
- Everything testable without Amiberry, against a fake.

**Non-Goals:**
- Savestates, warp, the debugger, sound, recording video.
- RTG screens (no planar bitmap), Kickstart 1.x, Windows and macOS.
- Starting programs other than from a Shell (projects that boot their own disk use `start` and
  their own checks).

## Decisions

### 1. One package, one object

`amiberry_remote` with a few small modules (`link`: the socket; `keys`; `memory`; `screen`;
`pointer`; `session`; `cli`) and one object for callers:

```python
from amiberry_remote import Amiga
amiga = Amiga.start("~/Amiberry/Configurations/A1200-OctaMED.uae")   # or Amiga.connect()
amiga.run("cd PC:OctaMED", "OctaMED.patched")
amiga.key("Help"); amiga.click(330, 48)
amiga.wait_for((0, 0), "expected/title.png", timeout=20)
base = amiga.hunks("OctaMED.patched")[43].address
```

Checks are plain Python scripts in each project; the tool has no test runner of its own.
Errors are one exception type, `AmiberryError`, with a message a person can act on.

*Alternative:* copy amiga-engine's functions into a module. Rejected: they assume one config,
one screen layout and fixed sleeps.

### 2. The link: one connection per command

Each command opens the socket, sends one line, reads one line, closes, as amiga-engine did; it was
reliable there. The socket path is `AMIBERRY_SOCKET` if set, else `$XDG_RUNTIME_DIR/amiberry.sock`.
A reply not starting `OK` raises `AmiberryError` with the command and the reply.

Block reads use `READ_MEM` 4 bytes at a time. Task 1.1 measures how long a command takes; if a
1,040-byte read is slower than half a second, `MONITOR` with the debugger's memory dump is tried,
and used for blocks if it doesn't stop the emulated CPU.

### 3. Reading the Amiga: exec and Intuition structures

All "where is it" questions are answered from the OS's own structures, read with `READ_MEM`
(offsets from the 3.1 includes; task 1.1 confirms each on a running Workbench):

| What | How |
|---|---|
| Libraries | ExecBase = long at 4; `LibList` at `$17A`; each node: next 0, name pointer `$0A`, version `$14`. |
| Tasks | `ThisTask` `$114`, lists `TaskReady` `$196`, `TaskWait` `$1A4`; type `$08` (13 = process). |
| A Shell's program | process `pr_CLI` `$AC` (BPTR) -> `cli_CommandName` `$10` (BSTR), `cli_Module` `$3C` (BPTR seglist). |
| A detached program | process name = program name, `pr_SegList` `$80` -> array, seglist in entry 3. |
| Hunks | seglist BPTR chain: segment at `4 * bptr`, next BPTR at +0, contents from +4, size long at -4 (contents + 8). |
| Front screen | IntuitionBase `FirstScreen` `$3C`; Screen `LeftEdge` 8, `TopEdge` 10, `Width` 12, `Height` 14, `MouseY` 16, `MouseX` 18, `Title` 22, `BitMap` 184 (`BytesPerRow` 0, `Rows` 2, `Depth` 5, planes from 8). |
| Active window | IntuitionBase `ActiveWindow` `$34`; Window `Title` 32, `WScreen` 46. |

*Alternative for hunks:* the project searches memory for a marker in its own code. Rejected as the
general way: slow over `READ_MEM`, and every project would need a marker.

### 4. Waiting for Workbench

After `start`, poll (every half second): the socket answers; ExecBase is set; `intuition.library`
is in the list; a process called `Workbench` exists; the front screen is the Workbench screen
(screen flag `WBENCHSCREEN`); and then two screenshots one second apart are the same (disk
activity and icons have settled). Each step that fails just waits; the time limit covers the lot.

### 5. Shell commands

Right Amiga+E is Workbench's Execute Command; it needs a Workbench window active, so the pointer is
first put on an empty spot of the Workbench screen's title bar and clicked. Then `newshell` is
typed into the requester. The new window must become `ActiveWindow` (a different window from
before, on the Workbench screen); if not within 3 seconds, the tool clicks inside it. Then each
command is typed with Return. `run` returns once the keys are sent: the caller waits for the
screen or memory state it expects, as only it knows what that is.

### 6. Keys and typing

A table of names to Amiga key codes (Hardware Reference Manual's keyboard map), plus a US keymap
table for typing: character -> (code, shift). Each key goes down for 50 ms with 50 ms after it, as
in amiga-engine. Combinations are written `Ctrl-F2`, `LShift-RAmiga-E`. Names are matched without
regard to case.

### 7. Pointer steering

`SEND_MOUSE` moves are relative and Workbench's input preferences may accelerate them. So the
pointer is steered: read the front screen's `MouseX`/`MouseY`, send a move, read again, and learn
the ratio of pixels moved to counts sent on each axis from that move. Moves are at most 8 counts
per event (small enough not to be accelerated), the next move aims at the remaining distance, and
it stops when the position is exact, giving up after 200 moves. Buttons are bit 0 (left) and
bit 1 (right) of `SEND_MOUSE`'s third value, sent with a zero move; a drag sends its moves with
the left bit set, one pixel-step of the line at a time, then releases. A `try`/`finally` releases
the buttons whatever happens.

### 8. Screenshots in Amiga pixels

Amiberry's screenshot is the emulator's window: the display with its border, lores pixels
doubled, non-interlaced lines doubled. The mapping (scale per axis and offset) is found once per
front screen (keyed by its address, size and depth) and kept for the session:

1. Read a band of the screen's bitmap from memory (8 rows with more than one colour, found by
   reading rows from the top), giving each pixel's colour number.
2. Try horizontal scales 1, 2, 4 and vertical scales 1, 2, with offsets in a search window, and
   keep the one where the screenshot's colour is a function of the colour number across the band
   (same number, same colour; different numbers mostly different colours).
3. No exact fit is an error naming the screen.

Then a shot is cropped and scaled down to Amiga pixels. Comparisons reduce both sides to 4 bits
per gun by default (OCS/ECS colours, and what PC-made expected pictures use); 8 bits can be asked
for. The pointer is a sprite and shows in screenshots, so `compare` and `wait_for` first park the
pointer outside the area unless told not to (bottom-right of the screen, or the nearest corner
outside the area).

*Alternative:* render the screen from its bitplanes and palette. Rejected for every shot: a whole
screen is about 60 KB over `READ_MEM`, far too slow; it is used only for the small calibration band.

### 9. Tests against a fake Amiberry

`tests/fake_amiberry.py` serves the socket from a thread: a memory image (bytearray) where
`READ_MEM`/`WRITE_MEM` act, with ExecBase, a library list, tasks, a Shell process with a seglist,
IntuitionBase and a screen built in it; a pointer that `SEND_MOUSE` moves with an acceleration
curve; `SCREENSHOT` that writes a framebuffer with a border and doubling; and a log of every
command. Live tests run only when `AMIBERRY_LIVE_CONFIG` names a config.

## Risks / Trade-offs

- [The screen's `MouseX`/`MouseY` aren't updated for a screen that isn't active] -> task 1.1
  checks; if so, use IntuitionBase's `MouseX`/`MouseY` and the screen's position.
- [Commands are answered once per frame, so 1 KB reads take seconds] -> measured in task 1.1;
  blocks via `MONITOR` if it works; checks prefer few reads.
- [The real mouse over Amiberry's window moves the pointer] -> steering corrects as it goes; the
  README says to keep the PC mouse off the window during a run.
- [Keys go to the wrong window] -> the Shell is checked to be the active window before typing.
- [ClassicWB starts more than plain Workbench, or its screen title differs] -> the Workbench
  check uses the process and the screen flag, not a title.
- [Two Amiberrys running] -> `AMIBERRY_SOCKET` picks one; the error for a missing socket says so.

## Open Questions

- How long ClassicWB takes to settle on the OctaMED config; the default limit (90 s) may need to
  change.
