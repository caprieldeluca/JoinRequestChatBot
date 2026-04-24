# Changelog

Registro de cambios.

## [Unreleased]

### Added
- Los tiempos de expiración se guardan en la persistencia y se agendan nuevamente al reiniciar.

### Changed
- Configuraciones personalizadas son opcionales y pueden sobreescribir las del archivo de configuraciones por defecto.

---

## [0.1.0] - 2026-04-21

### Added
- Archivo de configuración YAML personalizado.
- Variables de entorno mediante archivo `.env`.

### Changed
- Texto en los botones.
- Todos los mensajes del bot van a un topic del approve group.
- Adaptación del bot para entorno de despliegue.

### Fixed
- Dependencia `job-queue` faltante en la instalación de `python-telegram-bot`.

### Removed
- Se quitó el comando start (los créditos al código fuente original se integrarán en el mensaje de bienvenida).