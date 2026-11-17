# Baraza — Bilan des travaux de Thierry, sprints 01 à 04

**Responsable :** Thierry — backend et capture Vexa  
**Date du bilan :** 10 novembre 2026  
**Périmètre :** intégration Vexa, contrôle des captures, états des réunions,
persistance et comptes rendus versionnés.

## 1. Objectif de mes contributions

J’ai construit puis consolidé la partie backend qui permet à Baraza de demander
un bot Google Meet, suivre la capture, récupérer les segments de transcription
et conserver les états de la réunion. J’ai ensuite ajouté les fondations de base
de données et le stockage des comptes rendus, avec historique des modifications
et validation explicite.

Ces travaux s’intègrent aux autres contributions de l’équipe : format commun et
ingestion des segments, interface de démonstration et génération IA. L’ingestion
existante est réutilisée ; le développement de l’interface et du générateur IA
ne constitue pas mon livrable dans ce bilan.

Le bilan distingue trois niveaux :

- **Réalisé dans le code** : fonctionnalité présente dans le dépôt local.
- **Vérifié localement** : comportement contrôlé par les tests ou les commandes indiquées.
- **À confirmer en environnement réel** : vérification nécessitant Docker opérationnel,
  PostgreSQL/Redis ou une réunion Google Meet autorisée.

## 2. Vue d’ensemble des quatre sprints

| Sprint | Objectif de mon travail | Principaux livrables |
|---|---|---|
| 01 | Préparer le socle Vexa | Profil Docker facultatif, client API, adaptateur, suivi des captures, états et tests simulés |
| 02 | Rendre la capture contrôlable depuis le backend | API de démarrage, suivi et arrêt ; protection contre les doublons ; erreurs HTTP explicites |
| 03 | Stabiliser le raccordement au frontend | Contrat `/captures`, identifiant local commun, CORS, paramètres de construction du frontend, vérifications Docker |
| 04 | Structurer la persistance et les comptes rendus | Sessions asynchrones, migrations Alembic, modèles de comptes rendus et révisions, verrouillage de version, tests d’intégration |

Cette répartition décrit les étapes de réalisation et de consolidation. Certaines
issues, notamment #126, #127 et #77, traversent plusieurs sprints : leur présence
dans plusieurs étapes ne signifie pas qu’elles ont été développées plusieurs fois.

## 3. Sprint 01 — Socle backend et intégration Vexa

**Issues de référence :** #124, #125, #126, #127, #128 et #77.

Le socle est identifié dans le commit local `3b8ef53`, intitulé
« Feat: Configuration Vexa AI », présent sur `thierry-sprint01`.

### Environnement Docker facultatif — #124

J’ai ajouté un profil Compose `vexa`, activé explicitement, qui regroupe Vexa Lite,
son PostgreSQL et un serveur Whisper local. Les images sont épinglées par version
et empreinte SHA-256 pour rendre leur sélection reproductible.

La configuration prévoit :

- Vexa Lite `v0.12.26`, utilisé à partir de son image officielle ;
- Whisper CPU, avec une configuration GPU complémentaire pour Linux/NVIDIA ;
- les variables de configuration dans `.env.example` : modèle, appareil de calcul,
  clé API et nom du bot ;
- un réseau interne pour les échanges entre services, sans port Vexa publié ;
- un réseau de sortie pour rejoindre Meet et télécharger les modèles Whisper ;
- des contrôles de santé et une documentation des ressources nécessaires.

La base de données de Vexa est séparée de celle de Baraza. Les enregistrements
audio persistants sont désactivés dans les demandes de bot.

### Client API et adaptateur — #125 et #126

J’ai implémenté un client asynchrone `httpx` pour demander un bot, l’arrêter,
consulter son état et récupérer sa transcription. Il utilise une clé API,
des délais d’attente configurables et des modèles de réponse Pydantic.

Les lectures et demandes d’arrêt peuvent être réessayées sur certaines erreurs
temporaires. La création d’un bot n’est pas rejouée automatiquement : après un
délai d’attente dépassé, le bot peut déjà avoir été créé chez Vexa.

`VexaAdapter` traduit les réponses dans le contrat commun `CaptureAdapter`.
Il gère notamment l’attente d’admission et convertit les segments en conservant
leurs identifiants, horodatages, textes, langues et informations de locuteur.
Les locuteurs sans nom reçoivent des libellés `Speaker N`, sans déduction d’identité.

### Suivi des captures et états — #127 et #77

J’ai retenu le **polling authentifié** : le worker interroge Vexa à une cadence
cible de cinq secondes à partir des identifiants conservés par Baraza. Chaque
réponse est vérifiée pour éviter de traiter les données d’une autre capture.

