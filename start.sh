python3 -c "
import os
from sqlalchemy import create_engine, text
engine = create_engine(os.environ['DATABASE_URL'])
with engine.connect() as conn:
    conn.execute(text('CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)'))
    existing = conn.execute(text(\"SELECT version_num FROM alembic_version WHERE version_num='001'\")).fetchone()
    if not existing:
        conn.execute(text(\"INSERT INTO alembic_version VALUES ('001')\"))
    conn.commit()
print('Alembic version initialized')
"
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
