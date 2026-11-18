---
name: amiberry-remote
description: How to drive Amiberry, the user's emulated A1200s, with the amiberry-remote tool (~/source/amiga/amiberry-remote). It covers starting a machine, running a program in a Shell, keys, clicks and drags, screenshots in Amiga pixels and comparing them, reading and writing memory, finding a running program's hunks, and writing check scripts. Use it whenever a session in an Amiga project (octamed4, amiga-engine, dizzy or anything under ~/source/amiga) needs to run, test, check, look at or install something on an emulated Amiga. Also use it when the user mentions Amiberry, "the Amiga", "my OctaMED machine", "the engine machine", a .uae config, an Amiberry check or an emulator screenshot, even if they don't name the tool. Use it instead of talking to Amiberry's socket directly or reusing the old amiga-engine driver scripts.
---

# Driving Amiberry with amiberry-remote

The user checks their Amiga work in Amiberry 8.4.2. It emulates A1200s running Kickstart and
Workbench 3.1. `amiberry-remote` is how sessions drive it. It is a Python library and a command
in its own git repo, `~/source/amiga/amiberry-remote`. It already handles the awkward parts:
- steering the pointer to an exact pixel
- finding the Amiga screen inside Amiberry's bordered screenshot
- waiting for Workbench to settle
- opening a Shell that really has the keyboard
- finding where a program that detached from its Shell was loaded

Its `README.md` is the full reference: read it when you need more than this page. Its `NOTES.md`
records what was measured on the real emulator.

Use the tool rather than writing socket code of your own. Don't reuse
`~/amiga/local-engine/amiberry_ipc.py` or `drive-*.py` either: those are what the tool replaced.
If the tool lacks something, `amiberry-remote send LINE` passes one raw socket command through.
Needing that more than once means the tool is missing a feature (see the last section).

## The machines

Configs live in `~/Amiberry/Configurations/`. Each one mounts a PC folder as an Amiga volume, and
that is how files reach the Amiga: copy them into the folder. A Workbench window that is already
open may need closing and reopening to show new files. The config files are the truth: their
`filesystem2=` and `uaehf` lines name the volumes. On 2026-11-18 they were:

| Config | Machine | Volumes |
|---|---|---|
| `A1200-OctaMED.uae` | "my OctaMED machine": A1200, 68020, 2 MB chip + 8 MB fast, ClassicWB, OctaMED | `PC:` = `~/amiga/local-octamed`, `DH1:` = `~/amiga/drives/octamed-work.hdf` |
| `A1200-Engine.uae` | stock A1200, 2 MB chip, no fast RAM, for amiga-engine | `PC:` = `~/amiga/local-engine`, `Engine:` = `~/source/amiga/amiga-engine/build`, `DH1:` = `~/amiga/drives/engine-work.hdf` |

Both boot from the same `~/amiga/emu/hd/System.hdf`, read-write. Workbench only shows files that
have an icon (`.info`). If the user will start a program from Workbench, give it one. Copying a
generic tool icon is fine, for example `~/amiga/local-octamed/OctaMED_Soundstudio_c1.1/Icons/Executable.info`.

## One Amiberry at a time

Only one Amiberry should run at a time, for two reasons:
- The machines share `System.hdf` read-write.
- The tool talks to whichever Amiberry answers on `$XDG_RUNTIME_DIR/amiberry.sock`.

`Amiga.start(config)` and `amiberry-remote start` **reuse an Amiberry that is already running,
whatever its config**. So look first:

```sh
pgrep -af Amiberry          # its --config shows which machine is up
```

- **Nothing is running:** start the config you need.
- **The config you need is running:** use it as it is (`Amiga.connect()`, or any command-line
  command). It may be the user's live session, so don't reset it.
- **Another config is running:** it belongs to the user or to another session. Don't quit it.
  Tell the user which machine you need and why, and go on with whatever doesn't need the
  emulator. Restart it only if the user says so. "Run it yourself" counts as a yes.

If you started Amiberry for a check, you can quit it when you're done. If the user had it running,
leave it running.

## Command line: looking and trying things by hand

Any session can use the tool's own copy, `~/source/amiga/amiberry-remote/.venv/bin/amiberry-remote`.
A project that installed the tool has `.venv/bin/amiberry-remote` too.

