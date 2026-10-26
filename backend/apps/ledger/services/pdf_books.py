"""PDF livres légaux — journal, grand-livre, balance, inventaire (art. 19, 22, 66–67)."""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO

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

from apps.ledger.models import (
    Account,
    AccountingPeriod,
    Entry,
    EntryStatus,
    InventoryCampaign,
    InventoryStatus,
)
from apps.ledger.money import format_amount_fr
from apps.ledger.services.balance import general_ledger, trial_balance
from apps.ledger.services.pdf_disclaimers import PDF_FOOTER_LEFT
from apps.ledger.services.pdf_statements import (
    BAND,
    HEAD_FG,
    INK,
    MUTED,
    RULE,
    pdf_text,
    _beta_disclaimer_block,
)

BOOK_KINDS = ("journal", "ledger", "balance", "inventory", "all")
ZERO = Decimal("0")


def books_filename(period: AccountingPeriod, kind: str) -> str:
    names = {
        "journal": "livre-journal",
        "ledger": "grand-livre",
        "balance": "balance",
        "inventory": "livre-inventaire",
        "all": "livres-legaux",
    }
    return f"{names.get(kind, 'livre')}-{period.year}-{period.month:02d}.pdf"


def render_books_pdf(company, period: AccountingPeriod, kind: str = "all") -> bytes:
    kind = (kind or "all").lower()
    if kind not in BOOK_KINDS:
        raise ValueError("Livre PDF inconnu (journal, ledger, balance, inventory ou all).")

    pagesize = landscape(A4) if kind in {"balance", "all"} else A4
    if kind == "all":
        pagesize = A4
    currency = (company.currency_code or "XOF").upper()
    entity_name = company.legal_name or company.name
    stamp = period.ends_on.isoformat()
    titles = {
        "journal": "Livre-journal",
        "ledger": "Grand-livre",
        "balance": "Balance des comptes",
        "inventory": "Livre d'inventaire",
        "all": "Livres legales (art. 19)",
    }

    def draw_chrome(canvas, doc):
        canvas.saveState()
        width, height = pagesize
        canvas.setFillColor(INK)
        canvas.rect(0, height - 6 * mm, width, 6 * mm, fill=1, stroke=0)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(doc.leftMargin, height - 14 * mm, pdf_text(entity_name))
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(width - doc.rightMargin, height - 14 * mm, pdf_text(f"Devise {currency}"))
        canvas.setFont("Helvetica-Bold", 12)
        canvas.drawString(doc.leftMargin, height - 22 * mm, pdf_text(titles[kind] if kind != "all" else titles["all"]))
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(
            doc.leftMargin,
            height - 28 * mm,
            pdf_text(
                f"Periode {period.year}-{period.month:02d}  |  "
                f"{period.starts_on.isoformat()} - {period.ends_on.isoformat()}  |  "
                f"Etablis le {stamp}"
            ),
        )
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.4)
        canvas.line(doc.leftMargin, height - 31 * mm, width - doc.rightMargin, height - 31 * mm)
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 7)
        canvas.drawString(
            doc.leftMargin,
            10 * mm,
            pdf_text(PDF_FOOTER_LEFT),
        )
        canvas.drawRightString(width - doc.rightMargin, 10 * mm, str(canvas.getPageNumber()))
        canvas.restoreState()

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=pagesize,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=36 * mm,
        bottomMargin=16 * mm,
        title=pdf_text(f"{titles[kind]} {period.year}-{period.month:02d}"),
        author="Muhimu ERP",
        pageCompression=0,
    )
    story: list = []
    story.extend(_beta_disclaimer_block())
    if kind == "all":
        story.extend(_journal_flow(company, period, currency))
        story.append(PageBreak())
        story.extend(_ledger_flow(company, period, currency))
        story.append(PageBreak())
        story.extend(_balance_flow(company, period, currency))
        story.append(PageBreak())
        story.extend(_inventory_flow(company, period, currency))
    elif kind == "journal":
        story.extend(_journal_flow(company, period, currency))
    elif kind == "ledger":
        story.extend(_ledger_flow(company, period, currency))
    elif kind == "balance":
        story.extend(_balance_flow(company, period, currency))
    else:
        story.extend(_inventory_flow(company, period, currency))

    doc.build(story, onFirstPage=draw_chrome, onLaterPages=draw_chrome)
    return buffer.getvalue()


