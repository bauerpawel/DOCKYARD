# Dockyard — serveur MCP du catalogue d'applications

Le catalogue Dockyard décrit des applications Docker prêtes à l'emploi (les mêmes que Portainer lit dans `templates.json`). Une fois ce serveur MCP ajouté, votre agent peut trouver une application et la déployer chez vous : dans Docker en local ou dans votre propre Portainer.

Le serveur du catalogue ne se connecte pas à votre réseau. L'adresse de votre Portainer et votre clé d'API restent sur votre ordinateur. L'agent qui dispose de ce serveur MCP s'adresse lui-même à Docker et à Portainer.

Adresse du serveur :

```text
https://YOUR-DOMAIN/mcp
```

## Claude Code

Dans un terminal, une fois pour tous les projets :

```bash
claude mcp add --scope user --transport http dockyard https://YOUR-DOMAIN/mcp
```

Ou un fichier `.mcp.json` dans le répertoire du projet. Le champ `type` est obligatoire :

```json
{
  "mcpServers": {
    "dockyard": {
      "type": "http",
      "url": "https://YOUR-DOMAIN/mcp"
    }
  }
}
```

Ouvrez une nouvelle session Claude Code après avoir enregistré le fichier. Pour vérifier : `claude mcp list`.

## Claude Desktop

Si les réglages permettent d'ajouter un connecteur personnalisé (Connectors), collez-y l'adresse `https://YOUR-DOMAIN/mcp`.

Si votre version de Desktop ne lance que des programmes locaux, ajoutez le serveur dans le fichier de configuration via `mcp-remote`. Node.js est nécessaire.

- Windows : `%APPDATA%\Claude\claude_desktop_config.json`
- macOS : `~/Library/Application Support/Claude/claude_desktop_config.json`
- Linux : `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "dockyard": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://YOUR-DOMAIN/mcp"]
    }
  }
}
```

Enregistrez le fichier et redémarrez Claude Desktop.

## Codex

```bash
codex mcp add dockyard --url https://YOUR-DOMAIN/mcp
```

Le fichier est commun à la CLI et à l'extension :

- Windows : `%USERPROFILE%\.codex\config.toml`
- macOS et Linux : `~/.codex/config.toml`

```toml
[mcp_servers.dockyard]
url = "https://YOUR-DOMAIN/mcp"
```

Dans une session Codex, la commande `/mcp` affiche le serveur `dockyard`. Redémarrez Codex après avoir modifié le fichier à la main.

## Grok

```bash
grok mcp add --transport http dockyard https://YOUR-DOMAIN/mcp
```

La même chose dans le fichier de configuration :

- Windows : `%USERPROFILE%\.grok\config.toml`
- macOS et Linux : `~/.grok/config.toml`

```toml
[mcp_servers.dockyard]
url = "https://YOUR-DOMAIN/mcp"
```

Pour vérifier : `grok mcp list`. Ouvrez une nouvelle session Grok après avoir modifié le fichier.

## Gemini CLI

```bash
gemini mcp add --transport http dockyard https://YOUR-DOMAIN/mcp
```

La même chose dans le fichier `~/.gemini/settings.json` :

```json
{
  "mcpServers": {
    "dockyard": {
      "httpUrl": "https://YOUR-DOMAIN/mcp"
    }
  }
}
```

## Cursor

Le fichier `~/.cursor/mcp.json` (tous les projets) ou `.cursor/mcp.json` dans le répertoire du projet :

```json
{
  "mcpServers": {
    "dockyard": {
      "url": "https://YOUR-DOMAIN/mcp"
    }
  }
}
```

## VS Code

Le fichier `.vscode/mcp.json` dans le répertoire du projet, ou la configuration utilisateur ouverte par la commande **MCP: Open User Configuration** :

```json
{
  "servers": {
    "dockyard": {
      "type": "http",
      "url": "https://YOUR-DOMAIN/mcp"
    }
  }
}
```

## Autres clients MCP

Tout client qui prend en charge les serveurs distants via Streamable HTTP accepte l'adresse du serveur indiquée en haut. Un client qui ne lance que des programmes locaux se connecte via `mcp-remote`, comme dans le fichier Claude Desktop ci-dessus.

## Ce qui reste chez vous

Seule l'adresse du catalogue va dans la configuration MCP. N'y mettez pas votre clé Portainer.

Gardez les données Portainer dans l'environnement depuis lequel l'agent démarre, ou donnez-les à l'agent dans la conversation lorsqu'il les demande :

```text
PORTAINER_URL=https://192.168.1.10:9443
PORTAINER_API_KEY=ptr_...
PORTAINER_ENDPOINT_ID=1
```

La clé : dans Portainer, **My account → Access tokens**. Le numéro de l'environnement est l'`Id` de la liste des environnements. Il apparaît aussi dans l'adresse une fois l'environnement ouvert. L'agent peut lire la liste lui-même, par un appel d'API depuis votre ordinateur, dès qu'il a l'adresse et la clé.

Pour la cible Docker, l'agent utilise la commande `docker` sur l'ordinateur où il s'exécute. Docker Desktop ou le moteur Docker doit être démarré.

## Comment demander à l'agent

```text
Trouve n8n dans Dockyard et lance-le dans Docker sur cet ordinateur.
```

```text
Déploie AdGuard dans mon Portainer.
```

L'agent présente un plan (ports, volumes, mots de passe à changer) et ne commence qu'après votre accord. Les mots de passe par défaut du modèle, comme `admin`, doivent être remplacés par les vôtres. Pour un conteneur privilégié, l'agent doit demander séparément.
