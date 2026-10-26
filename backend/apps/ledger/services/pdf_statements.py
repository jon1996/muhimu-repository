"""PDF liasse SN — bilan, compte de résultat, TFT, notes (Titre IX, art. 8 et 22)."""

from __future__ import annotations

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from apps.ledger.money import format_amount_fr
from apps.ledger.services.pdf_disclaimers import (
    NOTE2_SECTION_LABEL,
    PDF_BETA_DISCLAIMER_LINES,
    PDF_BETA_DISCLAIMER_TITLE,
    PDF_FOOTER_LEFT,
)

STATEMENT_KINDS = ("liasse", "bilan", "result", "tft", "notes")

INK = colors.HexColor("#0F3D3E")
MUTED = colors.HexColor("#5C6560")
RULE = colors.HexColor("#C4B8A8")
BAND = colors.HexColor("#E8EEEA")
HEAD_FG = colors.white

_LATIN1 = (
    ("\u2019", "'"),
    ("\u2018", "'"),
    ("\u2013", "-"),
    ("\u2014", "-"),
    ("\u00a0", " "),
    ("\u202f", " "),
    ("œ", "oe"),
    ("Œ", "OE"),
)


def pdf_text(value) -> str:
    text = str(value or "")
    for src, dst in _LATIN1:
        text = text.replace(src, dst)
    return text.encode("latin-1", "replace").decode("latin-1")


def pdf_filename(payload: dict, kind: str) -> str:
    year = payload.get("exercise_year") or "exercice"
    smt = payload.get("regime") == "smt"
    scope = payload.get("scope")
    if smt:
        names = {
            "liasse": "liasse-smt",
            "bilan": "situation-patrimoniale",
            "result": "etat-de-tresorerie",
            "tft": "etat-de-tresorerie",
            "notes": "notes-annexes-smt",
        }
    elif scope == "consolidated":
        names = {
            "liasse": "liasse-consolidee",
            "bilan": "bilan-consolide",
            "result": "compte-de-resultat-consolide",
            "tft": "tft-consolide",
            "notes": "notes-consolidees",
        }
    elif scope == "combined":
        names = {
            "liasse": "liasse-combinee",
            "bilan": "bilan-combine",
            "result": "compte-de-resultat-combine",
            "tft": "tft-combine",
            "notes": "notes-combinees",
        }
    else:
        names = {
            "liasse": "liasse-sn",
            "bilan": "bilan",
            "result": "compte-de-resultat",
            "tft": "tft",
            "notes": "notes-annexes",
        }
    return f"{names.get(kind, 'etat')}-{year}.pdf"


