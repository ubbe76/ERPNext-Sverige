"""Fraktpris till kund (påslag), register över transportörsprodukter, prisförfrågan och fraktrad på faktura."""

import frappe
from frappe import _
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


def fraktrad(konto, beskrivning, belopp, cost_center) -> dict:
	return {
		"charge_type": "Actual",
		"account_head": konto,
		"description": beskrivning,
		"tax_amount": flt(belopp),
		"cost_center": cost_center,
	}


def lagg_frakt_pa_faktura(doc, method=None):
	"""Sales Invoice.before_insert: fraktrad per bokad Shipment på fakturans följesedlar, en gång per Shipment."""
	inst = frappe.get_cached_doc("Fraktinstallningar")
	if not (inst.aktiverad and inst.fraktkonto and doc.company == inst.bolag):
		return
	if any(t.account_head == inst.fraktkonto for t in doc.taxes):
		return
	foljesedlar = list({r.delivery_note for r in doc.items if r.delivery_note})
	if not foljesedlar:
		return
	shipments = frappe.get_all(
		"Shipment Delivery Note",
		filters={"delivery_note": ["in", foljesedlar], "parenttype": "Shipment"},
		pluck="parent",
		distinct=True,
	)
	cost_center = doc.cost_center or frappe.get_cached_value("Company", doc.company, "cost_center")
	for s in frappe.get_all(
		"Shipment",
		filters={"name": ["in", shipments], "docstatus": 1, "status": ["in", ["Booked", "Completed"]]},
		fields=["name", "kundpris", "carrier", "carrier_service"],
		order_by="name",
	):
		if not flt(s.kundpris) or _redan_fakturerad(s.name):
			continue
		beskrivning = _("Frakt {0} {1} ({2})").format(s.carrier, s.carrier_service, s.name)
		doc.append("taxes", fraktrad(inst.fraktkonto, beskrivning, s.kundpris, cost_center))


def _redan_fakturerad(shipment) -> bool:
	return bool(
		frappe.db.exists(
			"Sales Taxes and Charges",
			{"parenttype": "Sales Invoice", "description": ["like", f"%({shipment})"], "docstatus": ["<", 2]},
		)
	)
