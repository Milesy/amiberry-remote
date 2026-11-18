## ADDED Requirements

### Requirement: Amiberry's own screenshot
The tool SHALL give Amiberry's own screenshot as it is, border and all, and save it at a path
when the caller names one. It SHALL do this whatever is shown, without looking for the front
screen, so a display that isn't an Intuition screen (a program that has taken the display over)
can be captured too.

#### Scenario: A game's own display
- **WHEN** Amiberry's own screenshot is asked for while a program shows its own display, with Workbench's screen still the front one
- **THEN** the picture is Amiberry's whole screenshot, showing the program's display
