from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

from django.db import connection
from django.test import Client
from ninja.errors import HttpError

from apps.identity.beta_test01.constants import (
    CLOSE_YEAR,
    COMPANY_ISOL,
    COMPANY_MAIN,
    OPERATIONS_YEAR,
    ORG_SLUG,
    SALE_AMOUNT,
)
from apps.identity.beta_test01.provision import assert_beta_database, default_password
from apps.identity.beta_test01.runner_rls import org_and_companies_for_runner
from apps.ledger.models import (
    Account,
    AccountingPeriod,
    Entry,
    EntryStatus,
    Exercise,
    ExerciseStatus,
    Journal,
)
from apps.ledger.services.balance import trial_balance, trial_balance_ytd
from apps.ledger.services.closing import allocate_result, close_exercise, preview_close
from apps.ledger.services.opening import post_opening
from apps.ledger.services.sn_map import cr_amounts
from apps.ledger.services.posting import create_draft, post_entry
from apps.ledger.services.pdf_disclaimers import PDF_BETA_DISCLAIMER_TITLE
from apps.tenancy.models import Company, Organization


def _login(client: Client, email: str) -> int:
    r = client.post(
        "/api/auth/login",
        data=json.dumps({"email": email, "password": default_password()}),
        content_type="application/json",
        REMOTE_ADDR="203.0.113.50",
    )
    return r.status_code


def _org_company() -> tuple[Organization, Company, Company]:
    return org_and_companies_for_runner()


