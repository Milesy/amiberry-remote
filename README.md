# amiberry-remote

Drives Amiberry (the Amiga emulator) through its remote-control socket, so an Amiga project can
check its program in the emulator without a person at the keyboard: keys and typing, the pointer
put on an exact screen position, screenshots in the Amiga's own pixels, and memory, including
where a running program's hunks were loaded.

It is a Python library (`amiberry_remote`) and a command (`amiberry-remote`), shared by the
Amiga projects in `~/source/amiga`. Each project keeps its own Amiberry config and its own checks;
the tool never changes a config file.

Made for Amiberry 8.4.2 on Linux and A1200s running Kickstart/Workbench 3.1. What it relies on
was checked on a running Amiberry and is written down in [NOTES.md](NOTES.md).

## Setup

In the project that uses it, with its virtual environment:

```sh
python3 -m venv .venv
.venv/bin/pip install -e ~/source/amiga/amiberry-remote
```

Installed this way (editable), a fix here reaches every project at once. Pillow comes with it.

The tool talks to the socket at `$XDG_RUNTIME_DIR/amiberry.sock`. A second Amiberry running at the
same time listens on another name; set `AMIBERRY_SOCKET` to the one to use.

## Session

```python
from amiberry_remote import Amiga
amiga = Amiga.start("~/Amiberry/Configurations/A1200-OctaMED.uae")   # or Amiga.connect()
amiga.run("cd PC:OctaMED", "OctaMED.patched")
amiga.key("Help"); amiga.click(330, 48)
amiga.wait_for((0, 0), "expected/title.png", timeout=20)
base = amiga.hunks("~/amiga/local-octamed/OctaMED/OctaMED.patched")[43].address
amiga.quit()
```

Checks are plain Python scripts in each project; the tool has no test runner of its own. Anything
that goes wrong raises `AmiberryError` with a message saying what.

- `Amiga.connect()` uses the Amiberry already running, as it is (it isn't reset). If none
  answers, it stops with an error saying Amiberry is not running.
- `Amiga.start(config, timeout=90)` starts Amiberry with the config and no settings window
  (`--config FILE -G`), or uses the one already running, and waits for Workbench. The config file
  isn't changed. The program is `$AMIBERRY` if set, else `amiberry` on the `PATH`, else
  `~/amiga/emu/Amiberry-8.4.2-x86_64.AppImage`.
- `amiga.wait_for_workbench(timeout=90)` returns once exec and Intuition are running, the
  `Workbench` process is there, Workbench's screen is in front and two screenshots a second apart
  are the same (about 11 s from starting on the OctaMED config). After the time limit it stops
  with an error saying what it was still waiting for and the path of a screenshot.
- `amiga.run(*commands)` opens a new Shell with Workbench's Execute Command (Right Amiga+E, Right
  Amiga+X to clear the command it remembers, `newshell`) and types each command into it with
  Return, checking first that the Shell window
  has the keyboard. If another window has it (say an old Shell), a Workbench window is clicked
  first, on a spot nothing covers. Workbench's screen must be in front. It returns once the keys
  are sent; wait for what the command should show with `wait_for` or by reading memory.
- `amiga.quit()` quits Amiberry and returns once it has gone.

## Keys

```python
amiga.key("Help")                  # down, then up
amiga.key("Ctrl-F2")               # Ctrl down, F2 down and up, Ctrl up
amiga.key("RAmiga-E", "Return")    # one after the other
amiga.key_down("LShift"); amiga.key_up("LShift")
amiga.type("cd PC:OctaMED\n")      # Shift held for P, C, :, O, M, E, D; \n is Return
```

Each key is held 50 ms with 50 ms after it, so typing runs at about ten characters a second. A
combination's keys go down in the order written and come up in reverse. Every name or character
is checked before any key is sent, so a mistake sends nothing; keys pressed by a call that fails
part-way are released.

Key names, matched without regard to case:

| Keys | Names |
|---|---|
| Letters, digits | `a`-`z`, `0`-`9` |
| Punctuation | `` ` `` `-` `=` `\` `[` `]` `;` `'` `,` `.` `/` |
| Function keys | `F1`-`F10`, `Help` |
| Editing | `Esc`, `Del`, `Backspace`, `Tab`, `Return`, `Enter` (keypad), `Space` |
| Cursor keys | `Up`, `Down`, `Left`, `Right` |
| Modifiers | `LShift`, `RShift` (`Shift` = `LShift`), `CapsLock`, `Ctrl`, `LAlt`, `RAlt` (`Alt` = `LAlt`), `LAmiga`, `RAmiga` |
| Keypad | `Num0`-`Num9`, `NumDot`, `NumMinus`, `NumPlus`, `NumStar`, `NumSlash`, `NumLParen`, `NumRParen` |

