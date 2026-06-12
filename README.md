# Oparence — Backend & Infrastructure

> Trust layer pour les IA en secteurs régulés.
> Tiers neutre certificateur. Modèle Spotify-de-la-science.

---

## 1. Vision & Mission

Oparence est l'infrastructure de provenance scientifique pour les IA verticales en secteurs régulés (santé, pharma, legal, finance).

**Le problème** : les IA verticales ne peuvent pas garantir elles-mêmes la provenance des sources scientifiques qu'elles utilisent, même avec licenses éditeurs (problème "juge et partie"). EU AI Act et régulateurs sectoriels exigent un audit trail opposable.

**La solution** : tiers neutre certificateur. Oparence stocke les publications scientifiques (metadata + MeSH + abstract), génère un fingerprint cryptographique multi-zone v1.1, émet un KPT (Knowledge Provenance Token) signé. Les IA streament via API Oparence avec audit trail opposable et détection automatique d'altération/rétraction.

**Modèle économique** : Spotify-de-la-science. Stockage de tout ce qui est légal (PubMed metadata domaine public, PMC OA, bioRxiv, arXiv), pay-per-stream certifié, royalties bilatérales aux éditeurs post-seed.

---

## 2. Architecture technique

### 2.1 Stack
- **Backend** : FastAPI, SQLAlchemy 2.0, Pydantic v2, PostgreSQL 16 (Railway)
- **Frontend** : Next.js 14 App Router, TypeScript, Tailwind CSS
- **Infrastructure** : EC2 t3.2xlarge (ingestion + workers), Railway (DB prod + backend API), Vercel (frontend)
- **Crypto** : Ed25519, X.509, SHA-256, fingerprint multi-zone v1.1

### 2.2 Souveraineté
Phase actuelle : AWS (EC2) + Railway + Vercel + GitHub = juridiction US.
Phase post-seed : migration OVH (DB + workers EU souverain).
Phase post-Series A : SecNumCloud certification.

### 2.3 Stockage
- Railway PostgreSQL 1 TB (DB prod)
- EC2 i-0ac3b07c48c308523 (workers ingestion + scripts bulk)
- Scripts persistants : `/home/ubuntu/`

---

## 3. Doctrine KPT & Fingerprint v1.1

### 3.1 KPT (Knowledge Provenance Token)

Identifiant cryptographique unique par publication, format lisible :
- `KPT-{HASH8}-PUBMED-PMID{pmid}` (PubMed)
- `KPT-{HASH8}-EPMC-PMC{pmcid}` (EuropePMC)
- `KPT-{HASH8}-HAL-{halid}` (HAL)
- `KPT-{HASH8}-CT-{nctid}` (Clinical Trials)

Table `kpts` :
- `id` (uuid) - clé primaire interne
- `kpt_id` (varchar) - identifiant lisible
- `publication_id` (uuid) - FK publications.id (CASCADE)
- `content_hash` (varchar) - SHA-256 du contenu certifié
- `version` (int) - version du KPT (1 = initial)
- `status` (varchar) - 'active', 'retracted', 'altered'
- `issued_at` (timestamptz) - date émission KPT
- `metadata_json` (jsonb) - metadata étendues
- `is_indexed` (bool) - flag indexation OS

### 3.2 Fingerprint multi-zone v1.1

5 zones SHA-256 indépendantes + 1 canonique :
- `fp_identity` = sha256(DOI + titre + auteurs + journal)
- `fp_metadata` = sha256(titre + auteurs + journal + année)
- `fp_content` = sha256(abstract + titre)
- `fp_references` = sha256(références citées)
- `fp_canonical` = sha256(fp_identity + fp_metadata + fp_content + fp_references)

Compléments :
- `fp_content_length`, `fp_word_count` (statistiques contenu)
- `fp_first_sentence`, `fp_last_sentence` (hash sentinelles)
- `fp_computed_at` (timestamptz), `fp_spec_version` = 'v1.1'

Spec version v1.1 ratifiée le 6 juin 2026.

---

## 4. Sources de données certifiées

### 4.1 Sources actives

| Source | Volume | Légal | Couverture |
|--------|--------|-------|------------|
| PubMed | 36.6M (bulk en cours 8 juin 2026) | Domaine public NLM | Métadonnées + MeSH 100% + abstract 51% |
| EuropePMC | 113K | Open Access | Métadonnées + abstract |
| HAL | 80K | CC0 | Métadonnées HAL + plein texte HAL OA |
| OpenAlex | 6K | Open Access | Métadonnées étendues |
| arXiv | 27 | Open Access | Préprints physique/info |
| ClinicalTrials.gov | 153K | Domaine public | Essais cliniques complets |

