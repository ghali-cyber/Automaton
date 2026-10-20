# Atlas / Automaton

Atlas est une version modifiée et étendue d’[Automaton](https://github.com/Conway-Research/automaton), le runtime d’agent autonome de Conway. Cette distribution ajoute notamment un tableau de bord local, un générateur de projets, un moteur d’opportunités et de décision, une mémoire persistante, une boucle autonome contrôlée, du monitoring, une politique de sécurité, une finance strictement simulée, une reprise après incident et un pont n8n sans credentials.

Le dépôt contient uniquement le code et des exemples de configuration. Il ne contient ni état d’exécution, ni wallet, ni base SQLite, ni credential. Le pack d’état partenaire `Atlas-Partner-State-Pack.zip` est transmis séparément et ne doit jamais être ajouté à Git.

## Prérequis

- Windows avec WSL 2, ou Linux compatible ;
- Node.js 20 ou plus récent ;
- pnpm (la version déclarée dans `package.json` est recommandée) ;
- Python 3.11 ou plus récent pour le tableau de bord Atlas ;
- [Ollama](https://ollama.com/) ;
- n8n uniquement si vous souhaitez tester le pont local optionnel.

## Cloner et installer

```bash
git clone https://github.com/ghali-cyber/Automaton.git
cd Automate
corepack enable
pnpm install --frozen-lockfile
pnpm typecheck
pnpm build
```

Si `corepack` n’est pas disponible, installez pnpm selon sa documentation officielle, puis relancez l’installation.

Créez éventuellement votre configuration locale à partir de l’exemple :

```bash
cp .env.example .env
```

Laissez les champs inutilisés vides. Ne commitez jamais `.env`, `wallet.json`, une base SQLite ou un fichier contenant un secret.

## Installer le modèle Ollama

Démarrez Ollama, puis téléchargez le modèle local :

```bash
ollama pull qwen2.5:1.5b
ollama list
```

Le mode local utilise `http://127.0.0.1:11434` et ne nécessite pas de clé API payante.

## Lancer Automaton en mode local

Après le build :

```bash
node dist/index.js --run
```

Pour exécuter un seul tour :

```bash
node dist/index.js --run --once --prompt "Bonjour, présente tes capacités locales."
```

Au premier démarrage sans pack d’état, l’assistant de configuration crée un état local privé sous `~/.automaton/`. Ce dossier reste hors du dépôt. Les personnes recevant le pack partenaire doivent suivre les instructions qui accompagnent ce pack, séparément du dépôt public.

## Lancer le tableau de bord Atlas

Depuis la racine du dépôt :

```bash
mkdir -p .atlas-runtime
ATLAS_CONTROL_STATE="$PWD/.atlas-runtime" \
ATLAS_CONTROL_SOCKET="$PWD/.atlas-runtime/control.sock" \
python3 atlas-local/atlas-control/launch.py
```

Ouvrez ensuite :

- tableau de bord : `http://127.0.0.1:8766/` ;
- previews locales : `http://127.0.0.1:8767/p/<PROJECT_ID>/` ;
- preview versionnée : `http://127.0.0.1:8767/p/<PROJECT_ID>/v/<VERSION>/`.

Le tableau de bord n’écoute que sur l’interface locale. Les previews sont générées dans l’état local, isolées par projet et par version. Elles servent à examiner le résultat technique ; elles ne constituent pas un déploiement public et n’exécutent aucune action externe.

Pour une installation Linux persistante, adaptez puis installez l’unité fournie dans `atlas-local/atlas-control/systemd/atlas-control.service`. Elle suppose que le code Atlas est copié dans `/opt/atlas-control` et que l’utilisateur système `atlas-control` dispose de `/var/lib/atlas-control` et `/run/atlas-control`.

## n8n optionnel

Les workflows de `atlas-local/atlas-control/n8n-workflows/` sont fournis sans credentials et sont inactifs à l’import. N’ajoutez jamais d’export n8n contenant des credentials. Le pont local applique une allowlist et refuse les actions externes.

## Tests

Suite TypeScript complète :

```bash
pnpm typecheck
pnpm build
pnpm test
```

Suite Atlas/Python :

```bash
cd atlas-local/atlas-control
python3 -m unittest discover -p 'test_*.py'
```

Les tests peuvent créer des fichiers temporaires et des bases éphémères hors Git. Ils ne doivent jamais réutiliser une base Atlas vivante.

## Structure principale

```text
src/                              runtime Automaton et extensions
packages/cli/                     CLI opérateur
atlas-local/atlas-control/        dashboard, moteurs et previews Atlas
atlas-local/atlas-control/static/ interface du dashboard
atlas-local/atlas-control/n8n-workflows/ workflows locaux sans credentials
scripts/                          installation, sauvegarde et tests d’endurance
```

La documentation détaillée est disponible dans `ARCHITECTURE.md`, `DOCUMENTATION.md` et `LOCAL_OLLAMA.md`.

## Publication de nouvelles versions

La méthode de publication est décrite dans `PUBLIC_RELEASE.md`. Chaque version publique doit partir d’un état privé validé, être exportée sans historique Git, repasser par un scan de secrets et les tests, puis recevoir un nouveau commit public. Il ne faut jamais synchroniser automatiquement et aveuglément le dépôt privé vers le dépôt public.

## Licence et attribution

Le projet d’origine Automaton est distribué sous licence MIT. Le fichier `LICENSE`, y compris la mention copyright Conway, est conservé conformément à cette licence. Atlas est une version modifiée et étendue d’Automaton ; aucune affiliation supplémentaire avec Conway n’est sous-entendue.
