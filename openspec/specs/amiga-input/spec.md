# amiga-input Specification

## Purpose

Drives the emulated Amiga's keyboard and mouse from the PC: keys by name, typed text, and the
pointer put on an exact position of the front screen to click or drag there.

## Requirements

### Requirement: Keys by name
The tool SHALL press, hold and release Amiga keys given by name (letters, digits, punctuation, the
function keys, `Help`, `Del`, `Esc`, `Return`, `Enter`, `Space`, `Tab`, the cursor keys, both
Shifts, both Amiga keys, `Ctrl`, both Alts) and send them as Amiga key codes. A key held together
with others (e.g. `Ctrl-F2`, `RAmiga-E`) SHALL be pressed in order and released in reverse order.
An unknown key name SHALL be an error naming it, with nothing sent.

#### Scenario: Help key
- **WHEN** `Help` is pressed
- **THEN** the Amiga receives key code `$5F` down and then up

#### Scenario: Combination
- **WHEN** `Ctrl-F2` is pressed
- **THEN** Ctrl goes down, F2 goes down and up, then Ctrl goes up

#### Scenario: Unknown key
- **WHEN** a key called `Hlep` is pressed
- **THEN** it stops with an error naming `Hlep`, and no key is sent

### Requirement: Type text
The tool SHALL type text as a person would on the Amiga's US keyboard, holding Shift for capitals
and shifted characters, and pressing Return for a line end. A character the keyboard can't type
SHALL be an error naming it, with nothing sent.

#### Scenario: Shell command with capitals and a colon
- **WHEN** `cd PC:OctaMED` is typed
- **THEN** the Amiga receives the keys for those characters, with Shift held for `P`, `C`, `:`, `O`, `M`, `E` and `D`

### Requirement: Put the pointer on a screen position
Given a position in the front screen's own pixels, the tool SHALL move the pointer there, reading
the pointer's position from the Amiga after each move until it is exactly there. It SHALL work
whatever the pointer speed-up and the screen's resolution. If the position is outside the screen,
or the pointer doesn't get there within a limit of moves, it SHALL stop with an error giving the
position it reached.

#### Scenario: Position on OctaMED's screen
- **WHEN** the pointer is put on x 330, y 48 of OctaMED's screen
- **THEN** reading the pointer position from the Amiga gives x 330, y 48

#### Scenario: Off the screen
- **WHEN** the pointer is asked to go to x 700 on a 640-pixel-wide screen
- **THEN** it stops with an error, and the pointer is not moved

### Requirement: Click and drag
The tool SHALL click the left or right mouse button at a screen position (pointer put there first),
and drag with the left or right button held from one position to another along a straight line, in
steps small enough that the program sees the pointer move. It SHALL leave every button released,
also when a step fails.

#### Scenario: Click a button
- **WHEN** the left button is clicked at x 330, y 48
- **THEN** the pointer is at x 330, y 48 while the button goes down and up

#### Scenario: Drag a marker
- **WHEN** a drag from x 100, y 120 to x 160, y 120 is asked for
- **THEN** the button goes down at x 100, the pointer passes through the positions in between, and the button goes up at x 160

### Requirement: Drag through several positions
A drag SHALL be able to go on through further positions in turn, along straight lines, the button
going down at the first position and up at the last. When asked, the tool SHALL wait a given time
at each position between the first and the last, so a menu can show its items. Fewer than two
positions, an x without its y, or a button other than left or right SHALL be an error, with
nothing sent.

#### Scenario: Right-button drag through a menu
- **WHEN** a right-button drag through x 300, y 100, then x 290, y 89, then x 360, y 70 is asked for, with a pause of 0.3 s
- **THEN** the right button goes down at x 300, y 100, the pointer passes every position along both lines, waits 0.3 s at x 290, y 89, and the button goes up at x 360, y 70

#### Scenario: Not a drag
- **WHEN** a drag with only one position, or with the middle button, is asked for
- **THEN** it stops with an error, and no button goes down