def render_statements_pdf(payload: dict, kind: str = "liasse") -> bytes:
    kind = (kind or "liasse").lower()
    if kind not in STATEMENT_KINDS:
        raise ValueError("État PDF inconnu (bilan, result, tft, notes ou liasse).")

    buffer = BytesIO()
    pagesize = landscape(A4)
    entity = payload.get("entity") or {}
    currency = entity.get("currency_code") or "XOF"
    year = payload.get("exercise_year")
    period_label = payload.get("period_label") or ""
    prior = payload.get("comparative_year")
    smt = payload.get("regime") == "smt"
    scope = payload.get("scope")
    if smt:
        title_map = {
            "liasse": "Liasse SMT SYSCOHADA",
            "bilan": "Situation patrimoniale",
            "result": "Etat de tresorerie",
            "tft": "Etat de tresorerie",
            "notes": "Notes annexes SMT",
        }
    elif scope == "consolidated":
        title_map = {
            "liasse": "Liasse consolidee SYSCOHADA",
            "bilan": "Bilan consolide (avant repartition)",
            "result": "Compte de resultat consolide",
            "tft": "TFT consolide",
            "notes": "Notes annexes consolidees",
        }
    elif scope == "combined":
        title_map = {
            "liasse": "Liasse combinee SYSCOHADA",
            "bilan": "Bilan combine (avant repartition)",
            "result": "Compte de resultat combine",
            "tft": "TFT combine",
            "notes": "Notes annexes combinees",
        }
    else:
        title_map = {
            "liasse": "Liasse SN SYSCOHADA",
            "bilan": "Bilan (avant repartition)",
            "result": "Compte de resultat",
            "tft": "Tableau des flux de tresorerie",
            "notes": "Notes annexes SN",
        }

    def draw_chrome(canvas, doc):
        canvas.saveState()
        width, height = pagesize
        canvas.setFillColor(INK)
        canvas.rect(0, height - 6 * mm, width, 6 * mm, fill=1, stroke=0)
        canvas.setFillColor(INK)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(
            doc.leftMargin,
            height - 14 * mm,
            pdf_text(entity.get("legal_name") or entity.get("name") or "Muhimu ERP"),
        )
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(
            width - doc.rightMargin,
            height - 14 * mm,
            pdf_text(entity.get("regime_label") or "Systeme Normal"),
        )
        canvas.setFont("Helvetica-Bold", 12)
        canvas.drawString(doc.leftMargin, height - 22 * mm, pdf_text(title_map[kind]))
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(MUTED)
        bits = [
            f"Exercice {year}" if year else "",
            f"Arrete {period_label}" if period_label else "",
            f"Devise {currency}",
            "Comptabilite de tresorerie" if smt else "Bilan avant repartition",
        ]
        if prior:
            bits.append(f"Comparatif {prior}")
        canvas.drawString(doc.leftMargin, height - 28 * mm, pdf_text("  |  ".join(b for b in bits if b)))
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.4)
        canvas.line(doc.leftMargin, height - 31 * mm, width - doc.rightMargin, height - 31 * mm)
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 7)
        canvas.drawString(doc.leftMargin, 10 * mm, pdf_text(PDF_FOOTER_LEFT))
        canvas.drawRightString(width - doc.rightMargin, 10 * mm, str(canvas.getPageNumber()))
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=pagesize,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=36 * mm,
        bottomMargin=16 * mm,
        title=pdf_text(f"{title_map[kind]} {year or ''}".strip()),
        author="Muhimu ERP",
        pageCompression=0,
    )

    story: list = []
    story.extend(_beta_disclaimer_block())
    if kind == "liasse":
        story.extend(_cover(payload, currency))
        story.append(PageBreak())
        story.extend(_bilan_flow(payload, currency, prior))
        story.append(PageBreak())
        if smt:
            story.extend(_tft_flow(payload, currency, prior))
        else:
            story.extend(_result_flow(payload, currency, prior))
            story.append(PageBreak())
            story.extend(_tft_flow(payload, currency, prior))
        story.append(PageBreak())
        story.extend(_notes_flow(payload))
    elif kind == "bilan":
        story.extend(_bilan_flow(payload, currency, prior))
    elif kind == "result":
        story.extend(_tft_flow(payload, currency, prior) if smt else _result_flow(payload, currency, prior))
    elif kind == "notes":
        story.extend(_notes_flow(payload))
    else:
        story.extend(_tft_flow(payload, currency, prior))

    doc.build(story, onFirstPage=draw_chrome, onLaterPages=draw_chrome)
    return buffer.getvalue()


def _beta_disclaimer_block() -> list:
    s = _styles()
    warn = ParagraphStyle(
        "betaWarn",
        parent=s["p"],
        fontName="Helvetica-Bold",
        fontSize=8,
        textColor=colors.HexColor("#8B3A2A"),
        spaceAfter=2 * mm,
        leading=11,
    )
    flow = [
        Paragraph(pdf_text(PDF_BETA_DISCLAIMER_TITLE), warn),
    ]
    for line in PDF_BETA_DISCLAIMER_LINES:
        flow.append(Paragraph(pdf_text(line), s["muted"]))
    flow.append(Spacer(1, 4 * mm))
    return flow


