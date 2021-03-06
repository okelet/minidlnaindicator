# Change Log

All notable changes to this project will be documented in this file.

## 0.6.0 - Unreleased


## 0.5.5 - 2017-09-08

- Added proxy support (detected from environment and Gnome settings) for update checks.
- Added `--test-mode` parameter to ease testing during development.


## 0.5 - 2017-09-07

- Started to version
- Publish to Pypi
- New way to install from PyPi
- Update check from PyPi
- Kill orphan minidlna process for the same user (configurable)
- New json format for configuration


## [2017.08.31] - 2017-08-31

### Changed

- Migrated to Python 3 (Python 3.5 because Ubuntu 16.04 has not Gi compiled for Python 3.6)
- Modularized to make it compatible with setuptools/Pypi.
- Changed the way to detect mount/umount; now it is not needed dbus; there is a thread that checks the filesystems.
- The application now registers with D-Bus, so multiple instances can not be run.
- The application won't create the application shortcut for the applications menu; it will be done by setuptools.


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
