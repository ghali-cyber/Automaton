# Publication publique sûre

Le dépôt privé reste la source de vérité. Le dépôt public est une distribution reconstruite et ne doit jamais recevoir l’historique Git privé.

## Processus obligatoire

1. Valider la version candidate sur la branche privée prévue.
2. Sauvegarder localement la source et noter son commit exact.
3. Exporter uniquement l’arbre de fichiers suivi dans un nouveau dossier, sans `.git`.
4. Exclure les états locaux, bases SQLite, wallets, `.env`, credentials, logs, caches, backups, dépendances installées et packs partenaires.
5. Conserver `LICENSE` et toutes les attributions requises.
6. Remplacer les configurations locales par des exemples vides ou des placeholders.
7. Examiner les workflows n8n et vérifier qu’ils ne contiennent aucun credential.
8. Lancer un scanner de secrets sur l’intégralité de l’export.
9. Installer les dépendances depuis le lockfile, puis lancer le typecheck, le build et les tests TypeScript et Python.
10. Refaire le scan de secrets après les tests et supprimer tous les artefacts générés.
11. Initialiser un nouveau dépôt Git dans l’export propre et créer un commit de publication.
12. Vérifier l’URL et la visibilité publique de la cible avant le push.

Flux attendu :

```text
dépôt privé → version validée → export sans historique → scan sécurité
             → tests → scan final → nouveau commit → dépôt public
```

## Interdictions

- Ne jamais pousser depuis le checkout privé vers le dépôt public.
- Ne jamais changer le remote `origin` du dépôt privé pour publier.
- Ne jamais utiliser une synchronisation automatique non relue.
- Ne jamais publier `wallet.json`, `.env`, `*.db`, `*.sqlite*`, clés, tokens, credentials n8n, logs, backups ou `Atlas-Partner-State-Pack.zip`.
- Ne jamais continuer une publication si la licence, la cible GitHub ou le résultat du scan est ambigu.

Chaque publication est un nouvel acte de distribution et doit repasser par l’ensemble de ces contrôles.
