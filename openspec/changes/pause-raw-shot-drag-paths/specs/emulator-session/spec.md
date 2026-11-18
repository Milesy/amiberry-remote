## ADDED Requirements

### Requirement: Pause and resume the emulation
The tool SHALL pause the emulation and resume it, so that memory and the display hold still
between the two and several reads and a screenshot show one moment. It SHALL offer a paused
block that resumes the emulation when the block ends, also when the block fails. A pause or
resume that Amiberry refuses SHALL be an error naming the command.

#### Scenario: Memory holds still while paused
- **WHEN** the emulation is paused and a value the Amiga changes all the time is read twice, some time apart
- **THEN** both reads give the same value, and after resuming the value changes again

#### Scenario: A failing block still resumes
- **WHEN** something fails inside a paused block
- **THEN** the emulation is resumed and the failure is passed on
