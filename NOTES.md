# Notes: Amiberry as seen through its socket

Seen on 2026-11-12 with Amiberry 8.4.2 (`~/amiga/emu/Amiberry-8.4.2-x86_64.AppImage`), config
`~/Amiberry/Configurations/A1200-OctaMED.uae` (A1200, 68020, AGA, 2 MB chip, 8 MB fast,
Kickstart/Workbench 3.1 with ClassicWB), started with `--config <file> -G`.

## Structures (design decision 3)

All offsets in the table were confirmed on the running machine:

| What | Seen |
|---|---|
| ExecBase | long at 4 = `$200830`, version 40. During reset the long at 4 is `$F800D2` (the ROM's start address, ROM overlaid at 0), so "ExecBase is set" means `ChkBase` (`$26`) = `~ExecBase`. |
| Libraries | `LibList` at `$17A`; node next 0, name `$0A`, version `$14`. 21 libraries, e.g. `intuition.library` 40 at `$20B3F4`, `exec.library` 40 last. |
| Tasks | `ThisTask` `$114`, `TaskReady` `$196`, `TaskWait` `$1A4`, type `$08` (13 = process, 1 = task). A task list read over the socket isn't atomic: a task moving between lists during the walk showed up twice (`Shell Process` running `wait`, and `input.device`). Results must be de-duplicated by address and the walk capped. |
| Shell program | `pr_CLI` `$AC` (BPTR), `cli_CommandName` `$10` (BSTR) as typed (`wait`, `C:NewIcons`, `SYS:System/FPalette/FPPrefs`), `cli_Module` `$3C` (BPTR seglist). `wait 60` in a new Shell: process `Shell Process`, command `wait`, one hunk of 816 bytes. Programs started with `run` from the startup-sequence keep their `cli_Module` too (`Background CLI` processes). |
| Detached program | `pr_SegList` `$80` -> array; entry 0 is the count (2 or 3), entry 3 the program's seglist. |
| Hunks | Segment at `4 * bptr`, next BPTR at +0, contents from +4, long at -4 = contents length + 8. All 44 lengths of OctaMED's detached seglist equal the hunk file's sizes exactly (no rounding). |
| Front screen | IntuitionBase `FirstScreen` `$3C`, Screen fields at 8, 10, 12, 14, 16, 18, 22, 184 as in the table. Workbench: 640 x 256, depth 4, flags `$4611` (type `& $F` = 1, `WBENCHSCREEN`), **interleaved bitmap**: `BytesPerRow` 320 (4 x 80), planes 80 bytes apart. OctaMED: 640 x 256, depth 3, flags `$020F` (custom), `BytesPerRow` 80, title "OctaMED Professional © 1991-1992 Teijo Kinnunen & Ray Burt-Frost". Row r of plane p is at `Planes[p] + r * BytesPerRow` either way. |
| Active window | IntuitionBase `ActiveWindow` `$34`; Window `Title` 32, `WScreen` 46. ClassicWB's backdrop window (no title, 640 x 245 at y 11) is active after boot. |
| Intuition's mouse | IntuitionBase `MouseY` `$44` / `MouseX` `$46` count in interlaced lines (Y 260 when the screen's `MouseY` is 130); the screen's own `MouseX`/`MouseY` are in its pixels. |

## Pointer (design decision 7)

- The front screen's `MouseX`/`MouseY` follow `SEND_MOUSE` on both Workbench's and OctaMED's
  screen (both 640 x 256 hires, not interlaced).
