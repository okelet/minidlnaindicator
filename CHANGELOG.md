# Change Log
All notable changes to this project will be documented in this file.

## [Unreleased]

## [2016.07.23] - 2016-07-23
### Added
- Monitoring of USB external drives connected/disconnected.
- Added option to "Restart and reindex"
- Added CHANGELOG (http://keepachangelog.com)
- Requirements documented

### Changed
- Changed from "Gtk.Main()" to "GObject.MainLoop()" due to the problems to stop with Control-C and from the indicator menu.

### Fixed
- Fixed problem when `~/.config/autostart` doesn't exist.
- Problems with unicode when initial creation of configuration file.