def _styles():
    return {
        "h": ParagraphStyle(
            "h",
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=INK,
            spaceAfter=4 * mm,
            leading=14,
        ),
        "p": ParagraphStyle(
            "p",
            fontName="Helvetica",
            fontSize=8,
            textColor=INK,
            leading=11,
        ),
        "muted": ParagraphStyle(
            "muted",
            fontName="Helvetica",
            fontSize=8,
            textColor=MUTED,
            leading=11,
        ),
        "cell": ParagraphStyle(
            "cell",
            fontName="Helvetica",
            fontSize=7.5,
            textColor=INK,
            leading=9.5,
            alignment=TA_LEFT,
        ),
        "cellBold": ParagraphStyle(
            "cellBold",
            fontName="Helvetica-Bold",
            fontSize=7.5,
            textColor=INK,
            leading=9.5,
            alignment=TA_LEFT,
        ),
        "dont": ParagraphStyle(
            "dont",
            fontName="Helvetica-Oblique",
            fontSize=7,
            textColor=MUTED,
            leading=9,
            leftIndent=8,
        ),
        "num": ParagraphStyle(
            "num",
            fontName="Helvetica",
            fontSize=7.5,
            textColor=INK,
            leading=9.5,
            alignment=TA_RIGHT,
        ),
        "numBold": ParagraphStyle(
            "numBold",
            fontName="Helvetica-Bold",
            fontSize=7.5,
            textColor=INK,
            leading=9.5,
            alignment=TA_RIGHT,
        ),
        "th": ParagraphStyle(
            "th",
            fontName="Helvetica-Bold",
            fontSize=7,
            textColor=HEAD_FG,
            leading=9,
            alignment=TA_CENTER,
        ),
        "thLeft": ParagraphStyle(
            "thLeft",
            fontName="Helvetica-Bold",
            fontSize=7,
            textColor=HEAD_FG,
            leading=9,
            alignment=TA_LEFT,
        ),
    }


def _cover(payload: dict, currency: str) -> list:
    s = _styles()
    entity = payload.get("entity") or {}
    going = "Retenue" if payload.get("going_concern") else "Non retenue"
    rows = [
        ("Dénomination", entity.get("name")),
        ("Sigle", entity.get("acronym")),
        ("Pays du siège", entity.get("country_label") or entity.get("country_code")),
        ("RCCM", entity.get("rccm")),
        ("NIF", entity.get("tax_id")),
        ("Forme juridique", entity.get("legal_form_label")),
        ("Régime fiscal", entity.get("tax_regime_label")),
        ("NAEMA", entity.get("naema_code")),
        ("Adresse", ", ".join(p for p in [entity.get("address"), entity.get("postal_code"), entity.get("city")] if p)),
        ("Téléphone", entity.get("phone")),
        ("Courriel", entity.get("email")),
        ("Activité", entity.get("activity_label")),
        ("Exercice du", entity.get("starts_on")),
        ("au", entity.get("ends_on")),
        ("Durée (mois)", entity.get("duration_months")),
        ("Continuité d'exploitation", going),
        ("Signataire", " · ".join(p for p in [entity.get("signatory_name"), entity.get("signatory_title")] if p)),
        ("Expert-comptable", " · ".join(p for p in [entity.get("auditor_name"), entity.get("auditor_order_no")] if p)),
    ]
    cells = []
    for label, value in rows:
        if value in (None, ""):
            continue
        cells.append(
            [
                Paragraph(pdf_text(str(label)), s["muted"]),
                Paragraph(pdf_text(str(value)), s["p"]),
            ]
        )
    table = Table(cells, colWidths=[55 * mm, 190 * mm])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    smt = payload.get("regime") == "smt"
    if smt:
        note = (
            f"Liasse du systeme minimal de tresorerie : situation patrimoniale et etat de "
            f"tresorerie (recettes / depenses, classe 5). Devise {currency}. "
            f"Arrete au plus tard le {payload.get('arrete_due_on') or '—'} ; "
            f"AGO avant le {payload.get('ago_due_on') or '—'}. "
            "Inventaire de fin d'exercice (art. 13). Colonne N-1 comparative. "
            "Notes annexes jointes en fin de liasse (statut A)."
        )
        extra = (payload.get("smt") or {}).get("warning") or ""
        if extra:
            note += " " + extra
    else:
        note = (
            f"Liasse du systeme normal : bilan AD-DZ, compte de resultat TA-XI, TFT ZA-ZH, "
            f"notes annexes 1-36. Devise {currency}. Arrete au plus tard le "
            f"{payload.get('arrete_due_on') or '—'} ; "
            f"AGO avant le {payload.get('ago_due_on') or '—'}. "
            "Le bilan est presente avant affectation. Colonne N-1 issue de l'exercice precedent "
            "(ou des soldes d'ouverture). Notes de statut A jointes ; N/A non jointes (fiche R4)."
        )
    if payload.get("bilan") and not payload["bilan"].get("balanced", True):
        note += " Attention : total actif (BZ) different du total passif (DZ)."
    return [
        Paragraph("Identite de l'entite (Titre IX ch. 1-2)", s["h"]),
        table,
        Spacer(1, 6 * mm),
        Paragraph(pdf_text(note), s["muted"]),
    ]


