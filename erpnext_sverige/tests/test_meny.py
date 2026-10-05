"""Skrivbordsikoner och sidomenyer: Svensk bokföring ska synas i ERPNext:s meny (Frakt finns i fraktappen)."""

import frappe
from frappe.tests import IntegrationTestCase

ICONS = {"Svensk bokföring": "Accounting"}


class TestMeny(IntegrationTestCase):
	def test_icons_under_erpnext(self):
		for name, parent in ICONS.items():
			icon = frappe.get_doc("Desktop Icon", name)
			self.assertEqual(icon.parent_icon, parent)
			self.assertEqual(icon.link_type, "Workspace Sidebar")
			self.assertTrue(frappe.db.exists("Workspace Sidebar", icon.link_to), name)
			self.assertFalse(icon.hidden)

	def test_sidebar_links_exist(self):
		for name in ICONS:
			for item in frappe.get_doc("Workspace Sidebar", name).items:
				if item.type == "Link":
					self.assertTrue(frappe.db.exists(item.link_type, item.link_to), item.link_to)