### 4.2 Sources cibles roadmap
- PMC OA Subset (6.5M full text gratuits) - phase J+7
- bioRxiv + medRxiv (500K preprints) - phase J+15
- PLOS + BMC + Frontiers (2M OA) - phase J+30
- Bilateral deals Elsevier/Wiley/Springer - phase post-seed

---

## 5. État DB actuel (snapshot 8 juin 2026 21:17 UTC)

### 5.1 Tables principales
- **publications** : 3,254,179 rows (avant fin bulk PubMed)
  - `kpt_status='certified'` ou NULL : 402,357 (vraies publications utiles)
  - `kpt_status='shell'` : 400,000 (coquilles marquées, exclues backend)
  - reste : ~2.4M coquilles non marquées (exclues par regex backend)
- **kpts** : 3,223,916 rows (avant fin bulk)
- **clinical_trials** : 153,379 essais complets
- **scientific_reviews** : 0 (table jeune)
- **vo_transactions** : 0 (table jeune, à activer post-seed)

### 5.2 Index critiques
- `uq_publications_pmid` : UNIQUE WHERE pmid IS NOT NULL (ajouté 8 juin 2026 19:18 UTC)
- `uq_publication_doi_active` : UNIQUE sur DOI actif (existant)
- Index B-tree sur source, kpt_status, fp_spec_version

### 5.3 Foreign keys
- `kpts.publication_id` → publications (CASCADE)
- `publication_relations.source_id` → publications (CASCADE)
- `scientific_reviews.publication_id` → publications (NO ACTION)
- `trust_scores.publication_id` → publications (CASCADE)
- `vo_transactions.publication_id` → publications (NO ACTION)

---

## 6. Catalog public (post-patch shells 8 juin 2026)

Patch backend `/demo/stream` et stats sources : exclusion des coquilles via regex SQL.

Catalog visible en prod (avant fin bulk PubMed) :
- Catalog size : 646,999
- Trials size : 153,379
- Total size : 800,378

Sources :
- pubmed 446,164 (69%)
- europepmc 113,791 (18%)
- hal 80,829 (12%)
- openalex 6,184 (1%)
- arxiv 27, direct 3, nature 1

Catalog visible attendu APRÈS fin bulk PubMed v4 :
- Catalog size : ~36,600,000 + 446,164 existants
- Total certifié : ~37M

---

## 7. Bulk PubMed v4 (8 juin 2026)

### 7.1 Architecture script `bulk_pubmed_ingest_v4.py`

Stratégie validée :
1. SELECT tous les DOI existants en RAM au démarrage (~2.5M DOIs, 50 MB)
2. Stream download fichier baseline NCBI (HTTP)
3. Gzip decompress + iterparse lxml
4. Filter Python : skip si DOI déjà en RAM (set lookup O(1))
5. Calcul fingerprint v1.1 multi-zone par publication
6. INSERT batch execute_values 1000 lignes/cmd avec template explicite
7. RETURNING id pour mapping pub_id → pmid
8. INSERT KPTs batch execute_values associés
9. Commit, batch suivant

### 7.2 Schéma INSERT publications
25 colonnes : id, pmid, title, abstract, doi, source, source_origin, hal_id, authors_raw, institution_raw, submitted_at, kpt_status, mesh_terms_json, keywords_json, fp_identity, fp_metadata, fp_content, fp_references, fp_canonical, fp_content_length, fp_word_count, fp_first_sentence, fp_last_sentence, fp_computed_at, fp_spec_version

### 7.3 Schéma INSERT KPTs
8 colonnes : id (uuid), kpt_id (string lisible), publication_id (FK), content_hash, version=1, status='active', issued_at=now(), is_indexed=false

### 7.4 Performance validée (test 8 juin 2026 21:09 UTC)
- 1 fichier (30K publis) en 109.8s
- Cadence : 273 publis/sec
- Inserted 27,295 + Skipped 2,307 (DOI déjà existants)

### 7.5 Lancement 8 workers nohup (8 juin 2026 21:17 UTC)
- W1 : files 2-153 (PID 176438)
- W2 : files 154-305 (PID 176440)
- W3 : files 306-457 (PID 176442)
- W4 : files 458-609 (PID 176444)
- W5 : files 610-762 (PID 176446)
- W6 : files 763-915 (PID 176448)
- W7 : files 916-1067 (PID 176450)
- W8 : files 1068-1220 (PID 176452)

