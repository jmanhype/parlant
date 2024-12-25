# Changelog

All notable changes to Parlant will be documented here.

## [Unreleased]
- Fix 404 not being returned if a tool service isn't found
- Support for union parameters ("T | None") in tool functions
- Made all stores thread-safe with reader/writer locks
- Fixed having direct calls to asyncio.gather() instead of safe_gather()
- Removed connection kind (entails / suggests) from the guideline connection proposer and all places downstream. the connection_kind argument is no longer needed or supported for all guideline connections.
- Reverted GPT version for guideline connection proposer to 2024-08-06
- Changed definition of causal connection to take the source's when statement into account. The connection proposer now assumes the source's condition is true when examining if it entails other guideline.
- Group engine tests by stability ranking
- Allow tapping into the PluginServer FastAPI app to provide additional custom endpoints


## [1.2.0] - 2024-12-19

### Added
- Expose deletion flag for events in Session API

### Changed
- Print traceback when reporting server boot errors
- Make cancelled operations issue a warning rather than an error

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
