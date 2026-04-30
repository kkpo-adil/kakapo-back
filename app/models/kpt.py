import uuid
from datetime import datetime

from sqlalchemy import Boolean, String, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.types import UUIDType, JSONType


class KPT(Base):
    __tablename__ = "kpts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(), primary_key=True, default=uuid.uuid4
    )
    kpt_id: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False, index=True,
        comment="KPT-<8pub>-v<version>-<8suffix>"
    )
    publication_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(), ForeignKey("publications.id", ondelete="CASCADE"), nullable=False
    )
    content_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="SHA-256 of file content"
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default="active", nullable=False,
        comment="active | challenged | revoked | superseded"
    )
    is_indexed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    metadata_json: Mapped[dict | None] = mapped_column(
        JSONType(), nullable=True, comment="ORCID, ROR, datasets, trust_fields"
    )

    publication: Mapped["Publication"] = relationship(
        "Publication", back_populates="kpts"
    )