- One count moves 1 pixel across and half a pixel down on both screens: sending 1 down moved 0
  or 1 (Intuition keeps half pixels), 2 moved 1, 16 moved 8. Moves of 1 to 32 counts were not
  sped up (Workbench's mouse acceleration is off on this config; `GET_MOUSE_SPEED` = 100).
- A move shows in the screen's position about 40 ms (two frames) after `SEND_MOUSE` answers.
- The pointer (a sprite) shows in screenshots, its hot spot at the screen position.

## Socket timing

- `READ_MEM` 4 bytes: 100 in a row took 11 ms (0.1 ms each); `PING` likewise. A 1,040-byte block
  at 4 bytes a command is about 30 ms, so `MONITOR` isn't needed for blocks.
- `MONITOR` has no memory dump: `m 4 1`, `m 4`, `x/4xb 4`, `mem 4 16`, `dump 4 16`, `help`
  all answer `ERROR unknown monitor command`; the binary's strings show only
  `capabilities`, `execution-status`, `input`, `guest-output`, `step-over`, `checkpoint`,
  `disasm`, `screenshot` and `memory-map`. The CPU kept running (exec's `DispCount` kept moving,
  `DEBUG_STATUS` stayed `stopped=0`).
- `QUIT` answers `OK`; the socket refuses connections 0.08 s later and its file is gone at 0.13 s.

## Screenshots (design decision 8)

- `SCREENSHOT <path>` writes a 756 x 576 RGB PNG and answers `OK<TAB><path>`.
- Workbench's screen and OctaMED's screen both sit at x 76, y 38 in it, at 1 x 2 (hires
  columns as they are, lines doubled): content x 76-715, y 38-549; the rest is black border.

## Programs from a Shell

- `OctaMED.patched` started from a Shell (`cd PC:OctaMED`, `OctaMED.patched`) **detaches**: the
  Shell's `cli_Module` is 0 and its command name empty once it is running, and the program runs
  as a separate process named **`OctaMED`** (not `OctaMED.patched`). That process's seglist
  (`pr_SegList` entry 3) has 44 segments, equal in length to hunks **1-44** of the 45-hunk file;
  hunk 0 (828 bytes, the start-up code that detaches) is not in it.
- OctaMED's screen was in front 0.13 s after Return.

## Execute Command and Shells

- Right Amiga+E with the backdrop window active: the "Execute a File" requester (400 x 67) is
  the active window at once. After `newshell` and Return, the backdrop window is active again for
  a moment, then the new `AmigaShell` window (640 x 130 at 0, 0) is, 0.25 s after Return.

## Workbench start-up (design decision 4)

From starting the AppImage (cold):

| Step | Time |
|---|---|
| socket answers `PING` | 0.5 s |
| ExecBase set | not timed separately: at 0.5 s the long at 4 was still the ROM's `$F800D2`; set by 1.5 s |
| `intuition.library` in the list | 1.5 s |
| `Workbench` process; front screen is `WBENCHSCREEN` | 7.1 s |
| two screenshots a second apart equal | 11.3 s (and unchanged after) |

## Calibration on a real screen (task 6.1)

- ClassicWB's `Copper` process puts a gradient on Workbench's colour 0: it shows as a different
  blue on every line ((85, 126, 187), (85, 126, 185), (85, 126, 183) on lines 1-3 of the title
  bar; (136, 140, 87) by line 192). So a colour number isn't one colour across the screen, but it
  is on each line: over the whole Workbench screen, every line but the 16 under the pointer had
  one colour per number. The calibration matches per line.
- The first band of 8 lines each with more than one colour starts at line 1 (the title bar's
  text); finding the Workbench screen took 0.19-0.28 s, a shot after that 0.03-0.04 s.

## Shells (task 6.1)

- A click on the Workbench screen's title bar doesn't change the active window, and a Shell window
  at 0, 0, 640 wide covers the title bar completely. Clicking an uncovered spot of the backdrop
  window (found from the layers in front of it) makes it active.
- Workbench's windows have `WFLG_WBENCHWINDOW` (`$02000000`) in their flags: the backdrop's flags
  were `$02201B40`; the Shell's `$2800304F` and the requester's `$00033046` don't have it. The
  backdrop's `UserPort` belongs to `ToolsDaemon`, not to `Workbench`.
- The Execute Command requester keeps the last command: typing `newshell` again gave
  `newshellnewshell`, "Unknown command", and an "Output Window" that took the keyboard. Right
  Amiga+X clears the string gadget first. `Esc` doesn't close the requester.

## Pointer speed (task 6.1)

- At most 8 counts a move, a position took 2.0-2.1 s (34 moves of about 60 ms: two frames to show
  the move, then a read to confirm it). At most 32 counts: 0.54-1.20 s, ending exact each time.

## Live check (task 8.1, 2026-11-13)

`AMIBERRY_LIVE_CONFIG=~/Amiberry/Configurations/A1200-OctaMED.uae .venv/bin/python -m unittest
tests.live_check -v`: all 3 checks pass, 18.1 s in all.

| Step | Time |
|---|---|
| start Amiberry and wait for Workbench | 11.43 s |
| pointer to x 0, y 0 (already there) / 639, 255 / 320, 128 / 13, 249 / 619, 17, each read back exact | 0.00 / 1.25 / 0.60 / 0.60 / 1.14 s |
| first shot, finding the screen (640 x 256, as the screen) / next shot | 0.19 / 0.03 s |
| `run` `wait 60` in a new Shell | 2.77 s |
| `hunks("wait")`: one hunk, 816 bytes | 0.03 s |
| quit | 0.09 s |

By hand with the command line:

| Command | Result | Time |
|---|---|---|
| `start ~/Amiberry/Configurations/A1200-OctaMED.uae` | Workbench is up | 11.54 s |
| `run "cd PC:OctaMED" "OctaMED.patched"` | OctaMED's screen in front, 640 x 256, depth 3 | 5.98 s |
| `hunks ~/amiga/local-octamed/OctaMED/OctaMED.patched` | 45 lines: hunk 0 not loaded (`$33C`), hunks 1-44 at their addresses with the file's lengths (hunk 34 in chip memory, `$27D60`) | 0.14 s |
| `shot` of OctaMED's screen, rows 0-12, against `OctaMED.gfx1` rows 0-12 in its palette (`000 CCC 667 99A 334 556 889 BBC`) | 95 pixels differ, all in x 0-22, y 0-11: the pointer, at 0, 0 over "TIMER" (`shot` doesn't move it). `compare((0, 0), strip)` parks the pointer first: 0 differ, at 4 and at 8 bits per gun | 1.36 s (compare, with parking) |
| `click`, `key RAmiga-X`, `type` in OctaMED's Files panel: directory `PC:songs`, file `test2.mod`, LOAD SONG | "Loaded.", instrument 01 "amen break.8svx" | |
| `key Help` | the title bar shows "15 slices" | 0.21 s |
| `quit` | Amiberry has quit | 0.18 s |

