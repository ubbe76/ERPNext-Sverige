"""Översikternas kort och diagram i ERPNext visar sina rubriker med __(), men ERPNext har dem inte i sv.po."""

import glob
import json
import os

import frappe
from frappe.tests import UnitTestCase
from frappe.translate import get_all_translations

RUBRIKER = {"Number Card": "label", "Dashboard Chart": "chart_name", "Dashboard": "dashboard_name"}


def oversatta_saknas() -> list[str]:
	oversattningar = get_all_translations("sv")
	saknas = set()
	for path in glob.glob(os.path.join(frappe.get_app_path("erpnext"), "**", "*.json"), recursive=True):
		try:
			with open(path, encoding="utf-8") as f:
				d = json.load(f)
		except (ValueError, OSError):
			continue
		falt = RUBRIKER.get(d.get("doctype")) if isinstance(d, dict) else None
		if falt and d.get(falt) and d[falt] not in oversattningar:
			saknas.add(d[falt])
	return sorted(saknas)


class TestOversikter(UnitTestCase):
	def test_rubriker_ar_oversatta(self):
		self.assertEqual(oversatta_saknas(), [])
