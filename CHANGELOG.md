# Changelog

All notable changes to Parlant will be documented here.

## [Unreleased]
- Expose deletion flag for events in Session API
- Print traceback when reporting server boot errors

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

