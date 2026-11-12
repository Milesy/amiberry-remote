## Purpose

Lets a project look at the emulated screen in the Amiga's own pixels: take screenshots, compare an
area with the picture it expects, and wait until the screen shows it.

## ADDED Requirements

### Requirement: Screenshot in Amiga pixels
The tool SHALL take a screenshot and give it as a picture of the front screen in that screen's own
pixels: one picture pixel per Amiga pixel, Amiberry's border removed, and doubled lines or columns
undone, with the colours Amiberry shows. The raw screenshot SHALL be kept as well when the caller
names a path for it.

#### Scenario: OctaMED's screen
- **WHEN** a screenshot is taken while OctaMED's screen is in front
- **THEN** the picture has that screen's width and height, and its pixel x 0, y 0 is the screen's top-left pixel

#### Scenario: Workbench screen
- **WHEN** a screenshot is taken while Workbench is in front
- **THEN** the picture has the Workbench screen's width and height

### Requirement: Compare an area
The tool SHALL compare an area of a screenshot (left, top, width, height in screen pixels) with an
expected picture of the same size, and report how many pixels differ and where the first one is.
Colours SHALL match to the Amiga's precision, so a colour that only differs below what the
Amiga can show is the same. When pixels differ, it SHALL save the screenshot and a picture that
marks the differing pixels, and give their paths.

#### Scenario: Same
- **WHEN** an area equals the expected picture
- **THEN** the result is 0 differing pixels and no files are saved

#### Scenario: Different
- **WHEN** 3 pixels of the area differ from the expected picture
- **THEN** the result is 3, with the first differing position, and the paths of the saved screenshot and difference picture

#### Scenario: Wrong size
- **WHEN** the expected picture is not the size of the area
- **THEN** it stops with an error giving both sizes

### Requirement: Wait for the screen
The tool SHALL wait until an area of the screen matches an expected picture, taking screenshots
until it does, and stop with an error, saving the last screenshot and difference picture, if it
doesn't within a time limit.

#### Scenario: Program starts
- **WHEN** a project waits up to 20 seconds for OctaMED's title strip to match its picture, and OctaMED appears after 6 seconds
- **THEN** the wait returns after about 6 seconds

#### Scenario: Never appears
- **WHEN** the area doesn't match within the time limit
- **THEN** it stops with an error giving the paths of the last screenshot and its difference picture