Il n’existe pas de route webhook Vexa entrante. Les tests vérifient que des appels
non signés, y compris répétés, à cette route absente reçoivent une réponse 404.
Ce résultat vérifie l’absence de cette entrée HTTP ; il ne constitue pas une
implémentation de vérification de signature webhook.

Les états métier et les transitions autorisées sont définis dans un seul module.
Les transitions interdites provoquent une erreur explicite ; les transitions
effectuées sont conservées avec leur date UTC et un contrôle de concurrence.

### Identification du bot — #128

Le nom du bot est configurable. Sa valeur par défaut est
**« Baraza – note taker (transcribing) »** et elle est envoyée à Vexa lors de sa création.
L’affichage réel dans Google Meet reste à vérifier. L’information préalable des
participants relève du parcours #106 ; l’envoi d’une notice par chat n’est pas
implémenté dans le cœur open source de la version Vexa retenue, selon la documentation
technique de l’intégration.

## 4. Sprint 02 — API de contrôle des captures

**Issues de référence :** #126, #127, #128 et #77 ; raccordement nécessaire à l’API de capture.

J’ai vérifié le socle existant, puis ajouté des routes HTTP permettant de lancer,
suivre et arrêter une capture à partir d’un identifiant de réunion fourni par l’appelant.

| Action | Route |
|---|---|
| Demander une capture | `POST /meetings/{meeting_id}/capture` |
| Consulter l’état et l’historique | `GET /meetings/{meeting_id}/status` |
| Demander l’arrêt | `POST /meetings/{meeting_id}/capture/stop` |

Ces routes s’appuient sur le service de capture et le stockage existants.
La lecture des segments utilise l’API d’ingestion déjà présente :
`GET /meetings/{meeting_id}/segments`.

J’ai ajouté les contrôles suivants :

- refus d’un second démarrage sous le même identifiant avant toute nouvelle demande de bot ;
- validation du lien Google Meet avant la création de la réunion ;
- erreur explicite si Vexa est désactivé ou non configuré ;
- réponses d’erreur qui n’exposent pas les détails renvoyés par le service distant ;
- lecture de l’état persistant et de l’historique horodaté.

Une demande d’arrêt acceptée ne suffit pas à déclarer la réunion terminée.
Le worker attend la transcription finale, l’ingère, puis enregistre `processing`.
Les tests couvrent ce parcours complet avec une API Vexa simulée.

## 5. Sprint 03 — Stabilisation pour l’intégration MVP Core

**Issues de référence :** #124 à #127, #77 et #128.

### Contrat utilisable par le frontend

J’ai constaté que le frontend appelait `/captures`, alors que les routes du
sprint 02 utilisaient `/meetings/{id}/capture`. J’ai ajouté les routes compatibles :

| Action | Route |
|---|---|
| Créer une capture avec un identifiant local généré | `POST /captures` |
| Lire son état | `GET /captures/{capture_id}` |
| Demander son arrêt | `POST /captures/{capture_id}/stop` |

Dans ce contrat, `capture_id` est l’UUID local de la réunion. Le frontend peut
utiliser cet identifiant pour consulter les segments et le compte rendu.
L’identifiant distant du bot Vexa reste associé à cette réunion dans le stockage.

La route historique `POST /meetings/{meeting_id}/capture` conserve son contrat :
elle renvoie l’identifiant distant. Ses appelants doivent donc conserver leur
`meeting_id` local pour les lectures dans Baraza.

### Corrections de configuration et de comportement

J’ai ajouté les origines navigateur autorisées via `BARAZA_CORS_ORIGINS` et transmis
les paramètres `NEXT_PUBLIC_API_URL` et `NEXT_PUBLIC_USE_MOCK_API` à la construction
Docker du frontend. Une modification de ces paramètres demande sa reconstruction.

J’ai également corrigé le suivi : un bot actif passe en `capturing` même si la
première lecture de transcription échoue ou arrive en retard. La capture reste
suivie pour une prochaine tentative. Les noms de bot vides sont désormais refusés.

### Vérifications du profil Docker

J’ai ajouté `backend/scripts/check_vexa.py` pour vérifier les images épinglées,
les réseaux, les contrôles de santé et l’absence de ports publiés. Ces vérifications
de configuration CPU/GPU sont intégrées à la CI. Le script propose aussi un
démarrage réel et des sondes de santé, avec un contrôle préalable d’espace disque.

Un démarrage a été tenté dans un projet Docker isolé. L’extraction des images a
échoué avec une erreur d’entrée/sortie alors que l’espace libre était d’environ
117 Mio. Aucun résultat de santé Vexa réussi n’a été obtenu. Aucun lien Meet de
test n’était disponible pour vérifier le bot en réunion.

