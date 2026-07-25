"""Case review report.

Produces a PDF a team lead can read away from the console: what the customer
wrote, how the desk classified it, what it did, what it drafted, and why any
case stopped for a person. Intended for quality review and audit sampling.
"""
import io
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

INK = colors.HexColor("#14181F")
SLATE = colors.HexColor("#5C6670")
MUTE = colors.HexColor("#8A9199")
RULE = colors.HexColor("#DDE0DE")
TEAL = colors.HexColor("#0F5F4E")
CRIMSON = colors.HexColor("#A32235")
SOFT = colors.HexColor("#F5F6F5")

TYPE_LABEL = {
    "billing_dispute": "Billing dispute",
    "general_enquiry": "General enquiry",
    "service_request": "Service request",
    "complaint": "Complaint",
}


def _styles():
    s = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("t", parent=s["Title"], fontName="Helvetica-Bold",
                                fontSize=18, textColor=INK, alignment=TA_LEFT, spaceAfter=2),
        "sub": ParagraphStyle("s", parent=s["Normal"], fontName="Helvetica",
                              fontSize=9, textColor=MUTE, spaceAfter=14),
        "h": ParagraphStyle("h", parent=s["Normal"], fontName="Helvetica-Bold",
                            fontSize=12, textColor=INK, spaceBefore=4, spaceAfter=6),
        "eyebrow": ParagraphStyle("e", parent=s["Normal"], fontName="Helvetica-Bold",
                                  fontSize=7, textColor=MUTE, spaceBefore=9, spaceAfter=3),
        "body": ParagraphStyle("b", parent=s["Normal"], fontName="Helvetica",
                               fontSize=9, textColor=INK, leading=13),
        "quote": ParagraphStyle("q", parent=s["Normal"], fontName="Helvetica",
                                fontSize=9, textColor=SLATE, leading=13,
                                leftIndent=8, borderPadding=0),
        "small": ParagraphStyle("sm", parent=s["Normal"], fontName="Helvetica",
                                fontSize=8, textColor=SLATE, leading=11),
        "held": ParagraphStyle("hd", parent=s["Normal"], fontName="Helvetica-Bold",
                               fontSize=9, textColor=CRIMSON, leading=12),
        "auto": ParagraphStyle("au", parent=s["Normal"], fontName="Helvetica-Bold",
                               fontSize=9, textColor=TEAL, leading=12),
    }


def _esc(text: Any) -> str:
    t = "" if text is None else str(text)
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")


def _case_block(case: Dict[str, Any], audit: List[Dict[str, Any]], st) -> list:
    held = bool(case.get("hold_for_human"))
    flow = []

    header = Table([[
        Paragraph(f'<b>{_esc(case.get("subject") or "(no subject)")}</b>', st["h"]),
        Paragraph(f'{_esc(case.get("case_id"))}<br/>{_esc(str(case.get("received_at"))[:16].replace("T", " "))}',
                  ParagraphStyle("r", parent=st["small"], alignment=2, textColor=MUTE)),
    ]], colWidths=[112 * mm, 55 * mm])
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.6, RULE),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    flow.append(header)
    flow.append(Spacer(1, 7))

    meta = Table([[
        Paragraph(f'<b>{_esc(TYPE_LABEL.get(case.get("request_type"), case.get("request_type")))}</b>', st["small"]),
        Paragraph(f'{_esc(str(case.get("urgency", "")).title())} priority', st["small"]),
        Paragraph(f'Certainty {float(case.get("confidence") or 0):.0%}', st["small"]),
        Paragraph(_esc(case.get("routed_to")), st["small"]),
    ]], colWidths=[42 * mm, 32 * mm, 35 * mm, 58 * mm])
    meta.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SOFT),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
    ]))
    flow.append(meta)

    if held:
        reasons = json.loads(case.get("hold_reasons") or "[]")
        flow.append(Spacer(1, 6))
        flow.append(Paragraph("STOPPED FOR A PERSON — NOTHING WAS SENT", st["eyebrow"]))
        for r in reasons:
            flow.append(Paragraph(f"— {_esc(r)}", st["held"]))
    else:
        flow.append(Spacer(1, 6))
        flow.append(Paragraph(f"Handled automatically and sent to {_esc(case.get('routed_to'))}.", st["auto"]))

    flow.append(Paragraph("WHAT THE CUSTOMER WROTE", st["eyebrow"]))
    body = case.get("customer_message") or "(message text not retained in the case store)"
    flow.append(Paragraph(_esc(body), st["quote"]))

    flow.append(Paragraph("WHAT THE DESK DID", st["eyebrow"]))
    for i, a in enumerate(json.loads(case.get("actions") or "[]"), 1):
        flow.append(Paragraph(f'<b>{i}. {_esc(a.get("step"))}</b> — {_esc(a.get("detail"))}', st["small"]))

    flow.append(Paragraph("REPLY THE DESK DRAFTED", st["eyebrow"]))
    flow.append(Paragraph(_esc(case.get("draft_response") or "(none)"), st["quote"]))

    if audit:
        flow.append(Paragraph("DECISION HISTORY", st["eyebrow"]))
        rows = [[Paragraph(f'<b>{_esc(e["node"])}</b>', st["small"]),
                 Paragraph(_esc(e["decision"]), st["small"]),
                 Paragraph(_esc(str(e["ts"])[11:19]), st["small"])] for e in audit]
        t = Table(rows, colWidths=[32 * mm, 118 * mm, 17 * mm])
        t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, -2), 0.4, RULE),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ]))
        flow.append(t)

    flow.append(Spacer(1, 12))
    return flow


def build_review_pdf(cases: List[Dict[str, Any]],
                     audit_lookup: Optional[Dict[str, List[Dict[str, Any]]]] = None,
                     title: str = "Case review") -> bytes:
    """Return a PDF over the supplied cases, one section each."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=21 * mm, rightMargin=21 * mm,
                            topMargin=18 * mm, bottomMargin=18 * mm,
                            title=title, author="Front Desk")
    st = _styles()
    audit_lookup = audit_lookup or {}
    total = len(cases)
    held = sum(1 for c in cases if c.get("hold_for_human"))

    flow = [Paragraph(title, st["title"])]
    flow.append(Paragraph(
        f'Front Desk · card servicing · generated '
        f'{datetime.now(timezone.utc).strftime("%d %B %Y, %H:%M UTC")}', st["sub"]))

    summary = Table([[
        Paragraph(f'<b>{total}</b><br/>messages', st["body"]),
        Paragraph(f'<b>{total - held}</b><br/>cleared without a person', st["body"]),
        Paragraph(f'<b>{held}</b><br/>stopped for review', st["body"]),
        Paragraph(f'<b>{(total - held) / total:.0%}</b><br/>handled end to end' if total else '—', st["body"]),
    ]], colWidths=[38 * mm, 45 * mm, 42 * mm, 42 * mm])
    summary.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SOFT),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    flow.append(summary)
    flow.append(Spacer(1, 4))
    flow.append(Paragraph(
        "Cases reach a person by design rather than by failure: complaints, customers disclosing "
        "difficult circumstances, and anything the desk was unsure about are always reviewed.",
        st["small"]))
    flow.append(Spacer(1, 14))

    for i, case in enumerate(cases):
        flow.extend(_case_block(case, audit_lookup.get(case.get("case_id"), []), st))
        if i < len(cases) - 1:
            flow.append(PageBreak())

    doc.build(flow)
    return buf.getvalue()