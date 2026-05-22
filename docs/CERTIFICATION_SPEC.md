# Oparence Certification & Integrity Spec

Version : v1.0
Date    : 2026-05-21
Status  : Production V1

## Principe fondamental

Chaque KPT (Knowledge Provenance Token) est caracterise par un systeme de fingerprints multi-zones SHA-256, calcules sur des zones canoniques du document source. Une alteration est detectee si et seulement si une zone cle change.

## 1. Architecture du fingerprinting

### 1.1 Clinical Trials

- identity  : nct_id + title + sponsor                                                     -> Renommage, reattribution sponsor
- protocol  : study_type + phase + conditions + interventions + eligibility + status       -> Amendement protocole
- outcomes  : primary_outcomes + secondary_outcomes                                        -> Modification endpoints
- narrative : brief_summary + detailed_description                                         -> Reecriture descriptive
- canonical : hash des 4 zones precedentes                                                 -> Alteration globale

### 1.2 Publications

- identity   : doi + title + authors + journal     -> Identite bibliographique
- metadata   : title + authors + journal           -> Modification metadata
- content    : abstract + full_text                -> Modification contenu
- references : references_json                     -> Modification bibliographie
- canonical  : hash des 4 zones precedentes        -> Alteration globale

### 1.3 Meta-fingerprints

- content_length : caracteres totaux dans zones cles
- word_count     : mots totaux
- first_sentence : SHA-256 de la premiere phrase
- last_sentence  : SHA-256 de la derniere phrase

## 2. Champs explicitement non-hashes (zone bruit)

- last_update_posted (timestamp API)
- enrollment_count (peut evoluer)
- locations.status
- contacts
- citations_count / downloads_count / views_count

Justification : un LLM cite le protocole, pas le nombre d'inscrits. La certification reflete le contenu scientifique opposable, pas la metadonnee vivante.

## 3. Normalisation canonique

- JSON serialise avec sort_keys=True, separators=(',', ':'), ensure_ascii=False
- Strings strippees + reduction espaces multiples
- Listes triees alphabetiquement
- Valeurs None deterministes
- Encodage UTF-8
- SHA-256 sur les bytes du JSON canonique

## 4. Tests de non-regression obligatoires

1. Determinisme : 10 calculs successifs identiques
2. Robustesse   : whitespace/ordre/encoding n'affectent pas le hash
3. Detection    : changement zone cle change le hash
4. Tolerance    : changement zone bruit n'affecte pas le hash

Implementation : python3 app/services/canonical_fingerprint.py

## 5. Detection d'alteration

### 5.1 Triggers

- Periodic re-crawl : 24/7 background, refresh sous 24h
- On-demand verify  : API endpoint /demo/integrity/verify/{kpt_id}
- Verify-on-stream  : sur appel /demo/stream (roadmap v1.5)

### 5.2 KPL Versioning

Quand une alteration est detectee :
- previous_hash stocke
- kpl_version incremente (v1 -> v2)
- record append-only insere dans alterations
- integrity_status passe a 'altered' ou 'retracted'

### 5.3 Granularite

alteration_type :
- identity   : essai renomme ou sponsor change
- protocol   : amendement protocole (critique pharma)
- outcomes   : endpoints modifies (signal regulation)
- narrative  : description reecrite (souvent cosmetique)
- multiple   : plusieurs zones simultanees
- retracted  : source 404

### 5.4 Champ significant

True si alteration concerne identity, protocol ou outcomes.
False si seule narrative est modifiee.

## 6. Audit trail immuable

Table alterations append-only. Aucun UPDATE ni DELETE n'est autorise par l'application. Chaque detection est conservee historiquement.

## 7. Roadmap

- v1.0  LIVE             : Multi-zone fingerprinting + re-crawl + on-demand verify
- v1.5  Q3 2026 planned  : Verify-on-stream
- v2.0  Q4 2026 planned  : Subscription Crossref/PMC update feeds
- v2.5  Q1 2027 planned  : Propagation automatique aux clients
