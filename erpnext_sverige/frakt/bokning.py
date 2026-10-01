"""Transportbokning på Shipment: skapa från följesedel, priser, spara val, boka, dokument och avbokning."""

import frappe
from erpnext.stock.doctype.delivery_note.delivery_note import make_shipment
from frappe import _
from frappe.contacts.doctype.address.address import get_address_display

from erpnext_sverige.frakt import hamta_installningar
from erpnext_sverige.frakt.kollin import foresla_kollin
from erpnext_sverige.frakt.parter import avsandare, nasta_arbetsdag, part


def _foljesedlar(doc) -> list[str]:
	return [r.delivery_note for r in doc.shipment_delivery_note if r.delivery_note]


def _lagerrader(foljesedlar) -> list[tuple[str, float]]:
	return frappe.get_all(
		"Delivery Note Item",
		filters={"parent": ["in", foljesedlar], "parenttype": "Delivery Note"},
		fields=["item_code", "stock_qty"],
		as_list=True,
	)


def satt_kollin(doc, kollin) -> None:
	doc.shipment_parcel = []
	for k in kollin:
		doc.append(
			"shipment_parcel",
			{
				"length": k["langd_cm"],
				"width": k["bredd_cm"],
				"height": k["hojd_cm"],
				"weight": k["vikt_kg"],
				"count": k["antal"],
				"kollityp": k["kollityp"],
				"stapelbar": k["stapelbar"],
				"flakmeter": k["flakmeter"],
				"beskrivning": k["beskrivning"],
			},
		)


def _visa_varningar(varningar):
	if varningar:
		frappe.msgprint("<br>".join(varningar), title=_("Kontrollera kollina"), indicator="orange")


def _forvald_fraktprodukt(dn) -> str | None:
	order = next((r.against_sales_order for r in dn.items if r.against_sales_order), None)
	if order and (produkt := frappe.db.get_value("Sales Order", order, "fraktprodukt")):
		return produkt
	return frappe.db.get_value("Customer", dn.customer, "forvald_fraktprodukt")


@frappe.whitelist()
def skapa_shipment(delivery_note: str) -> str:
	inst = hamta_installningar()
	dn = frappe.get_doc("Delivery Note", delivery_note)
	dn.check_permission("read")
	frappe.has_permission("Shipment", "create", throw=True)

	doc = make_shipment(delivery_note)
	doc.shipment_delivery_note = []
	doc.append("shipment_delivery_note", {"delivery_note": dn.name, "grand_total": dn.grand_total})
	doc.pickup_from_type = "Company"
	doc.pickup_company = inst.bolag
	doc.pickup_address_name = inst.avsandaradress
	doc.pickup_address = get_address_display(inst.avsandaradress)
	doc.pickup_date = nasta_arbetsdag()
	doc.pickup_from = inst.upphamtning_fran
	doc.pickup_to = inst.upphamtning_till
	doc.description_of_content = _("Gods enligt följesedel {0}").format(dn.name)
	doc.avsandarens_referens = dn.name
	doc.mottagarens_referens = dn.po_no
	doc.fraktprodukt = _forvald_fraktprodukt(dn)

	kollin, varningar = foresla_kollin(_lagerrader([dn.name]))
	satt_kollin(doc, kollin)
	doc.insert()
	_visa_varningar(varningar)
	return doc.name


def _utkast(shipment: str):
	doc = frappe.get_doc("Shipment", shipment)
	doc.check_permission("write")
	if doc.docstatus != 0:
		frappe.throw(_("Försändelsen {0} är redan bokad eller avbruten").format(doc.name))
	return doc


@frappe.whitelist()
def foresla_kollin_igen(shipment: str) -> list[str]:
	doc = _utkast(shipment)
	kollin, varningar = foresla_kollin(_lagerrader(_foljesedlar(doc)))
	satt_kollin(doc, kollin)
	doc.save()
	return varningar


def sandning_fran_shipment(doc) -> dict:
	kund = frappe.db.get_value(
		"Customer", doc.delivery_customer, ["customer_name", "customer_type"], as_dict=True
	)
	return {
		"avsandare": avsandare(hamta_installningar()),
		"mottagare": part(
			kund.customer_name,
			doc.delivery_address_name,
			doc.delivery_contact_name,
			privatperson=kund.customer_type == "Individual",
		),
		"kollin": [
			{
				"kollityp": r.kollityp or "Paket",
				"langd_cm": r.length,
				"bredd_cm": r.width,
				"hojd_cm": r.height,
				"vikt_kg": r.weight,
				"antal": r.count,
				"stapelbar": r.stapelbar,
				"flakmeter": r.flakmeter,
				"beskrivning": r.beskrivning or doc.description_of_content,
			}
			for r in doc.shipment_parcel
		],
		"referens_id": doc.name,
		"avsandarens_referens": doc.avsandarens_referens,
		"mottagarens_referens": doc.mottagarens_referens,
	}
