# Backend Vexa et cycle de vie des réunions

Périmètre : #124, #125, #126, #127, #128 et #77. Implémentation dans
`backend/src/baraza`, sans modification du frontend, fork de Vexa ni déploiement distant.

## Choix et dépendances

- **Vexa Lite v0.12.26**, image officielle publiée, épinglée par tag et digest multiarchitecture.
  Lite exécute les bots dans le conteneur : aucun montage du socket Docker.
- **Whisper local** via `fedirz/faster-whisper-server:0.5.0-cpu`, ou son image CUDA 0.5.0.
  Images du projet recommandé par le déploiement Lite officiel, également épinglées par digest.
- PostgreSQL Vexa séparé de PostgreSQL Baraza, image 17.6-alpine épinglée.
- **Polling authentifié**, cible toutes les cinq secondes, sans webhook entrant.
  Cette version possède des webhooks signés, mais le polling suffit aux états demandés,
  simplifie la reprise et évite une nouvelle surface entrante. Aucun événement HTTP fourni
  par un tiers ne peut enregistrer un bot ou terminer une capture.
- Google Meet uniquement dans l'adaptateur, conformément au POC de l'ADR 0001.
  Le client sait typer les plateformes Vexa, sans activer de nouveaux adaptateurs Teams/Zoom.
- Le dépôt Vexa porte une licence Apache-2.0 à ce tag. Aucun code Vexa n'est incorporé à Baraza.

L'ADR 0001 est encore « proposed » et #32 reste ouverte : cette implémentation optionnelle
ne constitue pas une validation de cette décision par l'équipe.
Les dépendances #52, #97, #106 et #110 ne sont pas entièrement présentes dans le dépôt :
ce travail ajoute un stockage minimal des états, les tâches worker et un contrat de test
réutilisable. Il n'implémente pas les API publiques de capture, le modèle métier Meeting complet
ni le parcours d'information/consentement des participants.

## Démarrage CPU

Depuis la racine du dépôt :

```bash
cp .env.example .env
# Remplacer VEXA_DB_PASSWORD, VEXA_ADMIN_TOKEN et VEXA_INTERNAL_SECRET dans .env.
docker compose --profile vexa up -d --build
docker compose --profile vexa ps
```

Le profil reste facultatif : `docker compose up` n'active aucun service Vexa.
`BARAZA_VEXA_ENABLED=false` permet de démarrer Baraza avant de provisionner sa clé.
Vexa Lite provisionne automatiquement un utilisateur self-host et des clés avec scopes `bot,tx`.
Une fois le service initialisé :

```bash
docker compose exec vexa cat /run/vexa/key.env
```

Copier la valeur `VEXA_API_KEY` obtenue dans `BARAZA_VEXA_API_KEY` du fichier `.env`, puis passer
`BARAZA_VEXA_ENABLED=true`. Cette clé est une clé utilisateur Vexa ; le token administrateur
n'est pas une clé pour les endpoints bots/transcripts. Ne pas publier ni committer ces valeurs.

```bash
docker compose up -d --force-recreate worker
```

La configuration des services vient de `.env` ; les noms et préfixes sont dans `.env.example`.
Le modèle par défaut est multilingue : `Systran/faster-whisper-small`.
Le backend STT reçoit `model=whisper-1`, alias que cette version du serveur traduit vers
`VEXA_WHISPER_MODEL`. Le modèle est téléchargé à la première transcription puis conservé
sur le volume de cache ; un healthcheck HTTP ne garantit pas que ses poids sont déjà chargés.

### Santé et réseau

```bash
docker compose exec vexa python3 -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8056/health', timeout=5).read().decode())"
```

Le healthcheck Compose vérifie également admin-api, meeting-api et runtime.
Les trois services ajoutés n'ont aucun port publié. API/worker communiquent avec Vexa sur
`vexa-internal` (`internal: true`). PostgreSQL Vexa n'a que ce réseau.
Vexa et Whisper ont aussi `vexa-egress` pour joindre Meet et télécharger les modèles.
Un réseau exclusivement `internal: true` empêcherait le bot de rejoindre Google Meet.
Les interfaces et ports supplémentaires inclus dans Lite ne sont pas publiés sur l'hôte.

Les enregistrements audio persistants sont désactivés (`recording_enabled=false` dans chaque
requête bot). Aucun stockage objet n'est ajouté pour cette intégration de transcription.

### GPU optionnel

Sur Linux avec GPU NVIDIA, pilotes compatibles et NVIDIA Container Toolkit installé,
modifier `.env` :

```dotenv
COMPOSE_FILE=docker-compose.yml:docker-compose.vexa-gpu.yml
VEXA_WHISPER_DEVICE=cuda
VEXA_WHISPER_COMPUTE_TYPE=float16
```

