## MODIFIED Requirements

### Requirement: Click and drag
The tool SHALL click the left or right mouse button at a screen position (pointer put there first),
and drag with the left or right button held from a first position through one or more further
positions, along straight lines, in steps small enough that the program sees the pointer move.
The button SHALL go down at the first position and up at the last. When asked, the tool SHALL wait
a given time at each position between the first and the last, so a menu can show its items. Fewer
than two positions, an x without its y, or a button other than left or right SHALL be an error,
with nothing sent. It SHALL leave every button released, also when a step fails.

#### Scenario: Click a button
- **WHEN** the left button is clicked at x 330, y 48
- **THEN** the pointer is at x 330, y 48 while the button goes down and up

#### Scenario: Drag a marker
- **WHEN** a drag from x 100, y 120 to x 160, y 120 is asked for
- **THEN** the button goes down at x 100, the pointer passes through the positions in between, and the button goes up at x 160

#### Scenario: Right-button drag through a menu
- **WHEN** a right-button drag through x 300, y 100, then x 290, y 89, then x 360, y 70 is asked for, with a pause of 0.3 s
- **THEN** the right button goes down at x 300, y 100, the pointer passes every position along both lines, waits 0.3 s at x 290, y 89, and the button goes up at x 360, y 70

#### Scenario: Not a drag
- **WHEN** a drag with only one position, or with the middle button, is asked for
- **THEN** it stops with an error, and no button goes down
