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
