import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, today

from erpnext_sverige.sweden_compliance.period_lock import las_period
from erpnext_sverige.tests.utils import COMPANY, account, ensure_test_company

LOCK_DATE = "2026-01-31"


def journal_entry(posting_date, submit=True):
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
	if submit:
		je.submit()
	return je


class TestPeriodLock(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_test_company()

	def tearDown(self):
		frappe.db.rollback()
		frappe.set_user("Administrator")

	def frozen(self):
		return frappe.db.get_value("Company", COMPANY, "accounts_frozen_till_date")

	def test_lock_blocks_posting_in_period(self):
		las_period(COMPANY, LOCK_DATE)
		self.assertEqual(getdate(self.frozen()), getdate(LOCK_DATE))
		self.assertRaises(frappe.ValidationError, journal_entry, "2026-01-15")

	def test_posting_after_lock_date_is_allowed(self):
		las_period(COMPANY, LOCK_DATE)
		self.assertEqual(journal_entry("2026-02-02").docstatus, 1)

	def test_refuses_future_date(self):
		self.assertRaises(frappe.ValidationError, las_period, COMPANY, add_days(today(), 1))

	def test_refuses_when_drafts_in_period(self):
		draft = journal_entry("2026-01-20", submit=False)
		with self.assertRaises(frappe.ValidationError) as cm:
			las_period(COMPANY, LOCK_DATE)
		self.assertIn(draft.name, str(cm.exception))
		self.assertIsNone(self.frozen())

	def test_never_moves_lock_backwards(self):
		las_period(COMPANY, "2026-02-28")
		las_period(COMPANY, LOCK_DATE)
		self.assertEqual(getdate(self.frozen()), getdate("2026-02-28"))

	def test_requires_accounts_manager(self):
		frappe.set_user("Guest")
		self.assertRaises(frappe.PermissionError, las_period, COMPANY, LOCK_DATE)
