import xml.etree.ElementTree as ET

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase
from frappe.utils import today

from erpnext_sverige.setup.company import TAX_CATEGORY_EU, TAX_CATEGORY_SE
from erpnext_sverige.setup.custom_fields import SERVICE
from erpnext_sverige.sweden_compliance.vat_return import (
	build_eskd_xml,
	compute_boxes,
	create_vat_settlement,
	format_org_nr,
	get_vat_return,
)
from erpnext_sverige.tests.utils import (
	COMPANY,
	COMPANY_ABBR,
	account,
	ensure_test_company,
	make_invoice,
	make_item,
	make_party,
)


class TestComputeBoxes(UnitTestCase):
	def test_boxes_from_balances(self):
		# Saldon som debet - kredit
		boxes = compute_boxes(
			{
				"3001": -1000.6,
				"3002": -500,
				"3740": -0.4,
				"3308": -2000,
				"2611": -250.15,
				"2621": -60,
				"4535": 1500,
				"2614": -375,
				"2645": 375,
				"2641": 200.9,
			}
		)
		self.assertEqual(boxes["05"], 1500)  # 3740 ingår inte, öretal stryks
		self.assertEqual(boxes["10"], 250)
		self.assertEqual(boxes["11"], 60)
		self.assertEqual(boxes["39"], 2000)
		self.assertEqual(boxes["21"], 1500)
		self.assertEqual(boxes["30"], 375)
		self.assertEqual(boxes["48"], 575)
		self.assertEqual(boxes["49"], 250 + 60 + 375 - 575)
		self.assertEqual(boxes["06"], 0)

	def test_refund_is_negative(self):
		boxes = compute_boxes({"2611": -100, "2641": 300})
		self.assertEqual(boxes["49"], -200)


class TestFormatOrgNr(UnitTestCase):
	def test_organisation_number(self):
		self.assertEqual(format_org_nr("556000-0000"), "165560000000")
		self.assertEqual(format_org_nr("SE556000000001"), "165560000000")

	def test_personal_identity_number(self):
		self.assertEqual(format_org_nr("850101-1234"), "198501011234")
		self.assertEqual(format_org_nr("198501011234"), "198501011234")


class TestVatReturnFromLedger(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_test_company()
		if not frappe.db.get_value("Company", COMPANY, "tax_id"):
			frappe.db.set_value("Company", COMPANY, "tax_id", "5560000000")
			frappe.db.commit()

	def setUp(self):
		self.date = today()
		service = make_item("TEST-SE-TJANST", kind=SERVICE)
		goods_12 = make_item("TEST-SE-VARA-12", kind="Vara", template=f"Moms 12 % - {COMPANY_ABBR}")
		customer_se = make_party("Customer", "Test SE Kund AB", TAX_CATEGORY_SE)
		customer_eu = make_party("Customer", "Test EU Kunde GmbH", TAX_CATEGORY_EU)
		supplier_se = make_party("Supplier", "Test SE Leverantör AB", TAX_CATEGORY_SE)
		supplier_eu = make_party("Supplier", "Test EU Lieferant GmbH", TAX_CATEGORY_EU)

		self.si_se = make_invoice("Sales Invoice", customer_se, [(service, 1000), (goods_12, 1000)])
		make_invoice("Sales Invoice", customer_eu, [(service, 2000)])
		make_invoice("Purchase Invoice", supplier_se, [(service, 800)])
		make_invoice("Purchase Invoice", supplier_eu, [(service, 1500)])

	def tearDown(self):
		frappe.db.rollback()

	def vat_return(self):
		return get_vat_return(COMPANY, self.date, self.date)

	def test_boxes(self):
		boxes = self.vat_return()
		self.assertEqual(boxes["05"], 2000)
		self.assertEqual(boxes["10"], 250)
		self.assertEqual(boxes["11"], 120)
		self.assertEqual(boxes["39"], 2000)
		self.assertEqual(boxes["21"], 1500)
		self.assertEqual(boxes["30"], 375)
		self.assertEqual(boxes["48"], 200 + 375)
		self.assertEqual(boxes["49"], 250 + 120 + 375 - 575)

	def test_cancelled_invoice_is_excluded(self):
		before = self.vat_return()
		extra = make_invoice("Sales Invoice", self.si_se.customer, [("TEST-SE-TJANST", 400)])
		extra.cancel()
		self.assertEqual(self.vat_return(), before)

	def test_settlement_draft_zeroes_vat_accounts(self):
		boxes = self.vat_return()
		je = frappe.get_doc("Journal Entry", create_vat_settlement(COMPANY, self.date, self.date))

		self.assertEqual(je.docstatus, 0)
		self.assertEqual(je.total_debit, je.total_credit)
		lines = {
			row.account: row.debit_in_account_currency - row.credit_in_account_currency for row in je.accounts
		}
		self.assertEqual(lines[account("2611")], 250)
		self.assertEqual(lines[account("2641")], -200)
		self.assertEqual(lines[account("2650")], -boxes["49"])

		# Samma utkast returneras igen, och en bokförd omföring ändrar inte rutorna
		self.assertEqual(create_vat_settlement(COMPANY, self.date, self.date), je.name)
		je.submit()
		self.assertEqual(self.vat_return(), boxes)

	def test_eskd_file(self):
		root = ET.fromstring(build_eskd_xml(COMPANY, self.date, self.date))
		self.assertEqual(root.tag, "eSKDUpload")
		self.assertEqual(root.findtext("OrgNr"), "165560000000")
		self.assertEqual(root.findtext("Moms/Period"), self.date.replace("-", "")[:6])
		self.assertEqual(int(root.findtext("Moms/MomsBetala")), self.vat_return()["49"])
		self.assertEqual(int(root.findtext("Moms/ForsMomsEjAnnan")), 2000)
		self.assertIsNone(root.find("Moms/UttagMoms"))  # nollrutor utelämnas
