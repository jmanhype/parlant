# Changelog

All notable changes to Parlant will be documented here.

## [Unreleased]

None


## [1.2.0] - 2024-12-19

### Added
- Expose deletion flag for events in Session API

### Changed
- Print traceback when reporting server boot errors
- Make cancelled operations issue a warning rather than an error
- Made all stores thread-safe with reader/writer locks

### Fixed
- Fixed tool calling with optional parameters
- Fixed sandbox UI issues with message regeneration and status icon
- Fixed case where guideline is applied due to condition being partially applied

### Removed

None


## [1.1.0] - 2024-12-18

### Added

- Customer selection in sandbox Chat UI
- Support tool calls with freshness rules for context variables
- Add support for loading external modules for changing engine behavior programatically
- CachedSchematicGenerator to run the test suite more quickly
- TransientVectorDatabase to run the test suite more quickly

### Changed

- Changed model path for Chroma documents. You may need to delete your `runtime-data` dir.

### Fixed

- Improve handling of partially fulfilled guidelines

### Removed

None