```sh
R=~/source/amiga/amiberry-remote/.venv/bin/amiberry-remote
$R start ~/Amiberry/Configurations/A1200-OctaMED.uae   # about 11 s to a settled Workbench
$R run "cd PC:OctaMED" "OctaMED.patched"               # new Shell, one command per argument
$R screen                     # what's in front: address, size, depth, title
$R shot <scratchpad>/now.png   # the front screen in Amiga pixels (640 x 256 for hires)
$R key Help                   # or several in turn: key RAmiga-E Return
$R type 'dir\n'               # US keymap; \n is Return
$R click 330 48               # click 330 48 right
$R drag 100 120 160 120
$R pointer
$R peek '$4' l                # b, w, l, or a count of bytes to dump
$R poke 0x40000 w 0x4E71
$R library intuition.library
$R hunks ~/amiga/local-octamed/OctaMED/OctaMED.patched
$R rawshot <scratchpad>/raw.png   # Amiberry's own screenshot: for a game's own display
$R pause                      # and resume: memory and display hold still
$R send GET_FPS               # one raw socket line
$R quit
```

To see the Amiga, take a `shot` into the scratchpad and open the PNG with the Read tool.
Positions are the front screen's own pixels: x 0-639 on a hires screen, 0-319 on a lores one.

## Python: check scripts

A check the user will keep is a plain Python script in the project (octamed4 keeps them in
`checks/*.py`), not a one-off sequence of shell commands. Install the tool in the project's
virtual environment once. Add `-e ${HOME}/source/amiga/amiberry-remote` to its requirements, then
run `.venv/bin/pip install -e ~/source/amiga/amiberry-remote`. It is installed editable, so a fix
to the tool reaches every project.

```python
from amiberry_remote import Amiga, AmiberryError
amiga = Amiga.start("~/Amiberry/Configurations/A1200-OctaMED.uae")   # or Amiga.connect()
amiga.run("cd PC:OctaMED", "OctaMED.patched")
amiga.key("Help"); amiga.click(330, 48)
amiga.wait_for((0, 0), "expected/title.png", timeout=20)
base = amiga.hunks("~/amiga/local-octamed/OctaMED/OctaMED.patched")[43].address
value = amiga.read(base + 0x1C6, 2)
```

These patterns worked in octamed4. Its `checks/octamed.py` is the example to copy from.
- **One helper module per project** wraps the tool for that program. It checks that the right
  config is running (the `pgrep` above) and starts the program if it isn't running. It also
  holds the program's screen positions and memory offsets. Check scripts import the helper.
- **Wait on state, not on time.** Poll memory or the front screen's title, or `wait_for` an
  expected picture. Use a timeout whose error names what it was waiting for. Fixed sleeps make
  checks flaky.
- **A new Shell can lose its first key.** octamed4's helper calls `open_shell()`, waits a second,
  then calls `type`. Do the same if a command typed by `run` arrives without its first letter.
- **Find a running program's code and data** with `amiga.hunks(<its hunk file on the PC>)`. This
  works for programs that detach from their Shell too. Their start-up hunk shows `address` None.
- **Compare screens with `compare` or `wait_for`.** They compare at 4 bits per gun and move the
  pointer out of the way first. When pixels differ, the shot and a difference picture (differing
  pixels in red) are saved under `amiberry-shots/`, or `$AMIBERRY_SHOTS` if set. Open them to
  see what went wrong.
- **Let errors through.** Failures raise `AmiberryError` with a message saying what went wrong.
- **Report as you go.** Each check prints what it checked and whether it passed, and the script
  ends with a count.

Prefer adding a check script over asking the user to try something by hand. Ask the user only
for what the emulator can't show, such as how something sounds or how it behaves on the real
A1200.

## Things that catch people out

- Ask the user to keep their mouse off Amiberry's window while a check runs. Moving it there
  moves the Amiga's pointer too.
- `run` and `open_shell` need Workbench's screen in front. If a program's own screen is up, quit
  the program first.
- `type` only knows the US keymap. It refuses characters like `é` or `£`.
- Pointer moves take 0.5-1.2 s and a drag about 60 ms per pixel. Allow for that in timeouts.
- A game that takes the display over (amiga-engine's) isn't an Intuition screen: `shot` and
  `compare` can't see it. Use `raw_shot` and crop it yourself.
- To read several values of one moment, read them inside `with amiga.paused():`. Keys sent while
  paused are lost.

## When the tool falls short

Fix the tool in `~/source/amiga/amiberry-remote` rather than working around it in a project.
- Its unit tests run against a fake Amiberry: `.venv/bin/python -m unittest`.
- Its live check needs the emulator free:
  `AMIBERRY_LIVE_CONFIG=~/Amiberry/Configurations/A1200-OctaMED.uae .venv/bin/python -m unittest tests.live_check -v`.
- Write anything newly measured about Amiberry in its `NOTES.md`, and keep `README.md` in step.
- The repo uses OpenSpec. For more than a small fix, propose a change there and tell the user.
- Commit or push in that repo only when the user asks.
