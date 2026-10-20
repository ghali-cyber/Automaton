# Workflows n8n Atlas locaux

Ces trois workflows sont sans credentials, inactifs à l’import et limités à des transformations locales :

- `AtlasDataTransform001` normalise des données ;
- `AtlasLocalReport001` génère un rapport texte local ;
- `AtlasTaskProcess001` traite une tâche Atlas autorisée.

Le pont `n8n_bridge.py` refuse tout identifiant absent de son allowlist, borne la taille des entrées, journalise succès/échec en SQLite et garantit `external_actions: false`.

Si un connecteur personnel est ajouté plus tard : `CREDENTIAL_REQUIRED`. Aucun credential ne doit être exporté avec le workflow.