## 6. Sprint 04 — Base de données, migrations et comptes rendus

**Issues de référence :** #50, #51 et #53 ; maintien des tests de #126, #127 et #77.
Les prérequis de tests PostgreSQL/Redis de #49 ont également été ajoutés.

### Sessions asynchrones et cycle de vie — #50

J’ai créé le module `baraza/db/` avec une base déclarative commune et des
conventions de nommage des contraintes. L’API et le worker disposent d’un moteur
asynchrone par processus, libéré à l’arrêt.

La dépendance FastAPI `get_session`, exposée par `SessionDep`, fournit une session
transactionnelle : les écritures sont validées avant l’envoi de la réponse et
annulées en cas d’exception. Les routes de capture et de segments utilisent le
moteur partagé au lieu de créer leurs propres pools de connexion.

### Migrations Alembic — #51

J’ai remplacé la création des tables à la demande par deux migrations :

1. `0001_capture_baseline` : réunions, associations avec les bots Vexa et segments.
2. `0002_minutes_versions` : comptes rendus et historique des révisions.

Le service Compose `migrate` exécute `alembic upgrade head` avant le démarrage de
l’API et du worker. La CI est configurée pour appliquer les migrations, puis lancer
`alembic check` afin de détecter un modèle modifié sans migration correspondante.

Les bases anciennes créées sans Alembic nécessitent une procédure d’adoption
après inspection et sauvegarde. La migration initiale ne masque pas automatiquement
une différence de schéma en déclarant la base à jour.

### Comptes rendus et révisions — #53

J’ai ajouté les tables `minutes` et `minutes_revisions` ainsi que `MinutesService`.
Le document courant conserve son contenu au format du schéma `Minutes`, son état
`draft` ou `validated`, le modèle de document, le nom du modèle IA, la version du
prompt, son numéro de version et les informations de validation.

Sur PostgreSQL, le contenu est stocké en JSONB. Les tests rapides utilisent JSON
sur SQLite. Chaque version sauvegardée, y compris la génération initiale et la
validation, conserve son contenu, son auteur, sa date UTC et sa provenance.

Le service permet de créer un brouillon, enregistrer une correction, valider,
consulter le document et lire ses révisions. Il impose :

- un contrôle de version pour refuser l’écrasement d’une modification concurrente ;
- l’interdiction de modifier un compte rendu déjà validé ;
- une transaction commune pour le document, sa révision et la transition de réunion ;
- le passage de `processing` à `draft_ready` à la création du brouillon,
  puis de `draft_ready` à `validated` lors de la validation.

J’ai aussi ajouté `GET /meetings/{meeting_id}/minutes`, qui renvoie le contenu
attendu par le frontend avec un en-tête `ETag` indiquant sa version.
L’appel du service depuis la tâche de génération IA reste à intégrer.

### Infrastructure de tests d’intégration

Le fichier `docker-compose.test.yml` fournit PostgreSQL et Redis sur des ports
locaux distincts. Les tests PostgreSQL créent une base temporaire par session de
test. Les fixtures transactionnelles annulent les écritures de chaque test ; les
scénarios de concurrence utilisent des sessions indépendantes dans cette base jetable.

Six tests d’intégration sont prévus : connexion PostgreSQL avec `SELECT 1`, JSONB
et cohérence des migrations, cycle de vie du compte rendu, concurrence entre
éditeurs, capture Vexa simulée sur PostgreSQL avec rejeu, et connexion Redis.

## 7. États de réunion et correspondance avec le frontend

| État métier | Signification | Transitions autorisées |
|---|---|---|
| `pending` | Capture en attente | `capturing`, `processing`, `error` |
| `capturing` | Capture en cours | `processing`, `error` |
| `processing` | Transcription ingérée, traitement à poursuivre | `draft_ready`, `error` |
| `draft_ready` | Brouillon du compte rendu disponible | `validated`, `error` |
| `validated` | Compte rendu explicitement validé | Aucune |
| `error` | Échec du traitement | `pending` |

Le passage direct de `pending` à `processing` permet de traiter une réunion dont
le polling n’a pas observé la phase active. Le retour de `error` à `pending` est
défini dans la machine à états ; une relance complète sous le même identifiant
n’est pas encore exposée par l’API de capture.

L’API `/captures/{id}` conserve deux champs : `meeting_status` pour l’état métier
et `status` pour le contrat de capture du frontend. Les correspondances sont :
`pending` → `waiting_admission`, `error` → `failed`, et
`draft_ready` ou `validated` → `done`. Les états `capturing` et `processing`
conservent leur nom. **`done` ne prouve donc pas une validation humaine** :
il faut lire `meeting_status` pour la distinguer de la disponibilité du brouillon.

