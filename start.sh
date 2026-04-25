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
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
