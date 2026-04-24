import time
from fastapi import Request, Response
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.ai_client_profile import AIClientProfile
from app.models.query_log import QueryLog, QueryResult

TRACKED_ENDPOINTS = [
    "/integrity/verify",
    "/kpt/",
    "/publications/",
    "/trust/score/",
]

async def track_ai_client_usage(request: Request, call_next):
    api_key = request.headers.get("X-Client-API-Key", "")
    path = request.url.path
    should_track = api_key and any(path.startswith(ep) for ep in TRACKED_ENDPOINTS)

    start = time.time()
    response: Response = await call_next(request)
    elapsed_ms = int((time.time() - start) * 1000)

    if should_track:
        db: Session = SessionLocal()
        try:
            client = db.query(AIClientProfile).filter(
                AIClientProfile.api_key == api_key,
                AIClientProfile.is_active == True,
            ).first()
            if client:
                result = QueryResult.match if response.status_code == 200 else QueryResult.error
                billed = float(client.price_per_query)
                log = QueryLog(
                    ai_client_id=client.id,
                    endpoint=path,
                    result=result,
                    response_time_ms=elapsed_ms,
                    billed_amount=billed,
                )
                client.quota_used_current_month += 1
                db.add(log)
                db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    return response