## 8. Vérifications effectuées

Les résultats suivants sont les vérifications consignées aux différentes étapes,
sur l’ensemble de la suite backend de chaque étape, et non des tests tous attribuables
à mes seules contributions.

| Étape | Résultat local consigné | Portée |
|---|---|---|
| Socle / sprint 01 | 116 tests réussis | Client et adaptateur simulés, états, ingestion et reprise |
| Sprint 02 | 120 tests réussis | Ajout du parcours HTTP de contrôle |
| Sprint 03 | 133 tests réussis | Contrat frontend, CORS, retard du transcript et nom du bot |
| Sprint 04 | 145 tests réussis, 6 ignorés | Sessions, migrations, versions et immutabilité ; services réels indisponibles |

Ruff, le contrôle de formatage et mypy ont réussi lors des dernières vérifications.
Les configurations Compose CPU/GPU ont été contrôlées. Les commandes Alembic de
montée, descente puis remontée ont réussi sur SQLite, de même que la détection
d’un changement de modèle non migré. Le SQL PostgreSQL généré hors connexion
contient les colonnes JSONB attendues.

Ces résultats ne valident pas une connexion PostgreSQL réelle, un healthcheck
Vexa réussi ou un parcours complet Google Meet → IA → interface. La CI est
configurée pour les tests de services réels ; aucune exécution distante réussie
n’a été constatée dans le cadre de ce travail local.

## 9. État actuel et validations restantes

| Sujet | État constaté | Suite nécessaire |
|---|---|---|
| Client Vexa et adaptateur | Implémentés et testés avec réponses simulées | Vérifier sur une réunion autorisée |
| Polling et états | Tests locaux réussis, dont les 36 couples d’états | Confirmer le suivi réel et la reprise du worker |
| Nom du bot | Configurable, envoyé dans la requête, noms vides refusés | Contrôler visuellement dans Meet |
| Vexa dans Compose | Configuration vérifiée ; démarrage tenté en échec | Préparer l’espace disque et obtenir les services sains |
| Sessions et migrations | Implémentées et testées localement sur SQLite | Exécuter les tests PostgreSQL et le démarrage Compose sur base vide |
| Comptes rendus versionnés | Service et tests locaux opérationnels | Brancher le pipeline IA et les intégrations d’édition/validation |
| Modèle Meeting complet — #52 | Dépendance distincte encore incomplète | Intégrer métadonnées, modèle UUID, transcript et participants |
| Information des participants — #106 | Dépendance distincte | Assurer l’information et l’accord avant la capture |

Après l’échec d’extraction des images, Docker est resté sans réponse et une
tentative de redémarrage limitée dans le temps a échoué. Aucun nettoyage des
données Docker d’autres projets n’a été effectué. Aucun lien Meet actuel n’a
été fourni pour une validation réelle.

Les branches locales sont nommées `thierry-sprint01`, `thierry-sprint02`,
`thierry-sprint03` et `thierry-sprint04`. Au moment de ce bilan, les évolutions des
sprints 02 à 04 sont présentes dans l’arbre de travail de `thierry-sprint04`,
sans commits distincts pour ces étapes. Elles n’ont pas été publiées par ce travail.
Les noms de branches ne constituent pas une preuve de fusion ou de revue.

## 10. Reprendre les vérifications

Depuis le dossier `backend`, les contrôles rapides sont :

```bash
uv run pytest -m 'not integration'
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```

Sur un environnement configuré, les migrations se vérifient avec :

```bash
uv run alembic upgrade head
uv run alembic check
```

Les procédures de tests PostgreSQL/Redis et de démarrage Vexa sont détaillées
dans les documents ci-dessous. Une fois ces services disponibles, il faudra
effectuer une réunion de test autorisée, constater les segments et les transitions,
puis vérifier l’intégration de la génération et de la consultation du compte rendu.

## 11. Références dans le dépôt

- [Configuration Vexa et cycle de vie des réunions](vexa-backend.md).
- [Contrat HTTP du sprint 02](sprint02-capture-api.md).
- [Livrable technique du sprint 03](sprint03-thierry.md).
- [Sessions, migrations et comptes rendus du sprint 04](sprint04-thierry.md).
- [Décision d’architecture Vexa](decisions/0001-capture-approach-vexa.md).
- [Client Vexa](../backend/src/baraza/vexa/client.py) et [adaptateur](../backend/src/baraza/adapters/vexa.py).
- [Machine à états](../backend/src/baraza/core/meetings.py).
- [Service des comptes rendus versionnés](../backend/src/baraza/core/minute_versions.py).
- [Migrations Alembic](../backend/alembic/) et [tests d’intégration](../backend/tests/integration/).
