# Atlas / Automaton

Atlas est une version modifiée et étendue d’[Automaton](https://github.com/Conway-Research/automaton), le runtime d’agent autonome de Conway. Cette distribution ajoute notamment un tableau de bord local, un générateur générique multi-catégories, une mémoire inter-projets, un moteur d’opportunités et de décision, une recherche Web publique contrôlée, une boucle autonome durable, du monitoring, une politique de sécurité et d’audit, une finance strictement simulée, une reprise après incident et un pont n8n sans credentials.

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
cd Automaton
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

## Web public contrôlé

Le gateway de `atlas-local/atlas-business/` fournit le pipeline `SEARCH → OPEN → EXTRACT → NORMALIZE → SOURCE → STORE`. Il utilise des interfaces publiques, respecte `robots.txt`, limite le débit et les tentatives, refuse les redirections, les IP privées, les connexions, CAPTCHA, paiements, uploads et téléchargements dangereux, puis traite chaque page comme une preuve non fiable.

Les recherches conservent l’URL canonique, le domaine, le titre, les dates disponibles, l’extrait, le type de source, la confiance et le rattachement à l’opportunité ou au projet. Les doublons d’URL, de contenu et d’entité sont filtrés. Une opportunité Web n’est sélectionnable qu’après au moins deux sources issues de deux domaines indépendants. Aucune fonction de contact, publication, compte externe, paiement ou contournement anti-bot n’est fournie.

Pour une installation Linux/WSL persistante, créez des utilisateurs système distincts `atlas-tools` et `atlas-control`, ainsi qu’un groupe partagé `atlas`. Ajoutez aussi au groupe `atlas` l’utilisateur qui lance Automaton :

```bash
sudo groupadd --system atlas 2>/dev/null || true
sudo groupadd --system atlas-control 2>/dev/null || true
sudo useradd --system --home /nonexistent --shell /usr/sbin/nologin --gid atlas atlas-tools 2>/dev/null || true
sudo useradd --system --home /nonexistent --shell /usr/sbin/nologin --gid atlas-control atlas-control 2>/dev/null || true
sudo usermod -aG atlas atlas-control
sudo usermod -aG atlas "$USER"
sudo install -d -o atlas-tools -g atlas -m 0750 /srv/atlas-workspace
sudo install -d -o root -g root -m 0755 /opt/atlas-business /opt/atlas-control
sudo cp atlas-local/atlas-business/*.py /opt/atlas-business/
sudo cp atlas-local/atlas-control/*.py /opt/atlas-control/
sudo cp -r atlas-local/atlas-control/static atlas-local/atlas-control/templates /opt/atlas-control/
sudo chown -R root:root /opt/atlas-business /opt/atlas-control
sudo find /opt/atlas-business /opt/atlas-control -type d -exec chmod 0755 {} +
sudo find /opt/atlas-business /opt/atlas-control -type f -exec chmod 0644 {} +
sudo cp atlas-local/atlas-business/systemd/atlas-business.service /etc/systemd/system/
sudo cp atlas-local/atlas-control/systemd/atlas-control.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now atlas-business atlas-control
```

Les fichiers placés sous `/opt` doivent rester détenus par `root:root` et non modifiables par les comptes de service. Une nouvelle session peut être nécessaire après l’ajout de l’utilisateur interactif au groupe `atlas`.

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
python3 -m unittest discover -s atlas-local/atlas-control -p 'test_*.py'
```

Validation de publication (secrets, état local et chemins personnels) :

```bash
python3 scripts/validate-public-release.py
```

Les tests peuvent créer des fichiers temporaires et des bases éphémères hors Git. Ils ne doivent jamais réutiliser une base Atlas vivante.

## Structure principale

```text
src/                              runtime Automaton et extensions
packages/cli/                     CLI opérateur
atlas-local/atlas-control/        dashboard, moteurs et previews Atlas
atlas-local/atlas-business/       gateway Web public restreint et workspace isolé
atlas-local/atlas-control/static/ interface du dashboard
atlas-local/atlas-control/n8n-workflows/ workflows locaux sans credentials
scripts/                          installation, sauvegarde et tests d’endurance
```

La documentation détaillée est disponible dans `ARCHITECTURE.md`, `DOCUMENTATION.md` et `LOCAL_OLLAMA.md`.

## Publication de nouvelles versions

La méthode de publication est décrite dans `PUBLIC_RELEASE.md`. Chaque version publique doit partir d’un état privé validé, être exportée sans historique Git, repasser par un scan de secrets et les tests, puis recevoir un nouveau commit public. Il ne faut jamais synchroniser automatiquement et aveuglément le dépôt privé vers le dépôt public.

## Licence et attribution

Le projet d’origine Automaton est distribué sous licence MIT. Le fichier `LICENSE`, y compris la mention copyright Conway, est conservé conformément à cette licence. Atlas est une version modifiée et étendue d’Automaton ; aucune affiliation supplémentaire avec Conway n’est sous-entendue.