Puis utiliser la même commande `docker compose --profile vexa up -d`.
Le fichier complémentaire sélectionne l'image CUDA épinglée et réserve les GPU.
Changer seulement `VEXA_WHISPER_DEVICE` sans changer l'image ne suffit pas.
Docker Desktop sur macOS ne fournit pas cet accès CUDA ; utiliser le mode CPU.

### Ressources

Budgets initiaux à mesurer sur une vraie réunion, pas des garanties de débit :

| Ressource | Budget de départ pour une réunion et Whisper small |
|---|---|
| CPU | 4 cœurs ; davantage si la transcription CPU prend du retard |
| RAM | 8 Go disponibles pour l'ensemble Vexa/Whisper/PostgreSQL, hors frontend et LLM |
| Mémoire partagée | 2 Go configurés pour le navigateur dans Lite |
| Disque | prévoir 15 Go libres pour les images, poids et données ; surveiller les volumes |
| GPU optionnel | prévoir au moins 4 Go de VRAM pour commencer avec small, puis mesurer |

Lite partage son environnement graphique/audio : commencer avec une seule réunion simultanée,
comme le précise la documentation officielle. Ce travail ne promet pas de concurrence multi-bots.
La première utilisation requiert un accès au registre d'images et au dépôt du modèle.

## Client et adaptateur

`vexa/client.py` : client async `httpx`, authentification `X-API-Key`, timeout configurable
(15 s par défaut), deux retries au maximum sur les lectures et l'arrêt idempotent.
Les erreurs réseau/timeouts et HTTP 408/429/500/502/503/504 sont transitoires ; les autres erreurs
HTTP sont propagées immédiatement. Le backoff est borné. Les redirections ne sont pas suivies.
`POST /bots` n'est jamais rejoué automatiquement : un timeout peut cacher un bot déjà créé.
Les réponses sont validées avec Pydantic et les états inconnus sont refusés.
La clé est masquée dans les représentations et sérialisations des paramètres.

`adapters/vexa.py` implémente `CaptureAdapter`. Un identifiant de capture est l'id de
l'enregistrement Vexa, associé localement à sa plateforme et son identifiant natif.
Les lectures utilisent cet id plutôt que la dernière occurrence d'un lien Meet réutilisé.
Chaque réponse est comparée à l'association conservée dans Baraza ; un id inconnu est refusé
avant tout appel HTTP.

| État Vexa | CaptureStatus |
|---|---|
| idle, scheduled, requested, joining, awaiting_admission, needs_help | waiting_admission |
| active, stopping | capturing |
| completed | processing |
| failed | failed |

`stopping` ne prouve pas que la transcription finale est disponible. La fin normale du bot
ou de la réunion est observable comme `completed`. On attend cet état et le transcript final
avant de terminer l'ingestion. L'adaptateur ne produit pas `done` : la génération/validation des
minutes appartient à la suite du pipeline.

Les segments conservent id, temps en secondes, texte, langue, identifiant du locuteur et caractère
final (`completed` → `is_final`). Les noms explicitement fournis sont conservés. Les identifiants
inconnus reçoivent « Speaker 1 », « Speaker 2 », etc., sans deviner leur identité.
Sans identifiant de locuteur, les segments sont regroupés sous un seul locuteur non attribué :
il est impossible de distinguer des personnes à partir de cette absence d'information.
`fetch_transcript` trie les segments et exclut les résultats provisoires.

## Suivi et ingestion

`core/captures.py` orchestre start/stop/poll et réutilise `ingest_segments`.
`storage/captures.py` conserve les associations et les états dans la base Baraza.
Le worker recharge les captures actives depuis SQL après un redémarrage.
Un id de job de polling stable empêche deux sweeps concurrents, même avec plusieurs workers.
La cadence de cinq secondes est une cible ; un sweep long décale le suivant.
Les erreurs HTTP/données invalides sont isolées par capture et n'inventent pas une fin de réunion.
Les logs Baraza de polling contiennent seulement l'id de réunion et le type d'erreur.

Les écritures de segments sont des upserts sur `(meeting_id, segment_id)`.
L'ingestion précède le passage en `processing` ; le changement d'état et la désactivation du suivi
sont dans une même transaction. Un crash entre ingestion et transition peut rejouer les upserts
sans créer de doublons ni de nouvelle transition. `failed` conduit à `error` et arrête le suivi.
Une capture peut passer directement de `pending` à `processing` si le polling n'a pas observé
sa phase active.

Les tâches worker utilisables par la future API #97 sont :

- `start_vexa_capture_task(meeting_id, meeting_url)` : crée un état pending et demande un bot ;
- `stop_vexa_capture_task(meeting_id)` : demande l'arrêt d'une capture active connue ;
- `poll_vexa_captures` : suivi automatique lorsque Vexa est activé.

Exemple depuis le backend, après information/accord des participants :

```python
from arq import create_pool
from arq.connections import RedisSettings
from baraza.config import get_settings

async def start_test_capture():
    redis = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
    try:
        await redis.enqueue_job(
            "start_vexa_capture_task", "unique-baraza-meeting-id",
            "https://meet.google.com/abc-defg-hij",
        )
    finally:
        await redis.aclose()
```

