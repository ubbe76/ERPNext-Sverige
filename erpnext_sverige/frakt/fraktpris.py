"""Fraktpris till kund (påslag), register över transportörsprodukter, prisförfrågan och fraktrad på faktura."""

import frappe
from frappe.utils import flt, rounded

from erpnext_sverige.frakt import hamta_installningar


def kundpris(pris: float) -> float:
	inst = hamta_installningar()
	return rounded(flt(pris) * (1 + flt(inst.paslag_procent) / 100) + flt(inst.paslag_belopp), 0)


def registrera_produkter(priser: list[dict]) -> list[dict]:
	"""Skapar saknade Fraktprodukter och sätter "fraktprodukt" och "kundpris" på varje pris."""
	for p in priser:
		namn = f"{p['transportor']} – {p['produkt']}"
		if not frappe.db.exists("Fraktprodukt", namn):
			frappe.get_doc(
				{
					"doctype": "Fraktprodukt",
					"leverantor": hamta_installningar().leverantor,
					"transportorskod": p.get("transportorskod"),
					"transportor": p["transportor"],
					"produkt": p["produkt"],
				}
			).insert(ignore_permissions=True)
		p["fraktprodukt"] = namn
		p["kundpris"] = kundpris(p["pris"])
	return sorted(priser, key=lambda p: p["pris"])
