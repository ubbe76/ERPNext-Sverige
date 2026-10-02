import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import today

from erpnext_sverige.sweden_compliance.report.grundbok.grundbok import execute
from erpnext_sverige.tests.utils import COMPANY, account, ensure_test_company


def journal_entry(posting_date):
	je = frappe.get_doc(
		{
			"doctype": "Journal Entry",
			"company": COMPANY,
			"posting_date": posting_date,
			"accounts": [
				{"account": account("1930"), "debit_in_account_currency": 100},
				{"account": account("1910"), "credit_in_account_currency": 100},
			],
		}
	).insert()
	je.submit()
	return je


class TestGrundbok(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_test_company()

	def tearDown(self):
		frappe.db.rollback()

	def test_rows_in_registration_order(self):
		later_dated = journal_entry("2026-03-15")
		earlier_dated = journal_entry("2026-02-10")
		_columns, rows = execute({"company": COMPANY, "from_date": today(), "to_date": today()})
		vouchers = [r.voucher_no for r in rows if r.voucher_no in (later_dated.name, earlier_dated.name)]
		# Registreringsordning, inte bokföringsdatum: den senare daterade registrerades först
		self.assertEqual(vouchers, [later_dated.name] * 2 + [earlier_dated.name] * 2)
		row = next(r for r in rows if r.voucher_no == later_dated.name)
		self.assertEqual(str(row.posting_date), "2026-03-15")
		self.assertEqual(row.owner, "Administrator")

	def test_cancellation_is_its_own_rows(self):
		je = journal_entry("2026-03-16")
		je.cancel()
		_columns, rows = execute({"company": COMPANY, "from_date": today(), "to_date": today()})
		self.assertEqual(len([r for r in rows if r.voucher_no == je.name]), 4)