ETA : 5-8h (fin attendue 2h-5h CET du 9 juin 2026)
Cible finale : +36.6M publications + 36.6M KPTs PUBMED

---

## 8. Frontend (oparence-site.vercel.app)

### 8.1 Architecture
- Next.js 14 App Router + TypeScript + Tailwind
- Pas de bibliothèque de composants tierces (esthétique scientifique dark)
- Mock data fallback (lib/mock-data.ts) si API Railway down

### 8.2 Pages clés
- `/` : OparenceTerminal (widget live catalog + sources + themes)
- Polling /demo/stream toutes les 8 sec
- Polling /demo/integrity/summary toutes les 12 sec

### 8.3 Phases livrées 8 juin 2026
- Phase A matin : renommage themes + sources widget
- Phase B matin : stream live merge CT/publi + diff visuelle


---

## 9. Backend Railway (kakapo-back-production.up.railway.app)

### 9.1 Endpoints critiques
- GET `/demo/stream` : catalog size + sources + recent
- GET `/demo/integrity/summary` : stats fingerprints + KPTs
- GET `/demo/health` : statut système (ready_for_demo)

### 9.2 Patch shell exclusion (8 juin 2026 ~16h CET)
Modification `app/routers/demo.py` :
- Catalog count : ajout WHERE `(kpt_status IS NULL OR kpt_status != 'shell')` AND NOT (regex coquille)
- Sources stats : même exclusion sur le GROUP BY source

Effet : catalog public passe de 3,175,343 à 646,999 (honnête).

---

## 10. Daemons & Workers actifs (8 juin 2026)

### 10.1 Backfill loop fingerprints publications
- Script : `~/backfill_pub_fingerprints.py`
- Wrapper : `while true; do timeout 600 python3 ...; sleep 60; done`
- Rôle : recalcul fingerprints v1.1 pour publications EPMC/HAL
- État : KILLED pendant bulk PubMed (à relancer post-bulk si besoin)

### 10.2 Daemon monitoring intégrité
- Script inline Python en boucle
- PID 173096 actif depuis 18:51 UTC
- Rôle : recrawl_batch toutes les heures (re-fetch + comparaison fp)
- Détecte altérations + rétractations en temps réel

### 10.3 Bulk PubMed v4 (en cours)
- 8 workers PIDs 176438-176452
- Logs : `~/bulk_pubmed_v4_W*.log`

---

## 11. Journal des sessions

### 8 juin 2026 — Bulk PubMed + Patch shells

**Matin (Phase frontend)**
- 09:00-11:00 : Phase A frontend (renommage themes, sources widget Phase B)
- 11:00-12:00 : Documentation README v3.2

**Après-midi (Audit + patch backend)**
- 14:00-15:00 : Découverte du bug "coquilles PubMed" (audit 100 échantillons)
  - 83% titres format "Journal PMCxxx" (extraction ratée mai 2026)
  - 0% MeSH sur 3M PubMed avant correction
- 15:00-16:00 : Tentatives DELETE coquilles (2.6M rows, FK CASCADE)
  - DELETE batch 50K échec (20 min sans 1 row commit sur Railway)
  - UPDATE kpt_status='shell' partiel (400K marquées)
- 16:00-16:30 : DÉCISION pivot vers patch backend
  - Modification /demo/stream et sources avec exclusion regex
  - Commit + push Railway auto-deploy
  - Catalog visible : 3.2M à 647K (honnête)

**Soir (Bulk PubMed v4)**
- 18:00-19:00 : Définition modèle Spotify-de-la-science
  - Tiers neutre certificateur (résout "juge et partie")
  - Stockage de tout ce qui est légal
  - Pay-per-stream certifié, royalties éditeurs
- 19:00-19:30 : Migration DB préparatoire
  - ALTER TABLE publications ADD COLUMN pmid BIGINT
  - CREATE UNIQUE INDEX uq_publications_pmid
- 19:30-21:00 : 3 tentatives échec scripts bulk (v1, v2, v3)
  - v1 : ORM SQLAlchemy + begin_nested (trop lent Railway)
  - v2 : psycopg2 execute_values atomic (FK violation DOI)
  - v3 : pre-filter DOI RAM + savepoints par row (tuple index OOB)