Typing uses the US keymap (Workbench's default): letters, digits, the punctuation on the keys
above with and without Shift, space, tab and line end. Other characters (`é`, `£`) are refused.

## Mouse

```python
amiga.pointer()                    # (x, y) on the front screen, in its own pixels
amiga.move_to(330, 48)
amiga.click(330, 48)               # left button; click(x, y, "right") for the right one
amiga.drag(100, 120, 160, 120)     # left button held from the first position to the second
amiga.drag(300, 100, 290, 89, 360, 70, button="right", pause=0.3)   # through several positions
```

Positions are the front screen's own pixels: x 0-639 on a hires screen, 0-319 on a lores one,
whatever Amiberry's window size. The pointer is steered: each `SEND_MOUSE` move (at most 32 counts)
aims at the distance left, and the position is read back from Intuition (the screen's
`MouseX`/`MouseY`) after every move, until it is exact. So Workbench's mouse speed-up and the
screen's resolution don't matter, and no Amiberry setting has to change. A move takes two frames
to show, so putting the pointer somewhere takes 0.5 to 1.2 seconds, and a drag about 60 ms per
pixel along it.

A position off the screen is refused before the pointer moves. A pointer that stops short is an
error giving where it got to. A click puts the pointer on the position first; a drag goes there,
presses the button (left unless `button="right"`), and moves a pixel at a time along the line, or
through each further position in turn, so the program sees every position in between. `pause`
seconds are spent at each position between the first and the last. Buttons are released whatever
happens.

**Menus.** The window must be the active one, or the right button shows no menu: a program
started from a Shell leaves the Shell active, so click inside the program's window first (inside
the window, not just the screen). ClassicWB, on both machines, runs MagicMenu, which changes how
menus behave (see `NOTES.md`, "Menus with MagicMenu"):

- The menu pops up at the pointer, not from the title bar. It opens with the menu and item last
  used under the pointer, so the layout depends on what was picked before. Take a `shot` with the
  menu open to see where things are.
- Pick with two clicks: `click(x, y, "right")` opens the menu and it stays open; then
  `click(item_x, item_y)` picks the item. Letting go of the right button at the end of a drag
  highlighted the item but sent no pick (MENUNULL).

**Keep the PC's mouse off Amiberry's window during a run.** Moving it over the window moves the
Amiga's pointer too; steering corrects for it, but a click or drag at the wrong moment lands in
the wrong place.

## Screen

```python
picture = amiga.shot("now.png")               # PIL image of the front screen, in Amiga pixels
result = amiga.compare((0, 0), "expected/title.png")          # area's size from the picture
result = amiga.compare((10, 20, 100, 40), "expected/box.png")
result.differing, result.first, result.shot_path, result.diff_path
amiga.wait_for((0, 0), "expected/title.png", timeout=20)
raw = amiga.raw_shot("raw.png")               # Amiberry's own screenshot, border and all
```

A shot is a picture of the front screen in its own pixels: one picture pixel per Amiga pixel, at
the screen's width and height, its pixel 0, 0 the screen's top-left one, in the colours Amiberry
shows. Amiberry's own screenshot (756 x 576 here, with a border, and hires screens' lines doubled)
is kept too when `raw_path` is given. Where the screen sits in Amiberry's screenshot is found the
first time a screen is shot, by matching a band of its bitmap (read from memory) against the
screenshot, line by line (the copper may change colours from line to line, as ClassicWB's
backdrop gradient does), and kept for that screen: the first shot of a screen takes about 0.2 s,
the next ones about 0.03 s. `shot` leaves the pointer where it is, so it shows in the picture.

`compare` takes an area as (left, top), its size that of the expected picture, or (left, top,
width, height), which must be the expected picture's size. It gives how many pixels differ and
where the first is (screen coordinates). Colours are compared at 4 bits per gun by default, the
precision of OCS/ECS colours, so `#F80` drawn on the PC as (240, 128, 0) equals Amiberry's
(255, 136, 0); `bits=8` compares exactly. When pixels differ, the shot and a difference picture
(the area dimmed, differing pixels in red) are saved in `amiberry-shots/` (or `$AMIBERRY_SHOTS`)
and their paths given.

`wait_for` takes shots until the area matches and returns as soon as it does; after `timeout`
seconds it stops with an error giving the paths of the last shot and its difference picture.
While it waits, a screen that isn't ready yet (still opening, or smaller than the area) just
means waiting on.

The pointer is a sprite and shows in screenshots, so `compare` and `wait_for` first move it out
of the area if it may cover it: to the bottom-right corner, or the first of the bottom-left,
top-right and top-left corners clear of the area. `park=False` leaves it where it is.

`raw_shot` is Amiberry's own screenshot (756 x 576 here) as it is, saved at a path if given. It is
for a display that isn't the front Intuition screen, such as a game that has taken the display
over with its own copper list: `shot` finds the screen from Intuition's bitmap, so it can't show
that. Where the game's picture sits in the raw screenshot is up to the caller.

## Pausing

```python
amiga.pause(); value = amiga.read(address, 2); amiga.raw_shot("now.png"); amiga.resume()
with amiga.paused():                     # resumed after the block, whatever happens
    value = amiga.read(address, 2)
```

