# KAKAPO — Scientific Reliability Infrastructure

KAKAPO certifie, relie et score des publications scientifiques via deux briques :
- **KPT (Proof of Knowledge Token)** — certificat cryptographique non transférable
- **Trust Engine** — moteur de scoring de fiabilité scientifique

---

## Prérequis

- Docker + Docker Compose
- Python 3.12+ (pour le développement local sans Docker)

---

## Lancement avec Docker Compose

```bash
# 1. Cloner et entrer dans le projet
git clone <repo>
cd kakapo

# 2. Copier les variables d'environnement
cp .env.example .env

# 3. Lancer PostgreSQL + API
docker compose up --build

# L'API est disponible sur http://localhost:8000
# Documentation interactive : http://localhost:8000/docs
```

---

## Développement local (sans Docker)

```bash
# 1. Créer un environnement virtuel
python -m venv .venv
source .venv/bin/activate  # Windows : .venv\Scripts\activate

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Configurer l'environnement
cp .env.example .env
# Éditer .env avec votre DATABASE_URL PostgreSQL locale

# 4. Lancer l'API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Lancer les tests

```bash
# Depuis la racine du projet (pas besoin de PostgreSQL — SQLite in-memory)
pip install -r requirements.txt
pytest -v
```

Résultat attendu :
```
app/tests/test_publications.py .......... PASSED
app/tests/test_kpt.py ............ PASSED
app/tests/test_trust.py .......... PASSED
```

---

## Endpoints API

### Publications

| Méthode | Route | Description |
|---------|-------|-------------|
| `POST` | `/publications/upload` | Upload PDF + création Publication + KPT + Trust Score |
| `GET` | `/publications/` | Lister les publications (pagination, filtre source) |
| `GET` | `/publications/{id}` | Lire une publication par UUID |

### KPT

| Méthode | Route | Description |
|---------|-------|-------------|
| `POST` | `/kpt/issue` | Émettre un KPT manuellement pour une publication existante |
| `GET` | `/kpt/{kpt_id}` | Lire un KPT par identifiant lisible |
| `POST` | `/kpt/{kpt_id}/verify` | Vérifier l'intégrité et le statut d'un KPT |
| `PATCH` | `/kpt/{kpt_id}/status` | Mettre à jour le statut (challenged / revoked / superseded) |
| `GET` | `/kpt/publication/{pub_id}` | Lister tous les KPT d'une publication |

### Trust Engine

| Méthode | Route | Description |
|---------|-------|-------------|
| `GET` | `/trust/score/{pub_id}` | Lire le dernier score de fiabilité |
| `POST` | `/trust/score/{pub_id}` | Recalculer et persister un nouveau score |
| `GET` | `/trust/history/{pub_id}` | Historique complet des scores |

---

## Exemple de flux complet

```bash
# 1. Uploader un PDF
curl -X POST http://localhost:8000/publications/upload \
  -F "file=@paper.pdf" \
  -F "title=Mon article de recherche" \
  -F "abstract=Résumé de l'article" \
  -F "source=arxiv" \
  -F "doi=10.1234/example.2024.001" \
  -F 'authors_raw=[{"name": "Alice Dupont", "orcid": "0000-0001-2345-6789"}]' \
  -F "institution_raw=Sorbonne Université" \
  -F "submitted_at=2024-01-15T10:00:00" \
  -F 'orcid_authors=["https://orcid.org/0000-0001-2345-6789"]' \
  -F "ror_institution=https://ror.org/02en5vm52"

# Réponse : objet Publication avec id, file_hash, etc.
# Un KPT et un TrustScore sont automatiquement créés.

# 2. Vérifier le KPT
curl http://localhost:8000/kpt/KPT-XXXXXXXX-v1-YYYYYYYY

# 3. Vérifier l'intégrité du fichier
curl -X POST "http://localhost:8000/kpt/KPT-XXXXXXXX-v1-YYYYYYYY/verify?verify_file=true"

# 4. Lire le score de fiabilité
curl http://localhost:8000/trust/score/<publication_id>

# 5. Recalculer le score (après mise à jour des métadonnées)
curl -X POST http://localhost:8000/trust/score/<publication_id>
```

---

## Structure du score Trust Engine V1

| Composante | Poids | Critère |
|------------|-------|---------|
| `source_score` | 20% | hal/arxiv = 1.0 · direct = 0.5 · other = 0.3 |
| `completeness_score` | 30% | Présence : titre, résumé, DOI, auteurs, institution |
| `freshness_score` | 20% | ≤2 ans = 1.0 · décroissance jusqu'à 5 ans = 0.0 |
| `citation_score` | 15% | DOI présent = 1.0 (proxy V1) |
| `dataset_score` | 15% | Dataset hash déclaré = 1.0 |

---

## Variables d'environnement

| Variable | Défaut | Description |
|----------|--------|-------------|
| `DATABASE_URL` | `postgresql://kakapo:kakapo@localhost:5432/kakapo` | URL PostgreSQL |
| `UPLOAD_DIR` | `./uploads` | Répertoire de stockage des fichiers |
| `MAX_UPLOAD_SIZE_MB` | `50` | Taille maximale d'upload en MB |
| `APP_ENV` | `development` | Environnement d'exécution |

