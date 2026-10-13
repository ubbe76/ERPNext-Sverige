"""Meny: Svensk bokföring ska synas i ERPNext:s meny (Frakt finns i fraktappen).

frappe 16.51 har två lägen. I Apps-läget (standard på nya siter) ligger posten i ERPNext:s dock och
öppnar sidomenyn "Svensk bokföring". I ikonläget ("Desktop Icons") ligger en ikon under Accounting.
"""

import json

import frappe
from frappe.desk.doctype.desktop_settings.desktop_settings import is_desktop_icons_page
from frappe.desk.doctype.dock.dock import mounted_apps, resolve_app_dock
from frappe.tests import IntegrationTestCase

MENY = "Svensk bokföring"
APP = "erpnext_sverige"


class TestMeny(IntegrationTestCase):
	def test_sidomeny_finns(self):
		meny = frappe.get_doc("Sidebar", MENY)
		self.assertEqual((meny.app, meny.module, meny.standard), (APP, "Sweden Compliance", 1))

	def test_sidomenyns_lankar_finns(self):
		for item in frappe.get_doc("Sidebar", MENY).items:
			if item.type == "Link":
				self.assertTrue(frappe.db.exists(item.link_type, item.link_to), item.link_to)

	def test_i_erpnext_dockan(self):
		self.assertEqual(mounted_apps().get(APP), "erpnext")
		self.assertIn(
			("Sidebar", MENY),
			[(e["link_type"], e["link_to"]) for e in resolve_app_dock("erpnext", gated=False)],
		)

	def test_ikon_under_accounting(self):
		with open(frappe.get_app_path(APP, "desktop_icon", "svensk_bokföring.json")) as f:
			ikon = json.load(f)
		self.assertEqual(
			(ikon["parent_icon"], ikon["link_type"], ikon["link_to"]),
			("Accounting", "Workspace Sidebar", MENY),
		)
		if is_desktop_icons_page():
			self.assertEqual(frappe.db.get_value("Desktop Icon", MENY, "parent_icon"), "Accounting")
			self.assertFalse(frappe.db.get_value("Desktop Icon", MENY, "hidden"))
