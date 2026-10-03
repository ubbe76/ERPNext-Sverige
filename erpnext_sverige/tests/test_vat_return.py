import os
import xml.etree.ElementTree as ET
from datetime import date
from unittest.mock import patch

import frappe
from erpnext.accounts.utils import FiscalYearError
from frappe.tests import IntegrationTestCase, UnitTestCase
from frappe.utils import getdate, today
from lxml import etree

from erpnext_sverige.setup.company import TAX_CATEGORY_EU, TAX_CATEGORY_SE
from erpnext_sverige.setup.custom_fields import SERVICE
from erpnext_sverige.sweden_compliance.period_lock import las_period
from erpnext_sverige.sweden_compliance.vat_return import (
	build_eskd_xml,
	compute_boxes,
	create_vat_settlement,
	download_eskd,
	format_org_nr,
	get_vat_return,
	kontrollera_period,
	perioden,
	senaste_avslutade_period,
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
		# Skatteverket: "Ange numret med 10 siffror enligt formatet xxxxxx-xxxx, med bindestreck."
		self.assertEqual(format_org_nr("556000-0000"), "556000-0000")
		self.assertEqual(format_org_nr("5560000000"), "556000-0000")
		self.assertEqual(format_org_nr("SE556000000001"), "556000-0000")

	def test_personal_identity_number(self):
		self.assertEqual(format_org_nr("850101-1234"), "850101-1234")
		self.assertEqual(format_org_nr("198501011234"), "850101-1234")


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

	@patch("erpnext_sverige.sweden_compliance.vat_return.kontrollera_period")
	def test_settlement_draft_zeroes_vat_accounts(self, _kontroll):
		# Testet gäller omföringen; periodkontrollen testas i TestMomsperiodKontroll
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
		self.assertEqual(root.findtext("OrgNr"), "556000-0000")
		self.assertEqual(root.findtext("Moms/Period"), self.date.replace("-", "")[:6])
		self.assertEqual(int(root.findtext("Moms/MomsBetala")), self.vat_return()["49"])
		self.assertEqual(int(root.findtext("Moms/ForsMomsEjAnnan")), 2000)
		self.assertIsNone(root.find("Moms/UttagMoms"))  # nollrutor utelämnas

	def test_eskd_utan_doctype_och_indrag_och_giltig_mot_dtd(self):
		data = build_eskd_xml(COMPANY, self.date, self.date)
		self.assertNotIn(b"DOCTYPE", data)
		self.assertFalse([rad for rad in data.split(b"\n") if rad[:1] in (b" ", b"\t")])
		dtd = etree.DTD(os.path.join(os.path.dirname(__file__), "fixtures", "eSKDUpload_6p0.dtd"))
		self.assertTrue(dtd.validate(etree.fromstring(data)), dtd.error_log)


BRUTET_AR = (date(2026, 5, 1), date(2027, 4, 30))


def brutet_rakenskapsar(datum):
	start = date(datum.year if datum.month >= 5 else datum.year - 1, 5, 1)
	return start, date(start.year + 1, 4, 30)


def bara_2026(datum, company=None, as_dict=False, raise_on_missing=True, **kwargs):
	"""Som get_fiscal_year när bara räkenskapsåret 2026 finns."""
	if getdate(datum).year == 2026:
		return frappe._dict(year_start_date=date(2026, 1, 1), year_end_date=date(2026, 12, 31))
	if raise_on_missing:
		frappe.throw(f"Datum {datum} är inte under något aktivt räkenskapsår", FiscalYearError)
	return False


class TestPerioden(UnitTestCase):
	def test_manad(self):
		self.assertEqual(
			perioden("Månad", date(2026, 9, 14), brutet_rakenskapsar), (date(2026, 9, 1), date(2026, 9, 30))
		)
		self.assertEqual(
			perioden("Månad", date(2028, 2, 10), brutet_rakenskapsar), (date(2028, 2, 1), date(2028, 2, 29))
		)

	def test_kvartal(self):
		self.assertEqual(
			perioden("Kvartal", date(2026, 8, 15), brutet_rakenskapsar), (date(2026, 7, 1), date(2026, 9, 30))
		)
		self.assertEqual(
			perioden("Kvartal", date(2026, 12, 31), brutet_rakenskapsar),
			(date(2026, 10, 1), date(2026, 12, 31)),
		)

	def test_ar_ar_rakenskapsaret(self):
		self.assertEqual(perioden("År", date(2026, 9, 14), brutet_rakenskapsar), BRUTET_AR)
		self.assertEqual(
			perioden("", date(2027, 4, 30), brutet_rakenskapsar), BRUTET_AR
		)  # tomt räknas som år


class TestMomsperiodKontroll(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_test_company()

	def setUp(self):
		frappe.db.set_value("Company", COMPANY, "se_momsperiod", "Kvartal")

	def tearDown(self):
		frappe.db.rollback()

	def test_hel_period_godkanns(self):
		kontrollera_period(COMPANY, "2026-07-01", "2026-09-30")

	def test_del_av_period_stoppas(self):
		self.assertRaisesRegex(
			frappe.ValidationError, "per kvartal", kontrollera_period, COMPANY, "2026-07-01", "2026-08-31"
		)
		self.assertRaisesRegex(
			frappe.ValidationError, "2026-07-01", kontrollera_period, COMPANY, "2026-08-01", "2026-09-30"
		)

	def test_eskd_stoppas_vid_fel_period(self):
		self.assertRaises(frappe.ValidationError, download_eskd, COMPANY, "2026-07-01", "2026-08-31")

	def test_omforing_stoppas_vid_fel_period(self):
		self.assertRaises(frappe.ValidationError, create_vat_settlement, COMPANY, "2026-07-01", "2026-08-31")

	def test_las_stoppas_om_slutdatum_inte_ar_periodslut(self):
		self.assertRaisesRegex(frappe.ValidationError, "per kvartal", las_period, COMPANY, "2026-08-31")

	def test_forsta_aret_ger_pagaende_period(self):
		# Årsredovisare utan avslutat räkenskapsår före det pågående (bolagets första år): pågående året,
		# utan felmeddelande, i stället för ett fel när rapporten öppnas
		frappe.db.set_value("Company", COMPANY, "se_momsperiod", "År")
		frappe.local.message_log = []
		with patch("erpnext_sverige.sweden_compliance.vat_return.get_fiscal_year", side_effect=bara_2026):
			self.assertEqual(
				senaste_avslutade_period(COMPANY, date(2026, 10, 3)), (date(2026, 1, 1), date(2026, 12, 31))
			)
		self.assertEqual(frappe.local.message_log, [])

	def test_senaste_avslutade_period(self):
		self.assertEqual(
			senaste_avslutade_period(COMPANY, date(2026, 10, 3)), (date(2026, 7, 1), date(2026, 9, 30))
		)
		frappe.db.set_value("Company", COMPANY, "se_momsperiod", "Månad")
		self.assertEqual(
			senaste_avslutade_period(COMPANY, date(2027, 1, 5)), (date(2026, 12, 1), date(2026, 12, 31))
		)
