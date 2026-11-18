## MODIFIED Requirements

### Requirement: Sub-commands
The `amiberry-remote` command SHALL offer these sub-commands, each using the running Amiberry:
`start CONFIG` (start it and wait for Workbench), `quit`, `run COMMAND` (in a new Shell), `key
NAME...`, `type TEXT`, `pointer` (print the pointer's position), `click X Y [right]`, `drag X1 Y1
X2 Y2 [X Y ...] [left|right] [--pause SECONDS]`, `shot PATH` (a screenshot in Amiga pixels),
`rawshot PATH` (Amiberry's own screenshot), `pause`, `resume`, `peek ADDRESS [b|w|l|COUNT]`,
`poke ADDRESS b|w|l VALUE`, `library NAME`, `hunks PROGRAM` (a name or a hunk file), `screen`, and
`send LINE` (a raw socket command, the reply printed).

#### Scenario: Screenshot by hand
- **WHEN** `amiberry-remote shot /tmp/now.png` is run while Amiberry runs
- **THEN** `/tmp/now.png` holds the front screen in Amiga pixels, and the command prints its size

#### Scenario: Hunks by hand
- **WHEN** `amiberry-remote hunks ~/amiga/local-octamed/OctaMED/OctaMED.patched` is run while it runs
- **THEN** it prints one line per hunk: its number, address and length, in hex, with "not loaded" for a hunk without an address

#### Scenario: Amiberry's own screenshot by hand
- **WHEN** `amiberry-remote rawshot /tmp/raw.png` is run while Amiberry runs
- **THEN** `/tmp/raw.png` holds Amiberry's own screenshot, and the command prints its size

#### Scenario: Pause by hand
- **WHEN** `amiberry-remote pause` is run, and later `amiberry-remote resume`
- **THEN** the emulation stops after the first and runs again after the second
