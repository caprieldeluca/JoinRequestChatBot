# Changelog

## [Unreleased]

### Added
- Persistent expiration times. Expiration rejection jobs are rescheduled on startup.
- Custom configuration variables are optional and override defaults.
- Send messages to topics is optional.
- Responses to bot can be sent to a different (than join requests) topic.
- Optionally relay approved message to main group.

### Changed
- Default configuration (mandatory) path is resolved at runtime (to the same directory as bot.py).
- Custom configuration path environment variable name to `CUSTOM_CONFIG_PATH`.
- Approve topic ID configuration variable name to `requests_appr_tid`.
- Approve welcome message configuration variable name to `welcome_msg`.
- Attachments from private chats are disabled.

### Fixed
- Ignored ("!") from approve group message checks first.
- Reject job logic in edge cases.
- Bot data cleanup at finish user.

---

## [0.1.0] - 2026-04-21

### Added
- Custom YAML configuration file.
- Environment variables via `.env` file.

### Changed
- Text in buttons.
- All bot messages from private chats go to a topic inside approve group.

### Fixed
- `job-queue` dependency in `python-telegram-bot`.

### Removed
- `/start` command (link to source code in Bot's description).