---

## Roadmap V2

- [ ] Authentification JWT / API keys
- [ ] Connecteurs HAL et arXiv (import automatique)
- [ ] Graphe inter-publications Neo4j
- [ ] Citation score via OpenAlex / Semantic Scholar
- [ ] Score de reproductibilité (vérification dataset)
- [ ] Score de contradiction (analyse croisée)
- [ ] Worker asynchrone pour traitement lourd (ARQ/Celery)
- [ ] Migrations Alembic
# force deploy Dim 10 mai 2026 00:30:15 CEST

<!-- README v3.2 -->

---

## 17. Frontend deployment workflow

### URL et identifiants

- **URL prod**         : https://oparence-site.vercel.app
- **Project Vercel**   : `prj_CXtGQozH8IPtNTn87VaqAA20fRnp`
- **Team Vercel**      : `team_mlX0NPUpUzXYxRIiSeTEjiVw`
- **Git repo**         : NON CONNECTE (deploiement via Vercel CLI uniquement)
- **Code source local**: `~/Desktop/KAKAPO/oparence-site/`

### Stack technique

- Next.js 16.2.6 (App Router)
- React 19.2.6
- TypeScript 5.4.5
- Tailwind CSS 3.4.3
- Turbopack (bundler par defaut)

### Structure du projet

```
oparence-site/
├── .env.local                              (variables API : NEXT_PUBLIC_API_URL)
├── .vercel/                                (config link Vercel)
├── package.json                            (en racine - IMPERATIF, pas de double-src)
├── next.config.js
├── tailwind.config.ts
├── tsconfig.json
├── public/
└── src/
    ├── app/
    │   ├── page.tsx                        (HomePage)
    │   ├── layout.tsx
    │   ├── demo/page.tsx
    │   ├── graph/page.tsx
    │   ├── kpt/[kpt_id]/page.tsx
    │   ├── publications/page.tsx
    │   ├── publications/[id]/page.tsx
    │   └── verify/page.tsx
    ├── components/
    │   ├── ui/
    │   │   ├── OparenceTerminal.tsx        (widget central live, 4 colonnes)
    │   │   ├── LiveCounter.tsx             (compteurs hero stats)
    │   │   ├── Badge.tsx
    │   │   ├── Card.tsx
    │   │   ├── EmptyState.tsx
    │   │   ├── ErrorState.tsx
    │   │   ├── ScoreBar.tsx
    │   │   ├── ScoreDial.tsx
    │   │   └── Spinner.tsx
    │   ├── layout/
    │   │   ├── Header.tsx
    │   │   └── Footer.tsx
    │   ├── brand/
    │   │   └── OparenceLogo.tsx
    │   ├── kpt/
    │   │   ├── KPTPanel.tsx
    │   │   └── KPTVerifyForm.tsx
    │   ├── publication/
    │   │   ├── PublicationCard.tsx
    │   │   ├── PublicationFilters.tsx
    │   │   └── PublicationMeta.tsx
    │   ├── trust/
    │   │   └── TrustScorePanel.tsx
    │   └── graph/
    │       └── RelationsPanel.tsx
    └── lib/
        ├── api-client.ts
        ├── api.ts
        ├── mock-data.ts
        └── utils.ts
```

### Procedure de deploy

```bash
cd ~/Desktop/KAKAPO/oparence-site
npx vercel --prod --yes
```

Le deploy CLI fait :
1. Build Next.js local (turbopack)
2. Upload bundle a Vercel
3. Deploy production
4. Alias oparence-site.vercel.app

### Recuperation du code source si perdu

Si le dossier local oparence-site est perdu (changement de machine, suppression accidentelle) :

```bash
mkdir -p ~/Desktop/KAKAPO/oparence-site
cd ~/Desktop/KAKAPO/oparence-site
npx vercel link --yes --project oparence-site
python3 ~/kakapo/scripts/download_vercel_source.py
```

Le script `scripts/download_vercel_source.py` utilise l'API Vercel `/v6/deployments/{id}/files` pour reconstituer l'arborescence depuis le deploy READY.

### Endpoints backend consommes par le frontend

| Endpoint                      | Frequence polling | Widget consommateur            |
|-------------------------------|-------------------|--------------------------------|
| `/demo/stream`                | 8 sec             | OparenceTerminal (4 colonnes)  |
| `/demo/integrity/summary`     | 12 sec            | Integrity monitoring (col 4)   |
| `/kakapo/stats`               | 15 sec            | LiveCounter (hero stats)       |
| `/demo/kpt/{kpt_id}`          | a la demande      | Page detail KPT                |