Limites de reprise : SQL et la création du bot distant ne forment pas une transaction distribuée.
Un crash/timeout après la création distante mais avant la persistance du handle exige une
réconciliation manuelle dans Vexa. Aucun second bot n'est créé par un retry automatique.
Le stockage suit le mécanisme `create_all` existant ; son remplacement par des migrations
Alembic reste à effectuer avec le chantier de migrations du dépôt.
La génération des minutes et le passage à `draft_ready` ne sont pas implémentés ici.

## Nom visible et information des participants

Nom par défaut : **Baraza – note taker (transcribing)**, configurable avec
`BARAZA_VEXA_BOT_NAME`, envoyé explicitement dans chaque création de bot.
Le bot rejoint la réunion en tant que participant visible ; la vérification visuelle finale
nécessite une réunion réelle.

La version épinglée **n'implémente pas l'envoi de chat** (`POST /bots/.../chat`) dans son cœur
open source. Aucune requête fictive de notice n'est envoyée.
L'organisateur doit informer les participants avant la capture (dépendance #106), par exemple :
« Baraza transcrit cette réunion pour préparer son compte rendu. Merci de signaler toute opposition
avant de démarrer. » Le parcours de consentement reste dans #106.

## Machine à états #77

`core/meetings.py` est l'unique définition des transitions permises.

| État | Prochains états permis |
|---|---|
| pending | capturing, processing, error |
| capturing | processing, error |
| processing | draft_ready, error |
| draft_ready | validated, error |
| validated | aucun |
| error | pending |

`draft_ready` est la valeur API correspondant au libellé « draft ready ».
Toute autre transition, y compris vers le même état, lève `InvalidMeetingTransition`.
Le polling demande explicitement une opération idempotente pour les états déjà observés.
Chaque création et transition est enregistrée avec un timestamp UTC ; une version optimiste
empêche d'écraser une transition concurrente. Les historiques survivent aux redémarrages.
`error → pending` définit la reprise métier ; démarrer une nouvelle tentative de bot sous le même
id de réunion n'est pas encore exposé par le service de capture.

## Vérification et critères restant à constater en environnement réel

```bash
cd backend
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

Les tests `respx` couvrent le client (authentification, erreurs, retries bornés), les états Vexa,
le contrat réutilisable dans `tests/adapters/contract.py`, les locuteurs inconnus, les segments
provisoires, le refus d'ids inconnus/mismatches, la reprise SQL et une réunion complète finissant
en `processing`. Les 36 couples d'états sont testés pour #77, ainsi que la persistance de l'historique.
Le choix polling implique qu'aucun webhook n'est installé : les appels entrants non signés,
y compris rejoués, reçoivent 404. Il ne s'agit pas d'une implémentation de signature webhook.

Validation locale : **116 tests passent**, Ruff (lint et formatage), mypy et
`uv sync --locked --offline` passent également.

Compose CPU/GPU a été validé avec une copie temporaire de `.env.example`, en contrôlant les
images épinglées, l'absence de ports Vexa publiés et le réseau interne.
Docker n'étant pas démarré sur la machine de développement, les vérifications suivantes restent
manuelles et ne sont pas annoncées comme réussies :

1. Démarrer `docker compose --profile vexa up` et constater le healthcheck vert (#124).
2. Créer une réunion Meet de test, informer les participants, demander le bot et l'admettre.
3. Vérifier son nom visible, l'arrivée de segments et le passage pending → capturing (#128).
4. Arrêter le bot ou terminer la réunion ; vérifier l'ingestion et l'état processing (#126).
5. Redémarrer le worker pendant une réunion et vérifier la reprise du suivi.

## Références officielles vérifiées

- [Images et digests v0.12.26](https://github.com/Vexa-ai/vexa/blob/v0.12.26/releases/v0.12.26/candidate-images.json)
- [Déploiement Lite et limites](https://github.com/Vexa-ai/vexa/blob/v0.12.26/deploy/lite/README.md)
- [API Meetings, états, bots et transcripts](https://github.com/Vexa-ai/vexa/blob/v0.12.26/docs/docs/api/meetings.mdx)
- [Limites des bots interactifs et du chat](https://github.com/Vexa-ai/vexa/blob/v0.12.26/docs/docs/interactive-bots.mdx)
- [Licence Vexa au tag retenu](https://github.com/Vexa-ai/vexa/blob/v0.12.26/LICENSE)
- [Serveur Whisper v0.5.0](https://github.com/fedirz/faster-whisper-server/tree/v0.5.0)
- [Tags Whisper et digests](https://hub.docker.com/r/fedirz/faster-whisper-server/tags)
- [PostgreSQL 17.6-alpine](https://hub.docker.com/_/postgres/tags?name=17.6-alpine)
