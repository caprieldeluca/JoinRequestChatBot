# JoinRequestChatBot
<sub>(A fork of https://github.com/Poolitzer/JoinRequestChatBot)</sub>

This is a small bot which forwards all chats from people trying to join your group to a second group (probably consistent of your admins), and all messages from that second group back to the proper private chat.

There will be three buttons below all the messages belonging to an applying user: ✅, ❌ and 🛑. ✅ approves the join request, ❌ declines, and 🛑 bans the users (forever), so they can't reapply to join the group.

Every message is supported, a wanting-to-join user message will reply to the last one in chat, so you can mute the second chat and won't miss a follow-up to your conversation.

You can send a reply with a !, the bot ignores these messages.

Also features a configurable 24 hour timer after the last send message, after which the wanting-to-join users join request is rejected.

Add the bot with add member + ban users right in the main group.

---

## Adaptaciones de OSM-AR

- Usamos [`uv`](https://docs.astral.sh/uv/) para crear el entorno Python.
- Las variables se configuran por defecto en el archivo `config.yaml`. Pueden ser sobreescritas por un archivo de configuraciones personalizadas.
- El token del bot y la ruta al archivo de configuraciones personalizadas se cargan como variables de entorno.

### Instalación rápida

1. Clonar el repositorio:
```bash
git clone https://codeberg.org/caprieldeluca/JoinRequestChatBot.git && cd JoinRequestChatBot
```

2. Sincronizar el entorno Python:
```bash
uv sync
```

3. Editar el archivo de configuraciones por defecto:
```bash
nano config.yaml
```

4. Correr el bot:
```bash
TOKEN="Your:Token-Here" uv run bot.py
```

### Instalación personalizada

1. Copiar el archivo de configuración y editarlo:
```bash
cp config.yaml custom_config.yaml && nano custom_config.yaml
```

2. Copiar el archivo de variables de entorno y editarlo:
```bash
cp .env.example .env && nano .env
```

3. Crear un script que ejecute el bot con entorno personalizado. Por ejemplo:
```bash
#!/usr/bin/env bash
set -eu

# Rutas (adaptar y endurecer según corresponda)
ENV_FILE=".env"
PYTHON=".venv/bin/python"
BOT="bot.py"

# Exportar variables de entorno
set -a
source "$ENV_FILE"
set +a

# Ejecutar el Bot
exec "$PYTHON" "$BOT"
```

### Otros cambios

Ver la lista completa de cambios en [CHANGELOG.md](CHANGELOG.md).