### Schema de reponse /demo/stream

```json
{
  "recent": [
    {
      "type": "publication | trial",
      "ref": "doi or nct_id",
      "label": "source or theme",
      "nct_id": "compat backward",
      "theme": "compat backward",
      "kpt_id": "KPT-XXX",
      "title": "string (60 chars max)",
      "secs_ago": 123
    }
  ],
  "themes": [{"theme": "oncology", "count": 52344, "pct": 34}],
  "themes_total": 153379,
  "sources": [{"source": "pubmed", "count": 3022579, "pct": 95}],
  "catalog_size": 3175343,
  "trials_size": 153379,
  "total_size": 3328722
}
```

---

## 18. Journal - 7 juin 2026 (PHASE A + B frontend)

### Backend

- EPMC ingest patche savepoints + IntegrityError : 0 erreur de cascade, cadence stable ~280-500/min
- Doctrine KPT certifie cryptographique gravee (abandon distinction i-KPT / KPT-Editorial)
- `/demo/stream` etendu :
  - Ajout `sources` (top 10 sources publications avec count + pct)
  - Ajout `themes_total` (somme des themes pour affichage total)
  - Merge CT (5) + publications (5) dans `recent`, tries par recence
  - Nouveaux champs `type`, `ref`, `label` (backward-compatibles avec frontend ancien)

### Frontend

- Code source `oparence-site` recupere via API Vercel `/v6/deployments/{id}/files`
- Structure normalisee : suppression du faux double-src (cause du crash deploy 25 mai)
- `OparenceTerminal.tsx` patche :
  - Renommage widget "Themes distribution" vers "Clinical trials by theme"
  - Ajout total "153 379 essais indexes" sous le widget themes
  - Ajout section "Publications by source" dans Catalog Live counters (6 sources)
  - Differenciation visuelle dans Recent ingestion stream :
    - Publications : glyph diamant copper, border copper
    - Trials      : glyph triangle teal, border teal
  - Footer mis a jour : Spec v1.1 KPT certifie cryptographique
- 2 deploys production sans erreur (Build 8s + 10s, Ready 23s + 24s)

### Pitch impact

- Le stream "LIVE" affiche maintenant de vraies ingestions actives (EPMC en 1-2 min)
- Le total 3,3M+ KPTs explicitement decompose par source
- Le widget themes ne pretend plus etre exhaustif sur les 3M publis (label clarifie)
- Footer doctrine aligne sur la realite technique du systeme

---

## 19. Etat horodate - 7 juin 2026 ~13h CET

### Volumes

- Publications totales      : 3,175,343
- Clinical trials totales   : 153,379
- Total KPTs                : 3,328,722

### Distribution par source

| Source       | Count       | Pct  | Fingerprint coverage |
|--------------|-------------|------|----------------------|
| pubmed       | 3,022,579   | 95%  | 100%                 |
| hal          | 80,829      | 3%   | 100%                 |
| europepmc    | 65,720+     | 2%   | 100% (a l'ingestion) |
| openalex     | 6,184       | 0%   | 100%                 |
| arxiv        | 27          | 0%   | 100%                 |
| direct       | 3           | 0%   | 100%                 |
| nature       | 1           | 0%   | 100%                 |

### Distribution themes (clinical trials uniquement)

| Theme           | Count   | Pct |
|-----------------|---------|-----|
| oncology        | 52,344  | 34% |
| drug_discovery  | 34,373  | 22% |
| metabolic       | 26,935  | 18% |
| neurology       | 23,735  | 15% |
| cardiology      | 14,362  | 9%  |
| ai_compliance   | 1,630   | 1%  |

### Integrity monitoring

- Publications verified : 3,155,356 / 3,175,429 (99.4%)
- Clinical trials verified : 153,379 / 153,379 (100%)
- Altered detected : 27
- Retractions tracked : 0

### Process actifs sur EC2 i-0ac3b07c48c308523 (t3.2xlarge, ip-172-31-29-156)

| PID    | Process                       | Cadence              | Log                              |
|--------|-------------------------------|----------------------|----------------------------------|
| 149902 | Daemon monitoring             | 1 cycle / heure      | ~/integrity_daemon.log           |
| 151110 | Backfill loop publications    | 5 min entre cycles   | ~/backfill_pub_loop.log          |
| 159842 | EPMC massive (12 workers)     | ~280-500 publis/min  | ~/ingest_epmc_massive.log        |

### Backlog non-bloquant

- [BL01] Stream backend lit publications.created_at, pas ingested_at (coherence a valider)
- [BL02] PHASE C (classification 13 themes sur 3M publis) : reportee a une session dediee
- [BL03] Init repo Git pour oparence-site (actuellement non versionne)
- [BL04] Documenter procedure de rollback frontend (Vercel rollback CLI)
