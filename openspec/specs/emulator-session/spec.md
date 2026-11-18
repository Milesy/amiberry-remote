# emulator-session Specification

## Purpose

Gets a project from nothing to a Workbench with a Shell ready for commands: connects to a running
Amiberry or starts one with the project's config, and quits it again.

## Requirements

### Requirement: Connect to a running Amiberry
The tool SHALL use an Amiberry that is already running and answering on its remote-control socket,
without restarting it. If no Amiberry answers and the caller did not ask for one to be started,
the tool SHALL stop with an error saying that Amiberry is not running.

#### Scenario: Amiberry already running
- **WHEN** a session is opened while Amiberry is running
- **THEN** the session uses it, and the emulated machine is not reset

#### Scenario: Not running
- **WHEN** a session is opened with no Amiberry running and no config given
- **THEN** it stops with an error saying Amiberry is not running

### Requirement: Start Amiberry with a project's config
Given an Amiberry config file, the tool SHALL start Amiberry with it, with no settings window, and
wait until it answers on the socket. The Amiberry program SHALL be found from the `AMIBERRY`
environment variable, else `amiberry` on the `PATH`, else `~/amiga/emu/Amiberry-8.4.2-x86_64.AppImage`.
The config file SHALL NOT be changed.

#### Scenario: Start with the OctaMED config
- **WHEN** a session is opened with `A1200-OctaMED.uae` and no Amiberry is running
- **THEN** Amiberry starts with that config and the session can send commands to it, and the config file is unchanged

#### Scenario: Amiberry missing
- **WHEN** no Amiberry program is found in any of the three places
- **THEN** it stops with an error naming the places it looked

#### Scenario: Config missing
- **WHEN** the config file named does not exist
- **THEN** it stops with an error naming the file, and nothing is started

### Requirement: Wait for Workbench
After starting Amiberry, the tool SHALL wait until Workbench is up and ready for input, and then
return; if it is not up within a time limit (default 90 seconds), it SHALL stop with an error and
save a screenshot of what is on screen.

#### Scenario: Boot to Workbench
- **WHEN** Amiberry has been started with a config that boots Workbench
- **THEN** the tool returns once Workbench is up, not after a fixed delay

#### Scenario: Boot never finishes
- **WHEN** Workbench is not up within the time limit
- **THEN** it stops with an error and the path of a screenshot of the screen at that moment

### Requirement: Run a Shell command
The tool SHALL open a new Shell window and type a command into it, followed by Return. Before
typing, it SHALL make sure the Shell window it opened is the active window, so the keys don't go
to another window.

#### Scenario: Run a program from PC:
- **WHEN** a project asks to run `cd PC:OctaMED` and then `OctaMED.patched`
- **THEN** both commands are typed into a Shell window that has the keyboard, and OctaMED starts

### Requirement: Quit Amiberry
The tool SHALL be able to quit Amiberry, and SHALL report when it has gone.

#### Scenario: Quit
- **WHEN** quit is asked for
- **THEN** Amiberry exits and the socket no longer answers