- 21:09 : Script v4 réécriture COMPLETE
  - parse_article retourne dict {pub_id, pmid, doi, row}
  - flush_batch() unique pour pub + kpt
  - templates explicites execute_values
  - try/except global parse + flush
- 21:11 : TEST v4 réussi (27,295 publis insérées + KPTs en 1.8 min)
- 21:17 : Lancement 8 workers nohup pour la nuit

### 6 juin 2026 — Spec v1.1 fingerprint
- Ratification fingerprint multi-zone v1.1
- Migration backfill EPMC + HAL

### Mai 2026 — Ingestion massive PubMed v0 (bug retrospectif)
- Script PubMed v0 esearch minimaliste sans efetch détaillé
- Résultat : 3M publis "coquilles" titres bidonnés
- Bug corrigé via patch backend 8 juin 2026


---

## 12. Backlog priorité

### Priorité 1 (post-bulk 9 juin matin)
- [ ] Verifier 8 workers ont fini (~36.6M publis ingérées)
- [ ] Snapshot DB final
- [ ] Validation frontend en prod (catalog ~37M)
- [ ] Update README section 11 (journal post-bulk)

### Priorité 2 (semaine 9 juin)
- [ ] PMC OA Subset full text (6.5M articles gratuits)
- [ ] LinkedIn post fierté catalog
- [ ] Cédric visio démo + ticket angel
- [ ] Mails Doctrine, Predictice, Mistral, Cohere

### Priorité 3 (semaine 16 juin)
- [ ] bioRxiv + medRxiv preprints
- [ ] PLOS + BMC + Frontiers OA
- [ ] Embeddings vectoriels (RAG sémantique)
- [ ] Trust scores enrichis multi-signal

### Priorité 4 (post-seed)
- [ ] Migration OVH (DB + workers)
- [ ] Deals bilatéraux Elsevier/Wiley/Springer
- [ ] SOC 2 + ISO 27001 audit
- [ ] Embauches : senior backend, BD enterprise, legal/compliance, CSM

---

## 13. Sécurité & conformité

- Aucun secret en clair dans le repo (.env gitignored)
- DATABASE_URL Railway en env vars uniquement
- HTTPS partout (Vercel + Railway)
- EU AI Act : audit trail opposable via KPT + fingerprints v1.1
- GPAI Code of Practice : compatibility tracée
- C2PA-ready (extension future signature contenus)


---

## 14. Format entrée journal

Chaque entrée du journal (section 11) doit suivre :

- Titre : YYYY-MM-DD — Titre court
- Périodes : matin, après-midi, soir avec horaires HH:MM-HH:MM
- Actions horodatées avec résultats factuels
- Décisions structurantes listées
- État DB post-session documenté

---

## 15. Contacts & accès

- EC2 SSH : `ssh -i ~/.ssh/kakapo-key.pem ubuntu@<ec2-public-ip>`
- Railway dashboard : projet kakapo-back-production
- Vercel dashboard : projet oparence-site
- GitHub repo : privé
- Domaine prod : oparence.com (Vercel)

---

**Dernière mise à jour : 8 juin 2026 21:25 UTC (post-lancement bulk PubMed v4)**

---

## 16. Post-mortem stabilisation backend demo (12 juin 2026)

### Symptome initial
/demo/stream, /demo/query, /demo/integrity/summary en 502 / timeout.
La demo affichait du SQL brut PostgreSQL aux utilisateurs.
Compteur catalog affichait 14,2M alors que la base contient 35,6M.

### 4 bugs racines identifies

**BUG 1 - Absence de db.rollback() dans les except (demo.py)**
Quand une query crash (DiskFull shared_memory sur 35M rows), la
transaction SQLAlchemy passe en etat "aborted". Sans rollback, toutes
les queries suivantes de la meme session recoivent "current transaction
is aborted, commands ignored until end of transaction block".
FIX : db.rollback() dans chaque except + rollback preventif en debut
de /demo/query.