def _styles():
    return {
        "h": ParagraphStyle(
            "bh",
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=INK,
            spaceBefore=2 * mm,
            spaceAfter=3 * mm,
            leading=13,
        ),
        "p": ParagraphStyle(
            "bp",
            fontName="Helvetica",
            fontSize=8,
            textColor=INK,
            leading=11,
        ),
        "muted": ParagraphStyle(
            "bm",
            fontName="Helvetica",
            fontSize=8,
            textColor=MUTED,
            leading=11,
        ),
        "cell": ParagraphStyle(
            "bc",
            fontName="Helvetica",
            fontSize=7,
            textColor=INK,
            leading=9,
            alignment=TA_LEFT,
        ),
        "cellBold": ParagraphStyle(
            "bcb",
            fontName="Helvetica-Bold",
            fontSize=7,
            textColor=INK,
            leading=9,
            alignment=TA_LEFT,
        ),
        "num": ParagraphStyle(
            "bn",
            fontName="Helvetica",
            fontSize=7,
            textColor=INK,
            leading=9,
            alignment=TA_RIGHT,
        ),
        "numBold": ParagraphStyle(
            "bnb",
            fontName="Helvetica-Bold",
            fontSize=7,
            textColor=INK,
            leading=9,
            alignment=TA_RIGHT,
        ),
        "th": ParagraphStyle(
            "bth",
            fontName="Helvetica-Bold",
            fontSize=6.5,
            textColor=HEAD_FG,
            leading=8.5,
            alignment=TA_CENTER,
        ),
        "thLeft": ParagraphStyle(
            "bthl",
            fontName="Helvetica-Bold",
            fontSize=6.5,
            textColor=HEAD_FG,
            leading=8.5,
            alignment=TA_LEFT,
        ),
    }


def _amt(value, currency, styles, bold=False):
    key = "numBold" if bold else "num"
    return Paragraph(pdf_text(format_amount_fr(value, currency)), styles[key])


def _txt(value, styles, bold=False):
    key = "cellBold" if bold else "cell"
    return Paragraph(pdf_text(value or ""), styles[key])


def _th(labels: list[tuple[str, bool]], styles) -> list:
    return [
        Paragraph(pdf_text(label), styles["thLeft"] if left else styles["th"])
        for label, left in labels
    ]


def _style_table(table: Table, header=True) -> Table:
    cmds = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("LINEBELOW", (0, 1), (-1, -1), 0.2, RULE),
    ]
    if header:
        cmds.extend(
            [
                ("BACKGROUND", (0, 0), (-1, 0), INK),
                ("TEXTCOLOR", (0, 0), (-1, 0), HEAD_FG),
                ("TOPPADDING", (0, 0), (-1, 0), 3),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 3),
            ]
        )
    table.setStyle(TableStyle(cmds))
    return table


def _posted_entries(company, period: AccountingPeriod):
    return (
        Entry.objects.filter(company=company, status=EntryStatus.POSTED, period=period)
        .select_related("journal")
        .prefetch_related("lines__account")
        .order_by("accounting_date", "number", "id")
    )


def _journal_flow(company, period: AccountingPeriod, currency: str) -> list:
    s = _styles()
    entries = list(_posted_entries(company, period))
    flow = [
        Paragraph("Livre-journal", s["h"]),
        Paragraph(
            pdf_text(
                "Enregistrement chronologique des ecritures validees (art. 17-2, 19). "
                "Les brouillons sont exclus. Contrepassation en negatif (art. 20)."
            ),
            s["muted"],
        ),
        Spacer(1, 3 * mm),
    ]
    widths = [22 * mm, 28 * mm, 14 * mm, 22 * mm, 56 * mm, 20 * mm, 20 * mm]
    header = _th(
        [
            ("Date", True),
            ("N°", True),
            ("Jnl", True),
            ("Compte", True),
            ("Libelle", True),
            ("Debit", False),
            ("Credit", False),
        ],
        s,
    )
    rows = [header]
    total_d = ZERO
    total_c = ZERO
    for entry in entries:
        lines = list(entry.lines.all())
        first = True
        for line in lines:
            total_d += line.debit
            total_c += line.credit
            rows.append(
                [
                    _txt(entry.accounting_date.isoformat() if first else "", s),
                    _txt(entry.number_display if first else "", s, bold=first),
                    _txt(entry.journal.code if first else "", s),
                    _txt(line.account.code, s, bold=True),
                    _txt(line.label or entry.description, s),
                    _amt(line.debit, currency, s) if line.debit else _txt("", s),
                    _amt(line.credit, currency, s) if line.credit else _txt("", s),
                ]
            )
            first = False
    if len(rows) == 1:
        flow.append(Paragraph("Aucune ecriture validee sur cette periode.", s["muted"]))
        return flow
    rows.append(
        [
            _txt("", s),
            _txt("", s),
            _txt("", s),
            _txt("", s),
            _txt("Totaux", s, bold=True),
            _amt(total_d, currency, s, bold=True),
            _amt(total_c, currency, s, bold=True),
        ]
    )
    table = Table(rows, colWidths=widths, repeatRows=1)
    _style_table(table)
    table.setStyle(TableStyle([("BACKGROUND", (0, -1), (-1, -1), BAND)]))
    flow.append(table)
    return flow


