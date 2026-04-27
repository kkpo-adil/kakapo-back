python3 -c "
import os
from sqlalchemy import create_engine, text
engine = create_engine(os.environ['DATABASE_URL'])
with engine.connect() as conn:
    conn.execute(text('CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)'))
    for v in ['001', '002', '003', '004', '005']:
        existing = conn.execute(text(f\"SELECT version_num FROM alembic_version WHERE version_num='{v}'\")).fetchone()
        if not existing:
            conn.execute(text(f\"INSERT INTO alembic_version VALUES ('{v}')\"))
    conn.commit()
print('Alembic version initialized')
"
python3 -c "
import os
from sqlalchemy import create_engine, text
engine = create_engine(os.environ['DATABASE_URL'])
with engine.connect() as conn:
    conn.execute(text('ALTER TABLE ai_client_profiles ALTER COLUMN api_key TYPE VARCHAR(72)'))
    conn.commit()
print('api_key column fixed')
" || true
python3 -c "
import os
from sqlalchemy import create_engine, text
engine = create_engine(os.environ['DATABASE_URL'])
with engine.connect() as conn:
    try:
        conn.execute(text('ALTER TABLE scientist_profiles ADD COLUMN IF NOT EXISTS monthly_kpt_quota INTEGER NOT NULL DEFAULT 50'))
        conn.execute(text('ALTER TABLE scientist_profiles ADD COLUMN IF NOT EXISTS kpt_count_current_period INTEGER NOT NULL DEFAULT 0'))
        conn.execute(text('ALTER TABLE scientist_profiles ADD COLUMN IF NOT EXISTS kpt_quota_period_start TIMESTAMPTZ NOT NULL DEFAULT NOW()'))
        conn.commit()
        print('scientist_profiles quota columns added')
    except Exception as e:
        print(f'quota columns: {e}')
" || true
python3 -c "
import os
from sqlalchemy import create_engine, text
engine = create_engine(os.environ['DATABASE_URL'])
with engine.connect() as conn:
    try:
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS scientific_reviews (
                id VARCHAR(36) PRIMARY KEY,
                publication_id VARCHAR(36) REFERENCES publications(id),
                reviewer_orcid VARCHAR(64) NOT NULL,
                reviewer_name VARCHAR(255) NOT NULL,
                reviewer_institution VARCHAR(255),
                methodology_score INTEGER NOT NULL,
                data_score INTEGER NOT NULL,
                reproducibility_score INTEGER NOT NULL,
                clarity_score INTEGER NOT NULL,
                global_score FLOAT NOT NULL,
                comment TEXT,
                flag VARCHAR(50) NOT NULL DEFAULT 'none',
                is_conflict_of_interest BOOLEAN NOT NULL DEFAULT false,
                is_same_institution BOOLEAN NOT NULL DEFAULT false,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        '''))
        conn.execute(text('CREATE INDEX IF NOT EXISTS ix_scientific_reviews_publication_id ON scientific_reviews(publication_id)'))
        conn.execute(text('CREATE INDEX IF NOT EXISTS ix_scientific_reviews_reviewer_orcid ON scientific_reviews(reviewer_orcid)'))
        conn.commit()
        print('scientific_reviews table ready')
    except Exception as e:
        print(f'scientific_reviews: {e}')
" || true
python3 -c "
import os
from sqlalchemy import create_engine, text
engine = create_engine(os.environ['DATABASE_URL'])
with engine.connect() as conn:
    conn.execute(text('DELETE FROM alembic_version'))
    conn.execute(text(\"INSERT INTO alembic_version VALUES ('008')\"))
    conn.commit()
    print('alembic_version reset to 008')
" || true
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