## Menus with MagicMenu (2026-11-18, OctaMED machine, SoundMon 2.2)

- No menu at all while the program's window isn't active. IntuitionBase `ActiveWindow` (+52) was 0
  after a Shell was used and the screens flipped back with Left-Amiga+M; a click on the program's
  screen below its window (SoundMon's window is 640 x 210) didn't activate it, a click inside did.
- MagicMenu pops the menu up at the pointer: the titles in a column, the open menu's items beside
  it. It opens with the last-used menu, and that menu's last-highlighted item, level with the pointer.
- Right button pressed, path through title and item (with 0.4 s pauses), released on the
  highlighted item: the menu stayed drawn for over a second, then closed with code `$FFFF`
  (MENUNULL), so nothing was picked.
- `click right` (held 50 ms) opened the menu and it stayed open (sticky); a left `click` on the item
  then picked it: the program received `$F820` (menu 0, item 1) at once.


## Pausing (2026-11-05 to 11-18, engine machine, amiga-engine steps 3.1-4.3)

Seen with `A1200-Engine.uae` while amiga-engine's game ran with its own copper list:

- `PAUSE` and `RESUME` both answer `OK`; `GET_STATUS` answers `OK`, `Paused=false`, `Config=...`.
- A key sent with `SEND_KEY` while paused is lost: the program never sees it.
- `FRAME_ADVANCE` answers "1 frame(s) advanced" while paused, but runs no frame: the program's
  frame counter (counted from the vertical blank) doesn't move.
- `SCREENSHOT` works while paused. It shows the frame drawn about 2 frames before the state in
  memory.
- Amiberry answers the socket at one point in each frame, so a `PAUSE` sent between frames can
  stop the program part-way through drawing one. Separate `READ_MEM`s while running aren't of
  one frame; read again after pausing.
- The game's display is lores, 320 wide: in the 756 x 576 screenshot its pixels are 2 x 2,
  its top-left at x 76, y 94 (that game's display window starts lower than Workbench's).

## Live check on the engine machine (2026-11-18)

`AMIBERRY_LIVE_CONFIG=~/Amiberry/Configurations/A1200-Engine.uae .venv/bin/python -m unittest
tests.live_check -v` (stock A1200, 2 MB chip, no fast RAM): all 4 checks pass, 19.5 s in all.

| Step | Time |
|---|---|
| start Amiberry and wait for Workbench | 12.20 s |
| pointer to x 0, y 0 / 639, 255 / 320, 128 / 13, 249 / 619, 17, each read back exact | 0.00 / 1.20 / 0.60 / 0.60 / 1.16 s |
| first shot (finding the screen) / next shot | 0.14 / 0.04 s |
| `run` `wait 60` in a new Shell / until its hunk (816 bytes, at `$89C40`) is found | 2.90 / 0.17 s |
| paused: exec's `DispCount` the same twice 0.3 s apart; raw shot while paused | 0.02 s (raw shot) |
| resumed: until `DispCount` moved | 0.07 s |
| quit | 0.09 s |
