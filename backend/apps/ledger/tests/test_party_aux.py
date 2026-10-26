from unittest import TestCase as UnitTestCase

from ninja.errors import HttpError

from apps.ledger.services.lettering import (
    account_root,
    auxiliary_code,
    bind_party_account,
    create_party,
    is_subdivision,
)
from apps.ledger.tests.db import LedgerDbTestCase


class AuxiliaryCodeTests(UnitTestCase):
    def test_builds_411_cli_and_sococim(self):
        self.assertEqual(auxiliary_code("411", "CLI-0001", set()), "411-CLI-0001")
        self.assertEqual(auxiliary_code("401", "SOCOCIM", set()), "401-SOCOCIM")
        self.assertEqual(auxiliary_code("411", "CLI-0001", {"411-CLI-0001"}), "411-CLI-0001-2")

    def test_root_groups_aux_with_collective(self):
        self.assertEqual(account_root("411-CLI-0001"), "411")
        self.assertEqual(account_root("4118"), "411")
        self.assertEqual(account_root("401-FOU-0001"), "401")
        self.assertTrue(is_subdivision("411-CLI-0001"))
        self.assertFalse(is_subdivision("411"))


class DummyAccount:
    def __init__(self, code):
        self.code = code


class DummyParty:
    def __init__(self, code):
        self.account_id = "x"
        self.account = DummyAccount(code)


class BindPartyAccountTests(UnitTestCase):
    def test_swaps_collective_for_aux(self):
        chosen = DummyAccount("411")
        party = DummyParty("411-CLI-0001")
        bound = bind_party_account(chosen, party)
        self.assertEqual(bound.code, "411-CLI-0001")

    def test_does_not_swap_other_class(self):
        chosen = DummyAccount("401")
        party = DummyParty("411-CLI-0001")
        self.assertEqual(bind_party_account(chosen, party).code, "401")


class CreatePartyAuxTests(LedgerDbTestCase):
    def test_customer_gets_411_aux(self):
        party = create_party(self.company, {"name": "SOCOCIM", "kind": "customer", "reference": "SOCOCIM"})
        self.assertEqual(party.account.code, "411-SOCOCIM")
        self.assertEqual(party.account.parent_id, self.acc411.id)
        self.assertFalse(party.account.is_syscohada)
        self.assertTrue(party.account.is_postable)

    def test_supplier_gets_401_aux(self):
        party = create_party(self.company, {"name": "Total", "kind": "supplier"})
        self.assertTrue(party.account.code.startswith("401-"))
        self.assertEqual(party.account.parent_id, self.acc401.id)

    def test_two_customers_do_not_share_account(self):
        first = create_party(self.company, {"name": "A", "kind": "customer"})
        second = create_party(self.company, {"name": "B", "kind": "customer"})
        self.assertNotEqual(first.account_id, second.account_id)
        self.assertNotEqual(first.account.code, second.account.code)
        self.assertTrue(first.account.code.startswith("411-"))
        self.assertTrue(second.account.code.startswith("411-"))

    def test_existing_aux_can_be_assigned_once(self):
        aux = self.make_account("411-EXIST", "Déjà là", parent=self.acc411, is_syscohada=False)
        party = create_party(
            self.company,
            {"name": "Exist", "kind": "customer", "account_id": str(aux.id), "reference": "EXIST"},
        )
        self.assertEqual(party.account_id, aux.id)
        with self.assertRaises(HttpError):
            create_party(
                self.company,
                {"name": "Autre", "kind": "customer", "account_id": str(aux.id), "reference": "AUTRE"},
            )
