## Purpose

Gives the tool's operations as one `amiberry-remote` command, for trying things by hand and for
small scripts, without writing Python.

## ADDED Requirements

### Requirement: Sub-commands
The `amiberry-remote` command SHALL offer these sub-commands, each using the running Amiberry:
`start CONFIG` (start it and wait for Workbench), `quit`, `run COMMAND` (in a new Shell), `key
NAME...`, `type TEXT`, `pointer` (print the pointer's position), `click X Y [right]`, `drag X1 Y1
X2 Y2`, `shot PATH` (a screenshot in Amiga pixels), `peek ADDRESS [b|w|l|COUNT]`, `poke ADDRESS
b|w|l VALUE`, `library NAME`, `hunks PROGRAM` (a name or a hunk file), `screen`, and `send LINE` (a raw socket command, the
reply printed).

#### Scenario: Screenshot by hand
- **WHEN** `amiberry-remote shot /tmp/now.png` is run while Amiberry runs
- **THEN** `/tmp/now.png` holds the front screen in Amiga pixels, and the command prints its size

#### Scenario: Hunks by hand
- **WHEN** `amiberry-remote hunks ~/amiga/local-octamed/OctaMED/OctaMED.patched` is run while it runs
- **THEN** it prints one line per hunk: its number, address and length, in hex, with "not loaded" for a hunk without an address

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