def _ledger_flow(company, period: AccountingPeriod, currency: str) -> list:
    s = _styles()
    flow = [
        Paragraph("Grand-livre", s["h"]),
        Paragraph(
            pdf_text(
                "Compte par compte, soldes d'ouverture de periode puis mouvements valides. "
                "Le solde courant est debiteur s'il est positif."
            ),
            s["muted"],
        ),
    ]
    accounts = Account.objects.filter(company=company, is_postable=True, is_active=True).order_by("code")
    printed = 0
    widths = [22 * mm, 22 * mm, 78 * mm, 24 * mm, 24 * mm, 24 * mm]
    header = _th(
        [
            ("Date", True),
            ("N°", True),
            ("Libelle", True),
            ("Debit", False),
            ("Credit", False),
            ("Solde", False),
        ],
        s,
    )
    for account in accounts:
        gl = general_ledger(company, account, period)
        if not gl["lines"] and gl["open_debit"] == 0 and gl["open_credit"] == 0:
            continue
        printed += 1
        flow.append(Spacer(1, 3 * mm))
        flow.append(Paragraph(pdf_text(f"{account.code}  {account.label}"), s["h"]))
        rows = [header]
        open_net = gl["open_debit"] - gl["open_credit"]
        rows.append(
            [
                _txt(period.starts_on.isoformat(), s),
                _txt("—", s),
                _txt("Solde d'ouverture", s, bold=True),
                _amt(gl["open_debit"], currency, s) if gl["open_debit"] else _txt("", s),
                _amt(gl["open_credit"], currency, s) if gl["open_credit"] else _txt("", s),
                _amt(open_net, currency, s, bold=True),
            ]
        )
        for line in gl["lines"]:
            rows.append(
                [
                    _txt(line["accounting_date"], s),
                    _txt(line["number_display"], s),
                    _txt(line["label"], s),
                    _amt(line["debit"], currency, s) if line["debit"] else _txt("", s),
                    _amt(line["credit"], currency, s) if line["credit"] else _txt("", s),
                    _amt(line["balance"], currency, s),
                ]
            )
        table = Table(rows, colWidths=widths, repeatRows=1)
        _style_table(table)
        flow.append(table)
    if printed == 0:
        flow.append(Spacer(1, 3 * mm))
        flow.append(Paragraph("Aucun mouvement sur cette periode.", s["muted"]))
    return flow


