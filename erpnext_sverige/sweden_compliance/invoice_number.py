"""Fakturanummer utan luckor (bokföringslagen 5 kap., mervärdesskattelagen).

ERPNext ger fakturan sitt namn redan när utkastet skapas, så ett raderat utkast lämnar en lucka i serien.
Fakturanumret sätts i stället när fakturan bokförs, i en serie per bolag och år (2026-0001). Räknaren
uppdateras i samma databastransaktion som bokföringen: misslyckas bokföringen rullas även räknaren tillbaka.
Kreditfakturor ingår i samma serie. ERPNext:s namn (ACC-SINV-…) finns kvar som internt id.
"""

import frappe
from frappe.model.naming import getseries
from frappe.utils import getdate


def rensa_utkast(doc, method=None):
	"""Sales Invoice.validate: ett utkast har aldrig fakturanummer, inte heller en kopia av en bokförd faktura."""
	if doc.docstatus == 0 and doc.get("se_fakturanummer"):
		doc.se_fakturanummer = None


def set_fakturanummer(doc, method=None):
	"""Sales Invoice.before_submit"""
	if doc.get("se_fakturanummer"):
		return
	year = getdate(doc.posting_date).year
	abbr = frappe.get_cached_value("Company", doc.company, "abbr")
	doc.se_fakturanummer = f"{year}-{getseries(f'SE-FAKTURA-{abbr}-{year}-', 4)}"
