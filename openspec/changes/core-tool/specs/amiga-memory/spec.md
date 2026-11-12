## Purpose

Lets a project read and change the emulated Amiga's memory, and find things in it by name: a
library, or the hunks of a program it has started, so checks can look at a program's own data.

## ADDED Requirements

### Requirement: Read and write memory
The tool SHALL read a byte, word or long at an address, and a block of bytes of any length, and
write a byte, word or long. Values SHALL be read and written big-endian, as the 68000 stores them.
An odd address for a word or long SHALL be an error, with nothing read or written.

#### Scenario: Read a long
- **WHEN** the long at address 4 is read
- **THEN** the result is the address of exec.library (ExecBase)

#### Scenario: Read a block
- **WHEN** 1,040 bytes are read from an address
- **THEN** the result is those 1,040 bytes in order

#### Scenario: Odd address
- **WHEN** a long is read at address 5
- **THEN** it stops with an error and nothing is read

### Requirement: Find a library
The tool SHALL find an open library by name (e.g. `intuition.library`) in exec's library list and
give its base address and version. A name not in the list SHALL be an error naming it.

#### Scenario: Intuition
- **WHEN** `intuition.library` is looked up on Workbench 3.1
- **THEN** the result is its base address and version 40

### Requirement: Find a running program's hunks
Given the name of a program started from a Shell, the tool SHALL find it while it runs and give the
address and length of each of its hunks, in the order of its hunk file, so a project can turn
"hunk n + offset" into an address. If the program is not running, or more than one Shell is
running it, it SHALL stop with an error saying so.

#### Scenario: Patched OctaMED
- **WHEN** the hunks of `OctaMED.patched` are asked for while it runs
- **THEN** the result has one entry per hunk of `OctaMED.patched`, each with the address where it was loaded and its length

#### Scenario: Not running
- **WHEN** the hunks of a program that isn't running are asked for
- **THEN** it stops with an error saying no Shell is running it

### Requirement: Front screen
The tool SHALL give the front screen's position, width, height and title, read from Intuition.

#### Scenario: OctaMED in front
- **WHEN** the front screen is asked for while OctaMED shows its screen
- **THEN** the result is OctaMED's screen: its width, height and title
