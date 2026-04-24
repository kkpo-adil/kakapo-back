python3 -c "
import os
from sqlalchemy import create_engine, text
engine = create_engine(os.environ['DATABASE_URL'])
with engine.connect() as conn:
    conn.execute(text('CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)'))
    for v in ['001', '002']:
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
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
