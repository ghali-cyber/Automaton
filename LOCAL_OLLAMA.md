# Mode local Ollama

Le mode local permet d’utiliser Atlas/Automaton avec Ollama, sans fournisseur d’inférence payant.

## Préparation

```bash
ollama pull qwen2.5:1.5b
ollama list
```

Ollama doit être accessible à l’adresse `http://127.0.0.1:11434`.

## Exécution

Depuis la racine du dépôt :

```bash
pnpm install --frozen-lockfile
pnpm build
node dist/index.js --run --once --prompt "Bonjour, explique ce que tu peux faire."
```

Pour une boucle persistante :

```bash
node dist/index.js --run
```

Arrêt : `Ctrl+C`.

En mode local, le modèle recommandé est `qwen2.5:1.5b`. L’état d’exécution reste dans le dossier local privé `~/.automaton/` et ne doit jamais être ajouté au dépôt. Les intégrations cloud, sociales, financières ou de provisioning nécessitent une configuration explicite et ne sont pas requises pour le mode Ollama local.