def _bilan_flow(payload: dict, currency: str, prior) -> list:
    s = _styles()
    bilan = payload.get("bilan") or {}
    smt = payload.get("regime") == "smt"
    title_actif = "Actif" if not smt else "Actif (situation patrimoniale)"
    title_passif = "Passif" if not smt else "Passif (situation patrimoniale)"
    flow = [Paragraph(title_actif, s["h"]), _statement_table(bilan.get("actif") or [], currency, prior, show_gross=not smt)]
    flow.append(Spacer(1, 5 * mm))
    flow.append(Paragraph(title_passif, s["h"]))
    flow.append(_statement_table(bilan.get("passif") or [], currency, prior, show_gross=False))
    if bilan and not bilan.get("balanced", True):
        flow.append(Spacer(1, 3 * mm))
        msg = "Situation non equilibree." if smt else "Bilan non equilibre : BZ different de DZ."
        flow.append(Paragraph(msg, s["muted"]))
    return flow


def _result_flow(payload: dict, currency: str, prior) -> list:
    s = _styles()
    result = payload.get("result") or {}
    return [
        Paragraph("Compte de resultat (signes du modele, SIG XA-XI)", s["h"]),
        _statement_table(result.get("lines") or [], currency, prior, show_gross=False),
    ]


def _tft_flow(payload: dict, currency: str, prior) -> list:
    s = _styles()
    tft = payload.get("tft") or {}
    title = (
        "Etat de tresorerie (recettes et depenses)"
        if payload.get("regime") == "smt"
        else "Tableau des flux de tresorerie (methode indirecte, CAFG)"
    )
    return [
        Paragraph(title, s["h"]),
        _statement_table(tft.get("lines") or [], currency, prior, show_gross=False),
    ]


def _xml(value) -> str:
    text = pdf_text(value)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _note_status(note: dict) -> str:
    if int(note.get("number") or 0) == 2 or note.get("required"):
        return "A"
    status = str(note.get("status") or "NA").upper()
    return "A" if status == "A" else "NA"


def _note_attached(note: dict) -> bool:
    return _note_status(note) == "A"


def _notes_flow(payload: dict) -> list:
    s = _styles()
    notes = list(payload.get("notes") or [])
    smt = payload.get("regime") == "smt"
    title = "Notes annexes SMT" if smt else "Notes annexes (Titre IX ch. 6)"
    intro = (
        "Les notes font partie des etats financiers (art. 8). Note 2 obligatoire. "
        "Statut A = jointe, N/A = non jointe (fiche R4). Une information en notes ne "
        "remplace pas une inscription au bilan ou au compte de resultat."
    )
    if smt:
        intro += (
            " Le SMT de l'acte prevoit quatre notes (Titre X ch. 3) ; ce dossier reprend "
            "le canevas SN 1-36 tant que les notes 1-4 SMT ne sont pas separees."
        )
    flow = [
        Paragraph(title, s["h"]),
        Paragraph(pdf_text(intro), s["muted"]),
        Spacer(1, 3 * mm),
        Paragraph("Sommaire (fiche R4)", s["h"]),
    ]
    if not notes:
        flow.append(Paragraph("Aucune note saisie pour cet exercice.", s["muted"]))
        return flow

    usable = landscape(A4)[0] - 28 * mm
    header = [
        Paragraph("N°", s["thLeft"]),
        Paragraph("Intitule", s["thLeft"]),
        Paragraph("Statut", s["th"]),
    ]
    rows = [header]
    for note in notes:
        status = _note_status(note)
        rows.append(
            [
                Paragraph(pdf_text(str(note.get("number") or "")), s["cellBold"]),
                Paragraph(_xml(note.get("title") or ""), s["cell"]),
                Paragraph("A" if status == "A" else "N/A", s["cell"] if status != "A" else s["cellBold"]),
            ]
        )
    sommaire = Table(rows, colWidths=[18 * mm, usable - 40 * mm, 22 * mm], repeatRows=1)
    sommaire.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), INK),
                ("TEXTCOLOR", (0, 0), (-1, 0), HEAD_FG),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("LINEBELOW", (0, 1), (-1, -1), 0.25, RULE),
            ]
        )
    )
    flow.append(sommaire)
    flow.append(Spacer(1, 5 * mm))
    flow.append(Paragraph("Notes jointes (statut A)", s["h"]))

    attached = [note for note in notes if _note_attached(note)]
    if not attached:
        flow.append(Paragraph("Aucune note de statut A a joindre.", s["muted"]))
        return flow

    for note in attached:
        number = note.get("number")
        flow.append(Spacer(1, 2 * mm))
        flow.append(Paragraph(_xml(f"Note {number} — {note.get('title') or ''}"), s["h"]))
        if int(number or 0) == 2:
            blocks = [
                (NOTE2_SECTION_LABEL, note.get("conformity")),
                ("B. Regles et methodes", note.get("methods")),
                ("C. Derogations", note.get("derogations")),
                ("D. Informations complementaires", note.get("extra") or note.get("body")),
            ]
            for label, value in blocks:
                flow.append(Paragraph(pdf_text(label), s["cellBold"]))
                flow.append(
                    Paragraph(_xml(value) if str(value or "").strip() else "Neant.", s["p"])
                )
                flow.append(Spacer(1, 1.5 * mm))
            continue
        computed = str(note.get("computed") or "").strip()
        body = str(note.get("body") or "").strip()
        if computed:
            flow.append(Paragraph(_xml(computed), s["p"]))
        if body:
            flow.append(Paragraph(_xml(body), s["p"]))
        if not computed and not body:
            flow.append(Paragraph("Jointe sans developpement chiffre.", s["muted"]))
    return flow


