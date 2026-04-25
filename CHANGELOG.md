# Changelog

## [Unreleased]

### Added
- Persistent expiration times. Expiration rejection jobs are rescheduled on startup.

### Changed
- Custom configuration variables are optional and override defaults.
- Custom configuration path environment variable name is now `CUSTOM_CONFIG_PATH`.
- Approve topic ID configuration variable name is now `requests_appr_tid`.

---

## [0.1.0] - 2026-04-21

### Added
- Custom YAML configuration file.
- Environment variables via `.env` file.

### Changed
- Text in buttons.
- All bot messages from private chats go to a topic inside approve group.
- Adaptación del bot para entorno de despliegue.

### Fixed
- `job-queue` dependency in `python-telegram-bot`.

### Removed
- `/start` command (link to source code included in Bot's description).