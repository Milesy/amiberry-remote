# command-line Specification

## Purpose

Gives the tool's operations as one `amiberry-remote` command, for trying things by hand and for
small scripts, without writing Python.

## Requirements

### Requirement: Sub-commands
The `amiberry-remote` command SHALL offer the tool's operations as sub-commands, each using the
running Amiberry: those for the session and for input below, and for the screen and memory `shot
PATH` (a screenshot in Amiga pixels), `rawshot PATH` (Amiberry's own screenshot), `screen`, `peek
ADDRESS [b|w|l|COUNT]`, `poke ADDRESS b|w|l VALUE`, `library NAME` and `hunks PROGRAM` (a name or
a hunk file).

#### Scenario: Screenshot by hand
- **WHEN** `amiberry-remote shot /tmp/now.png` is run while Amiberry runs
- **THEN** `/tmp/now.png` holds the front screen in Amiga pixels, and the command prints its size

#### Scenario: Hunks by hand
- **WHEN** `amiberry-remote hunks ~/amiga/local-octamed/OctaMED/OctaMED.patched` is run while it runs
- **THEN** it prints one line per hunk: its number, address and length, in hex, with "not loaded" for a hunk without an address

#### Scenario: Amiberry's own screenshot by hand
- **WHEN** `amiberry-remote rawshot /tmp/raw.png` is run while Amiberry runs
- **THEN** `/tmp/raw.png` holds Amiberry's own screenshot, and the command prints its size

### Requirement: Session sub-commands
The command SHALL offer `start CONFIG` (start Amiberry and wait for Workbench), `quit`, `run
COMMAND` (in a new Shell), `pause`, `resume`, and `send LINE` (a raw socket command, the reply
printed).

#### Scenario: Pause by hand
- **WHEN** `amiberry-remote pause` is run, and later `amiberry-remote resume`
- **THEN** the emulation stops after the first and runs again after the second

### Requirement: Input sub-commands
The command SHALL offer `key NAME...`, `type TEXT`, `pointer` (print the pointer's position),
`click X Y [right]` and `drag X1 Y1 X2 Y2 [X Y ...] [left|right] [--pause SECONDS]`.

#### Scenario: Right-button drag by hand
- **WHEN** `amiberry-remote drag 300 100 290 89 360 70 right --pause 0.3` is run
- **THEN** the right button is held from x 300, y 100 through x 290, y 89 to x 360, y 70, with 0.3 s at x 290, y 89

### Requirement: Numbers and errors
Addresses and values SHALL be accepted in decimal, `0x` hex or `$` hex, and printed in `$` hex.
A failure SHALL print one line saying what went wrong, to standard error, and exit with a non-zero
status.

#### Scenario: Amiberry not running
- **WHEN** `amiberry-remote pointer` is run with no Amiberry running
- **THEN** it prints that Amiberry is not running and exits with a non-zero status

#### Scenario: Hex address
- **WHEN** `amiberry-remote peek $4 l` is run
- **THEN** it prints ExecBase's address in `$` hex