Paused, the emulation stops: memory and the display hold still, so several reads and a
screenshot are all of one moment. Keys sent while paused are lost, and Amiberry's
`FRAME_ADVANCE` doesn't run a frame while paused (see `NOTES.md`): to catch a moment, poll memory
while running, then pause and read again to check it still holds.

## Memory

```python
amiga.read(4)                            # the long at 4: ExecBase
amiga.read(0x40000, 2)                   # a word; size 1 for a byte
amiga.write(0x40000, 2, 0x4E71)          # a byte, word or long
amiga.read_block(0x40000, 1040)          # bytes, in order
amiga.library("intuition.library")       # Library(name, address, version)
amiga.front_screen()                     # Screen(address, left, top, width, height, title, flags, bitmap)
amiga.active_window()                    # Window(address, title, screen, ...) or None
```

Values are big-endian, as the 68000 stores them, and unsigned when read. A word or long at an odd
address is refused before anything is sent. Each `READ_MEM` reads at most 4 bytes and takes about
0.1 ms, so a 1 KB block takes about 30 ms.

Libraries are found in exec's library list by their exact name; the front screen and the active
window come from Intuition (`IntuitionBase->FirstScreen`, `->ActiveWindow`).

### A running program's hunks

```python
hunks = amiga.hunks("~/amiga/local-octamed/OctaMED/OctaMED.patched")   # by its hunk file
address = hunks[43].address + 0x1C6                                     # hunk 43 + $1C6
amiga.hunks("wait")                                                     # by name
```

Each `Hunk` has its `number` in the hunk file, the `address` its contents were loaded at, and its
`length` in bytes.

- **By hunk file** (the argument is a file that exists on the PC): the tool reads the file's hunk
  sizes and finds the loaded program with those hunks. This finds a program that detaches from
  its Shell, as `OctaMED.patched` does: it runs as a process called `OctaMED`, without its first
  hunk (the start-up that detached it). Such hunks are given with `address` None; the others keep
  the file's numbers.
- **By name**: a program a Shell is running (its command, case ignored, with or without a path:
  `wait`, `PC:OctaMED/OctaMED.patched`), or a process of that name (`OctaMED`). Hunks are numbered
  from 0 in load order.

It stops with an error if no program matches, or if more than one does (the same program running
twice).

## Command line

The same operations by hand, on the running Amiberry (`.venv/bin/amiberry-remote`, or on the
`PATH` with the virtual environment active):

```sh
amiberry-remote start ~/Amiberry/Configurations/A1200-OctaMED.uae   # waits for Workbench
amiberry-remote run "cd PC:OctaMED" "OctaMED.patched"
amiberry-remote key Help                  # or several: key Ctrl-F2 Help
amiberry-remote type 'dir\n'              # \n is Return
amiberry-remote pointer                   # 330 48
amiberry-remote click 330 48              # click 330 48 right
amiberry-remote drag 100 120 160 120
amiberry-remote drag 300 100 290 89 360 70 right --pause 0.3   # a menu pick
amiberry-remote shot /tmp/now.png         # 640 x 256 (--raw PATH keeps Amiberry's own)
amiberry-remote rawshot /tmp/raw.png      # 756 x 576: Amiberry's own, for a game's display
amiberry-remote pause                     # and resume
amiberry-remote peek '$4' l               # $00200830 (b, w, l, or a count of bytes to dump)
amiberry-remote poke 0x40000 w 0x4E71
amiberry-remote library intuition.library # $0020B3F4 version 40
amiberry-remote hunks ~/amiga/local-octamed/OctaMED/OctaMED.patched
amiberry-remote screen                    # address, size, position, depth, title
amiberry-remote send GET_FPS              # a raw socket command; prints the reply
amiberry-remote quit
```

Addresses and values are accepted in decimal, `0x` hex or `$` hex (quote `$` from the shell), and
printed in `$` hex; positions are decimal. `hunks` prints one line per hunk: its number (decimal),
address and length, with `not loaded` for a hunk the program unloaded. A failure prints one line
saying what went wrong to standard error and exits with status 1 (2 for a mistake in the
command line).

## Claude skill

The `amiberry-remote` skill tells Claude sessions in any Amiga project how to use this tool: which
machine is which, checking what's running before starting Amiberry, the command line, and how to
write check scripts. It lives with the user's other skills in `~/source/skills`
(github.com/Milesy/skills), at `amiga/amiberry-remote/SKILL.md`; change it there when the tool
changes. That repo's `install.sh` links it into `~/.claude/skills`.

## Tests

The unit tests run against a fake Amiberry (`tests/fake_amiberry.py`), so Amiberry isn't needed:

```sh
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/python -m unittest
```

`tests/live_check.py` checks the tool against a real Amiberry: it starts Amiberry with the config
named, waits for Workbench, puts the pointer on five positions and reads them back, takes a shot,
runs `wait 60` in a Shell and finds its hunks, and quits (about 20 s). It is skipped unless the
config is given:

```sh
AMIBERRY_LIVE_CONFIG=~/Amiberry/Configurations/A1200-OctaMED.uae .venv/bin/python -m unittest tests.live_check -v
```