def _display_code(code: str) -> str:
    if not code or "_" in code:
        return ""
    return code


def _amount_cell(value, currency: str, bold: bool, styles: dict) -> Paragraph:
    text = format_amount_fr(value, currency)
    return Paragraph(pdf_text(text), styles["numBold"] if bold else styles["num"])


def _label_cell(line: dict, styles: dict) -> Paragraph:
    code = _display_code(str(line.get("code") or ""))
    label = pdf_text(line.get("label") or "")
    kind = line.get("kind") or ""
    bold = bool(line.get("bold") or kind in {"heading", "total", "sig"})
    body = f"<font face='Courier' size='6.5' color='#5C6560'>{pdf_text(code)}</font>  {label}" if code else label
    if kind == "dont":
        return Paragraph(body, styles["dont"])
    return Paragraph(body, styles["cellBold"] if bold else styles["cell"])


def _statement_table(lines: list[dict], currency: str, prior, *, show_gross: bool) -> Table:
    styles = _styles()
    with_gross = show_gross and any(line.get("gross") is not None for line in lines)
    prior_h = f"Net N-1 ({prior})" if prior else "Net N-1"
    header = [Paragraph("Poste", styles["thLeft"])]
    if with_gross:
        header.extend(
            [
                Paragraph("Brut", styles["th"]),
                Paragraph("Amort. et dep.", styles["th"]),
            ]
        )
    header.extend(
        [
            Paragraph("Net N", styles["th"]),
            Paragraph(pdf_text(prior_h), styles["th"]),
        ]
    )
    data = [header]
    emphasis_rows: list[int] = []
    for index, line in enumerate(lines, start=1):
        kind = line.get("kind") or ""
        bold = bool(line.get("bold") or kind in {"heading", "total", "sig"})
        row = [_label_cell(line, styles)]
        if with_gross:
            row.append(_amount_cell(line.get("gross"), currency, bold, styles))
            row.append(_amount_cell(line.get("amort"), currency, bold, styles))
        row.append(_amount_cell(line.get("current"), currency, bold, styles))
        row.append(_amount_cell(line.get("prior"), currency, bold, styles))
        data.append(row)
        if kind in {"heading", "total", "sig"}:
            emphasis_rows.append(index)

    usable = landscape(A4)[0] - 28 * mm
    if with_gross:
        col_widths = [usable - 4 * 32 * mm, 32 * mm, 32 * mm, 32 * mm, 32 * mm]
    else:
        col_widths = [usable - 2 * 38 * mm, 38 * mm, 38 * mm]
    table = Table(data, colWidths=col_widths, repeatRows=1)
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("TEXTCOLOR", (0, 0), (-1, 0), HEAD_FG),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, RULE),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
    ]
    for row in emphasis_rows:
        commands.append(("BACKGROUND", (0, row), (-1, row), BAND))
    table.setStyle(TableStyle(commands))
    return table
