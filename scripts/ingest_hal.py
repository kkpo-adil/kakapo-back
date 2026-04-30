#!/usr/bin/env python3
"""
CLI d'ingestion HAL pour KAKAPO.

Exemples :
  python scripts/ingest_hal.py --query "machine learning" --max-results 5000 --year-from 2020
  python scripts/ingest_hal.py --query "*:*" --domains "info.info-lg" "info.info-ai" --max-results 2000
  python scripts/ingest_hal.py --query "climate" --max-results 100 --dry-run
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.services.hal_ingestor import ingest_batch


def main():
    parser = argparse.ArgumentParser(description="Ingestion HAL → KAKAPO i-KPT")
    parser.add_argument("--query", required=True, help="Requête HAL (ex: 'machine learning')")
    parser.add_argument("--max-results", type=int, default=1000)
    parser.add_argument("--domains", nargs="*", help="Domaines HAL (ex: info.info-lg info.info-ai)")
    parser.add_argument("--year-from", type=int)
    parser.add_argument("--year-to", type=int)
    parser.add_argument("--dry-run", action="store_true", help="Simule sans écrire en base")
    args = parser.parse_args()

    if args.dry_run:
        from app.services import hal_client
        print(f"[DRY-RUN] Fetching up to {args.max_results} results for query: {args.query!r}")
        docs = hal_client.search(args.query, rows=min(args.max_results, 10))
        print(f"[DRY-RUN] Sample: {len(docs)} docs fetched (showing first 3):")
        for doc in docs[:3]:
            title = doc.get("title_s", ["?"])
            print(f"  - {title[0] if isinstance(title, list) else title} | HAL: {doc.get('halId_s', '?')}")
        return

    db = SessionLocal()
    try:
        print(f"Ingestion HAL: query={args.query!r} max={args.max_results}")
        report = ingest_batch(
            db=db,
            query=args.query,
            max_results=args.max_results,
            domains=args.domains,
            year_from=args.year_from,
            year_to=args.year_to,
        )
        print("\n=== RAPPORT D'INGESTION ===")
        print(f"  Fetched     : {report.total_fetched}")
        print(f"  Created     : {report.total_created}")
        print(f"  Skipped     : {report.total_skipped_existing}")
        print(f"  Failed      : {report.total_failed}")
        print(f"  Duration    : {report.duration_seconds}s")
        if report.errors:
            print(f"  Errors ({len(report.errors)}):")
            for e in report.errors[:10]:
                print(f"    - {e}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
