import os
import io
import json
import hashlib
import base64
import logging
from datetime import datetime, timezone
from dataclasses import dataclass
from app.schemas.demo import DemoResult

logger = logging.getLogger(__name__)


@dataclass
class SignedPDFInfo:
    filename: str
    size_bytes: int
    sha256: str
    signature_b64: str
    generated_at: datetime


def _sign_content(content_json: str) -> str:
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        raw = os.environ.get("KAKAPO_PDF_SIGNING_KEY", "")
        if not raw:
            return "NO_SIGNING_KEY"
        cleaned = raw.strip()
        if "\\n" in cleaned:
            cleaned = cleaned.replace("\\n", "\n")
        elif "\n" in cleaned and "-----" in cleaned:
            cleaned = cleaned.replace("\n", "\n")
        key_pem = cleaned.encode("utf-8")
        private_key = serialization.load_pem_private_key(key_pem, password=None)
        signature = private_key.sign(
            content_json.encode(),
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )
        return base64.b64encode(signature).decode()
    except Exception as e:
        return f"SIGNING_ERROR: {e}"

def generate_signed_pdf(result: DemoResult) -> tuple[bytes, SignedPDFInfo]:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.enums import TA_LEFT, TA_CENTER

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)

    styles = getSampleStyleSheet()
    gold = colors.HexColor("#B45309")
    navy = colors.HexColor("#1D4ED8")
    slate = colors.HexColor("#475569")

    title_style = ParagraphStyle("title", parent=styles["Heading1"], fontSize=18, textColor=navy, spaceAfter=6)
    sub_style = ParagraphStyle("sub", parent=styles["Normal"], fontSize=9, textColor=slate, spaceAfter=12)
    h2_style = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=13, textColor=navy, spaceBefore=12, spaceAfter=6)
    body_style = ParagraphStyle("body", parent=styles["Normal"], fontSize=10, leading=14, spaceAfter=8)
    mono_style = ParagraphStyle("mono", parent=styles["Code"], fontSize=8, textColor=slate, leading=11)
    disclaimer_style = ParagraphStyle("disc", parent=styles["Normal"], fontSize=8, textColor=slate, leading=11)

    story = []
    story.append(Paragraph("KAKAPO — Verified Response Export", title_style))
    story.append(Paragraph(f"Généré le {result.timestamp.strftime('%Y-%m-%d %H:%M:%S')} UTC · Request ID: {result.request_id}", sub_style))
    story.append(HRFlowable(width="100%", thickness=1, color=gold))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("Question", h2_style))
    story.append(Paragraph(result.question, body_style))

    story.append(Paragraph("Réponse", h2_style))
    answer_clean = result.answer_text.replace("<", "&lt;").replace(">", "&gt;")
    story.append(Paragraph(answer_clean, body_style))

    if result.cited_kpts:
        story.append(Paragraph("Sources citées", h2_style))
        for i, kpt in enumerate(result.cited_kpts, 1):
            badge = "KPT CERTIFIÉ" if kpt.kpt_status == "certified" else "i-KPT INDEXÉ"
            score = f"Trust Score: {kpt.trust_score}/100" if kpt.trust_score else (f"Indexation: {kpt.indexation_score}/100" if kpt.indexation_score else "")
            data = [
                [Paragraph(f"[{i}] {badge}", ParagraphStyle("badge", parent=styles["Normal"], fontSize=9, textColor=gold if kpt.kpt_status == "certified" else slate, fontName="Helvetica-Bold")),
                 Paragraph(score, ParagraphStyle("score", parent=styles["Normal"], fontSize=9, textColor=navy))],
                [Paragraph(kpt.title, ParagraphStyle("ktitle", parent=styles["Normal"], fontSize=10, fontName="Helvetica-Bold")), ""],
                [Paragraph(f"KPT ID: {kpt.kpt_id}", mono_style), ""],
                [Paragraph(f"Hash: {kpt.hash_kpt[:32]}...", mono_style), ""],
                [Paragraph(f"DOI: {kpt.doi or '—'}", mono_style), Paragraph(f"Date: {kpt.publication_date}", mono_style)],
            ]
            t = Table(data, colWidths=[11*cm, 5*cm])
            t.setStyle(TableStyle([
                ("BOX", (0,0), (-1,-1), 0.5, colors.HexColor("#E2DFD9")),
                ("LEFTPADDING", (0,0), (-1,-1), 6),
                ("RIGHTPADDING", (0,0), (-1,-1), 6),
                ("TOPPADDING", (0,0), (-1,-1), 4),
                ("BOTTOMPADDING", (0,0), (-1,-1), 4),
                ("SPAN", (0,1), (1,1)),
                ("SPAN", (0,2), (1,2)),
                ("SPAN", (0,3), (1,3)),
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#FAFAF8")),
            ]))
            story.append(t)
            story.append(Spacer(1, 0.2*cm))

    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#E2DFD9")))
    story.append(Spacer(1, 0.2*cm))

    content_dict = {
        "question": result.question,
        "answer": result.answer_text,
        "cited_kpts": [k.model_dump() for k in result.cited_kpts],
        "request_id": result.request_id,
        "timestamp": result.timestamp.isoformat(),
    }
    content_json = json.dumps(content_dict, sort_keys=True, ensure_ascii=False)
    signature_b64 = _sign_content(content_json)
    sha256_hash = hashlib.sha256(content_json.encode()).hexdigest()

    story.append(Paragraph(f"SHA-256: {sha256_hash}", mono_style))
    story.append(Paragraph(f"Signature: {signature_b64[:64]}...", mono_style))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(
        "Ce document a été généré par l'infrastructure KAKAPO. La signature RSA-PSS peut être "
        "vérifiée avec la clé publique KAKAPO disponible sur kakapo-front.vercel.app/about/kpt.",
        disclaimer_style
    ))

    doc.build(story)
    pdf_bytes = buf.getvalue()

    info = SignedPDFInfo(
        filename=f"kakapo-verified-{result.request_id[:8]}.pdf",
        size_bytes=len(pdf_bytes),
        sha256=hashlib.sha256(pdf_bytes).hexdigest(),
        signature_b64=signature_b64,
        generated_at=datetime.now(timezone.utc),
    )
    return pdf_bytes, info