**BUG 2 - Polling frontend agressif sans garde-fous (OparenceTerminal.tsx)**
setInterval 8s/12s avec fetch SANS AbortController, SANS timeout, SANS
skip-si-deja-en-cours, SANS backoff. Chaque navigateur ouvert bombardait
le backend. Les queries lentes s'empilaient en zombies PostgreSQL
(jusqu'a 31 connexions actives stuck pendant 3h+).
FIX : AbortController timeout 6s, skip si fetch en cours, backoff
exponentiel sur erreur, frequence 30s/60s au lieu de 8s/12s.

**BUG 3 - Fallback ILIKE sur 35M rows (kakapo_search.py)**
Quand la query tsvector echouait, le code basculait sur un fallback
ORM .ilike() qui scanne sequentiellement 35M rows = hang infini.
C'est ce fallback qui ressortait le SQL brut.
FIX : suppression du fallback, return [] propre + rollback.

**BUG 4 - Statistiques PostgreSQL perimees (pg_class.reltuples)**
Le compteur affichait 14,226,565 alors que la table contient 35,626,416
rows. Le bulk PubMed v4 avait insere +21M rows sans qu'un ANALYZE soit
lance. pg_class.reltuples = estimation perimee.
FIX : ANALYZE publications (25s) -> reltuples corrige a 35,626,416.

### Chiffres reels confirmes (post-ANALYZE 12 juin)
- Publications : 35,626,416 (et NON 14,2M)
- Dont certified : ~32,7M (92%)
- Dont indexed : ~2,4M (7%)
- Dont shell : ~0,4M (1%)
- KPTs : 35,3M (ratio 1.00 par publication, aucun doublon)
- Abstract present : ~61% des publications
- Index GIN full-text : idx_pub_fulltext_en (present, fonctionnel)
- Query "machine & learning & sepsis" : 626 matches en 0.4s (OK)

### REGLES PERMANENTES - ne plus retomber dans ces travers

R1. JAMAIS de query metier lourde (COUNT, GROUP BY, regex, ILIKE) sur
    la table publications (35M) sans : soit pg_class.reltuples
    (estimation instantanee), soit TABLESAMPLE SYSTEM(n), soit index
    dedie + LIMIT. JAMAIS de COUNT(*) brut, title ~ regex, ou ILIKE
    sans index.

R2. TOUJOURS db.rollback() dans chaque except entourant un db.execute().
    Pattern obligatoire :
        try: result = db.execute(...)
        except Exception: db.rollback(); result = fallback

R3. /demo/health et endpoints de monitoring NE FONT JAMAIS de query
    metier. SELECT 1 maximum.

R4. Tout polling frontend DOIT avoir : AbortController + timeout,
    skip-si-en-cours, backoff exponentiel. Frequence minimale 30s.
    JAMAIS de setInterval + fetch nu.

R5. Apres TOUT bulk d'ingestion massif : lancer ANALYZE sur les tables
    touchees AVANT de se fier aux compteurs (pg_class.reltuples).

R6. STOP PATCH LIVE. Avant chaque git push backend :
    - tester en local (Mac venv connecte a la DB Railway en lecture)
    - verifier le git diff manuellement
    - prevoir le git revert en cas de crash
    Doctrine violee 4x le 12 juin = 4 crashs prod. Ne plus jamais.

R7. AVANT de debugger le code : verifier pg_stat_activity (queries
    zombie) AVANT de toucher au code. Le bug peut etre des connexions
    stuck, pas le code lui-meme. Commande :
    SELECT pid, state, EXTRACT(EPOCH FROM (NOW()-query_start)) as dur
    FROM pg_stat_activity WHERE state='active' ORDER BY query_start;

### Commits de la session (kakapo-back)
- cae85e8 fix(demo): pg_class.reltuples pour catalog
- (rollback x4 dans demo_stream except blocks)
- (try/except + rollback /demo/integrity/summary)
- 2d3995f fix(demo): wrap /demo/query + clean 503
- c7c2abf fix(demo): rollback preventif avant query
- (kakapo_search: suppression fallback ILIKE)
- ANALYZE publications (manuel, a automatiser post-ingestion)

### RECOMMANDATION CRITIQUE - faire valider par un dev senior
Les patches du 12 juin ont stabilise la demo mais ont ete appliques en
urgence SANS tests automatises ni revue de code. AVANT le pitch
investisseur (Jean de La Rochebrochard / New Wave) ou un premier contrat
enterprise, faire auditer par un dev FastAPI/PostgreSQL senior
(Malt/Comet, ~200-400 EUR / 2-3h) :
- valider les 4 patches (rollback, polling, suppression fallback, ANALYZE)
- mettre en place statement_timeout cote PostgreSQL (garde-fou anti-zombie)
- ecrire des smoke tests pytest sur /demo/*
- automatiser ANALYZE dans le pipeline d'ingestion
- ajouter un index sur les colonnes de recherche frequentes si besoin
Raison : Claude.ai ne peut pas tester en local docker-compose ni
executer de suite de tests. Un humain qui teste AVANT push evite les
regressions que cette session a connues.

