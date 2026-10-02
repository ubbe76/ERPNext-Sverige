import frappe
from erpnext.controllers.sales_and_purchase_return import make_return_doc
from frappe.tests import IntegrationTestCase
from frappe.utils import getdate, today

from erpnext_sverige.setup.company import TAX_CATEGORY_SE
from erpnext_sverige.setup.custom_fields import GOODS
from erpnext_sverige.sweden_compliance.invoice import get_invoice_context
from erpnext_sverige.tests.utils import ensure_test_company, make_invoice, make_item, make_party


def number(name):
	return frappe.db.get_value("Sales Invoice", name, "se_fakturanummer")


def seq(value):
	year, n = value.split("-")
	return int(year), int(n)


class TestFakturanummer(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_test_company()

	def setUp(self):
		self.item = make_item("TEST-SE-FAKTURANR", kind=GOODS)
		self.customer = make_party("Customer", "Test SE Kund AB", TAX_CATEGORY_SE)

	def tearDown(self):
		frappe.db.rollback()

	def invoice(self, submit=True):
		return make_invoice("Sales Invoice", self.customer, [(self.item, 100)], submit=submit)

	def test_draft_has_no_number(self):
		self.assertFalse(self.invoice(submit=False).se_fakturanummer)

	def test_number_set_on_submit_with_year(self):
		si = self.invoice()
		year, n = seq(number(si.name))
		self.assertEqual(year, getdate(today()).year)
		self.assertGreaterEqual(n, 1)

	def test_deleted_draft_leaves_no_gap(self):
		first = self.invoice()
		draft = self.invoice(submit=False)
		frappe.delete_doc("Sales Invoice", draft.name)
		second = self.invoice()
		self.assertEqual(seq(number(second.name))[1], seq(number(first.name))[1] + 1)

	def test_credit_note_gets_next_number_and_refers_to_original(self):
		si = self.invoice()
		cn = make_return_doc("Sales Invoice", si.name)
		cn.insert()
		cn.submit()
		self.assertEqual(seq(number(cn.name))[1], seq(number(si.name))[1] + 1)
		ctx = get_invoice_context(cn)
		self.assertEqual(ctx["invoice_no"], number(cn.name))
		self.assertEqual(ctx["credit_for_invoice_no"], number(si.name))

	def test_number_not_copied_to_amendment(self):
		si = self.invoice()
		si.cancel()
		# Även en kopia som tar med no_copy-fält får nytt nummer: ett utkast har aldrig fakturanummer
		amended = frappe.copy_doc(si)
		amended.docstatus = 0
		amended.amended_from = si.name
		amended.insert()
		self.assertFalse(amended.se_fakturanummer)
		amended.submit()
		self.assertNotEqual(amended.se_fakturanummer, number(si.name))

	def test_failed_submit_does_not_use_a_number(self):
		from unittest.mock import patch

		from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice

		first = self.invoice()
		bad = self.invoice(submit=False)
		frappe.db.savepoint("fore_bokforing")
		# Felet uppstår efter before_submit, alltså efter att numret har tagits
		with patch.object(
			SalesInvoice, "make_gl_entries", side_effect=frappe.ValidationError("bokföringen misslyckades")
		):
			self.assertRaises(frappe.ValidationError, bad.submit)
		frappe.db.rollback(save_point="fore_bokforing")
		second = self.invoice()
		self.assertEqual(seq(number(second.name))[1], seq(number(first.name))[1] + 1)