def _balance_flow(company, period: AccountingPeriod, currency: str) -> list:
    s = _styles()
    flow = [
        Paragraph("Balance des comptes", s["h"]),
        Paragraph(
            pdf_text("Soldes d'ouverture, mouvements de la periode et soldes de cloture (snapshots)."),
            s["muted"],
        ),
        Spacer(1, 3 * mm),
    ]
    rows_data = trial_balance(company, period)
    widths = [20 * mm, 54 * mm, 18 * mm, 18 * mm, 18 * mm, 18 * mm, 18 * mm, 18 * mm]
    header = _th(
        [
            ("Compte", True),
            ("Intitule", True),
            ("Ouv. D", False),
            ("Ouv. C", False),
            ("Mvt D", False),
            ("Mvt C", False),
            ("Clot. D", False),
            ("Clot. C", False),
        ],
        s,
    )
    rows = [header]
    totals = {
        "open_debit": ZERO,
        "open_credit": ZERO,
        "mov_debit": ZERO,
        "mov_credit": ZERO,
        "close_debit": ZERO,
        "close_credit": ZERO,
    }
    for item in rows_data:
        for key in totals:
            totals[key] += item[key]
        rows.append(
            [
                _txt(item["code"], s, bold=True),
                _txt(item["label"], s),
                _amt(item["open_debit"], currency, s),
                _amt(item["open_credit"], currency, s),
                _amt(item["mov_debit"], currency, s),
                _amt(item["mov_credit"], currency, s),
                _amt(item["close_debit"], currency, s),
                _amt(item["close_credit"], currency, s),
            ]
        )
    if len(rows) == 1:
        flow.append(Paragraph("Balance vide sur cette periode.", s["muted"]))
        return flow
    rows.append(
        [
            _txt("", s),
            _txt("Totaux", s, bold=True),
            _amt(totals["open_debit"], currency, s, bold=True),
            _amt(totals["open_credit"], currency, s, bold=True),
            _amt(totals["mov_debit"], currency, s, bold=True),
            _amt(totals["mov_credit"], currency, s, bold=True),
            _amt(totals["close_debit"], currency, s, bold=True),
            _amt(totals["close_credit"], currency, s, bold=True),
        ]
    )
    table = Table(rows, colWidths=widths, repeatRows=1)
    _style_table(table)
    table.setStyle(TableStyle([("BACKGROUND", (0, -1), (-1, -1), BAND)]))
    flow.append(table)
    return flow


def _inventory_flow(company, period: AccountingPeriod, currency: str) -> list:
    s = _styles()
    flow = [
        Paragraph("Livre d'inventaire", s["h"]),
        Paragraph(
            pdf_text(
                "Transcription de l'inventaire de fin de periode (art. 16, 19, 66). "
                "Le bilan, le compte de resultat et le TFT se telechargent depuis Etats financiers."
            ),
            s["muted"],
        ),
        Spacer(1, 3 * mm),
    ]
    campaigns = list(
        InventoryCampaign.objects.filter(
            company=company,
            exercise=period.exercise,
            status=InventoryStatus.CLOSED,
            inventoried_on__lte=period.ends_on,
        )
        .prefetch_related("lines__account")
        .order_by("inventoried_on")
    )
    if not campaigns:
        flow.append(
            Paragraph(
                "Aucun inventaire physique cloture sur l'exercice. "
                "L'etat des comptes ci-dessous tient lieu d'inventaire comptable.",
                s["muted"],
            )
        )
        flow.append(Spacer(1, 3 * mm))
    for campaign in campaigns:
        lines = list(campaign.lines.all())
        total = sum((line.amount for line in lines), ZERO)
        flow.append(
            Paragraph(
                pdf_text(
                    f"Inventaire physique du {campaign.inventoried_on.isoformat()} — "
                    f"{len(lines)} poste(s), methode {campaign.method.upper()}, "
                    f"total {format_amount_fr(total, currency)} {currency}."
                ),
                s["p"],
            )
        )
        if campaign.notes:
            flow.append(Paragraph(pdf_text(campaign.notes), s["muted"]))
        header = _th(
            [
                ("Compte", True),
                ("Designation", True),
                ("Qte", False),
                ("Unite", True),
                ("P.U.", False),
                ("Montant", False),
            ],
            s,
        )
        rows = [header]
        for line in lines:
            rows.append(
                [
                    _txt(line.account.code if line.account_id else "", s, bold=True),
                    _txt(line.description, s),
                    _txt(format(line.quantity, "f"), s),
                    _txt(line.unit, s),
                    _amt(line.unit_value, currency, s),
                    _amt(line.amount, currency, s),
                ]
            )
        if len(rows) > 1:
            rows.append(
                [
                    _txt("", s),
                    _txt("Total inventaire", s, bold=True),
                    _txt("", s),
                    _txt("", s),
                    _txt("", s),
                    _amt(total, currency, s, bold=True),
                ]
            )
            table = Table(rows, colWidths=[22 * mm, 70 * mm, 22 * mm, 18 * mm, 22 * mm, 28 * mm], repeatRows=1)
            _style_table(table)
            table.setStyle(TableStyle([("BACKGROUND", (0, -1), (-1, -1), BAND)]))
            flow.append(Spacer(1, 2 * mm))
            flow.append(table)
        flow.append(Spacer(1, 4 * mm))

    flow.append(Paragraph("Etat d'inventaire des comptes (soldes de cloture)", s["h"]))
    flow.extend(_balance_flow(company, period, currency)[2:])
    return flow