def run_all_scenarios() -> list[dict]:
    assert_beta_database()
    org, co_main, co_isol = _org_company()
    results: list[dict] = []

    def record(sid: str, name: str, ok: bool, expected: str, got: str, extra: dict | None = None):
        results.append(
            {
                "id": sid,
                "name": name,
                "ok": ok,
                "expected": expected,
                "got": got,
                **(extra or {}),
            }
        )

    # 1 Organisation / société
    record(
        "S01",
        "Organisation et sociétés fictives",
        org.is_demo and org.setup_data == "beta-test-01",
        "org demo beta-test-01 + 2 sociétés CG/XAF",
        f"slug={org.slug} companies={Company.objects.filter(organization=org).count()}",
    )

    # 2 Plan comptable
    pcgo_count = Account.objects.filter(company=co_main, is_syscohada=True).count()
    record(
        "S02",
        "Plan comptable PCGO",
        pcgo_count > 100,
        ">100 comptes SYSCOHADA",
        str(pcgo_count),
    )

    # 3 Journaux
    journals = Journal.objects.filter(company=co_main).count()
    record("S03", "Journaux", journals >= 4, ">=4 journaux", str(journals))

    client = Client()
    owner_email = "beta-test.owner@beta-test.muhimu.local"
    assert _login(client, owner_email) == 200
    headers = {
        "HTTP_X_ORGANIZATION_SLUG": ORG_SLUG,
        "HTTP_X_COMPANY_ID": str(co_main.id),
    }

    acc521 = Account.objects.get(company=co_main, code="521")
    acc701 = Account.objects.get(company=co_main, code="701")
    journal = Journal.objects.get(company=co_main, code="OD")

    # 4 Écriture équilibrée
    draft_ok = create_draft(
        company=co_main,
        journal=journal,
        accounting_date=date(OPERATIONS_YEAR, 5, 10),
        value_date=date(OPERATIONS_YEAR, 5, 10),
        description="Test équilibrée BT01",
        document_ref="BT01-BAL-OK",
        raw_lines=[
            {"account_id": str(acc521.id), "debit": "50000", "credit": "0"},
            {"account_id": str(acc701.id), "debit": "0", "credit": "50000"},
        ],
    )
    record("S04", "Saisie équilibrée (brouillon)", draft_ok.lines.count() == 2, "2 lignes", str(draft_ok.lines.count()))

    # 5 Refus déséquilibrée
    unbal_status = "error"
    try:
        create_draft(
            company=co_main,
            journal=journal,
            accounting_date=date(OPERATIONS_YEAR, 5, 11),
            value_date=None,
            description="Test déséquilibrée",
            document_ref="BT01-BAD",
            raw_lines=[
                {"account_id": str(acc521.id), "debit": "100", "credit": "0"},
                {"account_id": str(acc701.id), "debit": "0", "credit": "50"},
            ],
        )
        unbal_status = "accepted"
    except HttpError:
        unbal_status = "HttpError"
    except Exception as exc:  # noqa: BLE001
        unbal_status = type(exc).__name__
    record("S05", "Refus écriture déséquilibrée", unbal_status != "accepted", "rejet", unbal_status)

    # 6 Validation
    posted = post_entry(draft_ok, None)
    record(
        "S06",
        "Validation écriture",
        posted.status == EntryStatus.POSTED,
        "POSTED",
        posted.status,
    )

    # 7 Immutabilité POSTED (API PATCH)
    r7 = client.delete(f"/api/ledger/entries/{posted.id}", **headers)
    record("S07", "Suppression POSTED refusée", r7.status_code == 409, "409", str(r7.status_code))

    # 8 Grand livre
    r8 = client.get(f"/api/ledger/general-ledger/{acc701.id}", **headers)
    record("S08", "Grand livre", r8.status_code == 200, "200", str(r8.status_code))

    # 9 Balance
    period_m5 = AccountingPeriod.objects.get(company=co_main, year=OPERATIONS_YEAR, month=5)
    tb = trial_balance(co_main, period_m5)
    total_d = sum((Decimal(row["mov_debit"]) for row in tb), Decimal("0"))
    total_c = sum((Decimal(row["mov_credit"]) for row in tb), Decimal("0"))
    record(
        "S09",
        "Balance équilibrée",
        total_d == total_c and total_d > 0,
        f"D=C>0 (attendu incl. vente {SALE_AMOUNT})",
        f"D={total_d} C={total_c}",
    )

    # 10 PDF
    r10 = client.get("/api/ledger/statements/pdf?kind=bilan", **headers)
    pdf_ok = r10.status_code == 200 and PDF_BETA_DISCLAIMER_TITLE.encode("latin-1", "replace") in r10.content
    record("S10", "PDF + disclaimer", pdf_ok, "200 + DOCUMENT DE TEST", str(r10.status_code))

    # 11 Permissions viewer
    viewer = Client()
    _login(viewer, "beta-test.viewer@beta-test.muhimu.local")
    r11 = viewer.post(
        f"/api/ledger/entries/{draft_ok.id}/post",
        data="{}",
        content_type="application/json",
        HTTP_X_ORGANIZATION_SLUG=ORG_SLUG,
        HTTP_X_COMPANY_ID=str(co_main.id),
    )
    record("S11", "Viewer ne peut pas valider", r11.status_code == 403, "403", str(r11.status_code))

    # 12 Isolation sociétés
    r12a = client.get(
        "/api/ledger/entries",
        HTTP_X_ORGANIZATION_SLUG=ORG_SLUG,
        HTTP_X_COMPANY_ID=str(co_isol.id),
    )
    isol_client = Client()
    _login(isol_client, "beta-test.isol@beta-test.muhimu.local")
    r12b = isol_client.get(
        "/api/ledger/entries",
        HTTP_X_ORGANIZATION_SLUG=ORG_SLUG,
        HTTP_X_COMPANY_ID=str(co_main.id),
    )
    record(
        "S12",
        "Isolation inter-sociétés",
        r12a.status_code == 200 and r12b.status_code in (400, 403, 404),
        "owner voit B ; isol_user pas A (400/403)",
        f"owner_isol={r12a.status_code} isol_main={r12b.status_code}",
    )

    # 13 BETA-SCOPE authentifié
    r13a = client.get("/api/ledger/consolidation", **headers)
    r13b = client.get("/api/ledger/beta-scope", HTTP_X_ORGANIZATION_SLUG=ORG_SLUG)
    scope = r13b.json() if r13b.status_code == 200 else {}
    record(
        "S13",
        "API fonctionnalités exclues",
        r13a.status_code == 403
        and r13b.status_code == 200
        and scope.get("consolidation") is False,
        "403 consolidation + flags false",
        f"consolidation={r13a.status_code} beta-scope={r13b.status_code} scope={scope}",
    )

    # 14 Clôture 2025 (exercice dédié)
    ex25 = Exercise.objects.get(company=co_main, year=CLOSE_YEAR)
    close_ok = False
    close_detail = ""
    if ex25.status == ExerciseStatus.OPEN:
        try:
            prev = preview_close(co_main, ex25)
            if not prev["can_close"]:
                close_detail = ";".join(prev["blockers"])
            else:
                close_exercise(co_main, ex25, None)
                ex25.refresh_from_db()
                net = ex25.net_result or Decimal("0")
                if net > 0:
                    legal = prev["suggested_legal_reserve"]
                    retained = prev["suggested_retained"]
                    allocate_result(
                        co_main,
                        ex25,
                        None,
                        {
                            "approved_on": date(CLOSE_YEAR + 1, 3, 1),
                            "legal_reserve": str(legal),
                            "free_reserve": "0",
                            "retained": str(retained),
                            "dividends": "0",
                        },
                    )
                ex26 = Exercise.objects.get(company=co_main, year=CLOSE_YEAR + 1)
                rows_ytd = trial_balance_ytd(co_main, ex25)
                xi = cr_amounts(rows_ytd).get("XI", Decimal("0"))
                if xi > 0:
                    post_opening(
                        co_main,
                        ex26,
                        None,
                        [
                            {"code": "521", "debit": "400000", "credit": "0"},
                            {"code": "401", "debit": "0", "credit": "200000"},
                            {"code": "131", "debit": "0", "credit": str(xi)},
                        ],
                    )
                close_ok = ex25.status == ExerciseStatus.CLOSED
                close_detail = f"status={ex25.status} net={net}"
        except Exception as exc:  # noqa: BLE001
            close_detail = str(exc)
    else:
        close_detail = f"already {ex25.status}"
        close_ok = ex25.status == ExerciseStatus.CLOSED
    record(
        "S14",
        "Clôture / affectation / AN 2025",
        close_ok,
        "exercice 2025 CLOSED",
        close_detail,
    )

    # Sécurité — triggers
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT count(*) FROM pg_trigger t
            JOIN pg_class c ON t.tgrelid = c.oid
            WHERE NOT tgisinternal AND c.relname IN ('ledger_entry', 'ledger_entryline')
            """
        )
        trig = cur.fetchone()[0]
    record("SEC01", "Triggers ACC-03", trig == 4, "4", str(trig))

    # RLS spot
    with connection.cursor() as cur:
        cur.execute(
            "SELECT relrowsecurity FROM pg_class WHERE relname = 'ledger_entry'"
        )
        rls = cur.fetchone()[0]
    record("SEC02", "RLS ledger_entry", rls is True, "true", str(rls))

    # Escompte POST refus
    acc415 = Account.objects.filter(company=co_main, code="4151").first()
    if not acc415:
        parent = Account.objects.filter(company=co_main, code="415").first()
        acc415 = Account.objects.create(
            organization=org,
            company=co_main,
            code="4151",
            label="Effets à encaisser (test)",
            is_postable=True,
            is_syscohada=False,
            parent=parent,
        )
    if acc415:
        escompte_draft = create_draft(
            company=co_main,
            journal=journal,
            accounting_date=date(OPERATIONS_YEAR, 6, 1),
            value_date=None,
            description="Escompte test",
            document_ref="BT01-ESC",
            raw_lines=[
                {"account_id": str(acc415.id), "debit": "1000", "credit": "0"},
                {"account_id": str(acc521.id), "debit": "0", "credit": "1000"},
            ],
        )
        r_esc = client.post(
            f"/api/ledger/entries/{escompte_draft.id}/post",
            content_type="application/json",
            data="{}",
            **headers,
        )
        record("SEC03", "Escompte refusé (403)", r_esc.status_code == 403, "403", str(r_esc.status_code))
    else:
        record("SEC03", "Escompte refusé", True, "403", "4151 absent — skip")

    # R0+R2 pas de reopen
    import apps.ledger.services.closing as closing_mod

    record(
        "SEC04",
        "Pas de réouverture self-service",
        not hasattr(closing_mod, "reopen_exercise"),
        "reopen_exercise absent",
        "absent" if not hasattr(closing_mod, "reopen_exercise") else "present",
    )

    return results
