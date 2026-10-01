import frappe
from frappe import _
from frappe.model.document import Document

from erpnext_sverige.frakt import hamta_installningar, leverantor, visa_fraktfel


class Fraktinstallningar(Document):
	def validate(self):
		if not self.aktiverad:
			return
		saknas = [
			self.meta.get_label(falt)
			for falt in ("bolag", "avsandaradress", "fraktartikel")
			if not self.get(falt)
		]
		if not self.api_nyckel:
			saknas.append(self.meta.get_label("api_nyckel"))
		if saknas:
			frappe.throw(_("Fyll i {0} innan transportbokning aktiveras").format(", ".join(saknas)))
		self.validera_fraktartikel()

	def validera_fraktartikel(self):
		from erpnext_sverige.setup.custom_fields import GOODS

		lagerford, typ = frappe.db.get_value(
			"Item", self.fraktartikel, ["is_stock_item", "se_goods_or_service"]
		)
		if lagerford:
			frappe.throw(_("Fraktartikeln {0} får inte vara en lagerförd artikel").format(self.fraktartikel))
		if typ != GOODS:
			frappe.throw(
				_("Fraktartikeln {0} måste ha Vara eller tjänst (moms) satt till Vara").format(
					self.fraktartikel
				)
			)


@frappe.whitelist()
@visa_fraktfel
def testa_anslutning() -> str:
	frappe.only_for(("System Manager", "Stock Manager"))
	return leverantor().kontrollera_nyckel(hamta_installningar())


@frappe.whitelist()
@visa_fraktfel
def hamta_transportorsprodukter() -> int:
	"""Prisförfrågan på en exempelsändning (en EUR-pall från avsändaren till sig själv) för att fylla registret."""
	from erpnext_sverige.frakt.fraktpris import priser_for_tillfallig_sandning
	from erpnext_sverige.frakt.parter import avsandare, nasta_arbetsdag, upphamtningstid

	frappe.only_for(("System Manager", "Stock Manager"))
	inst = hamta_installningar()
	part = avsandare(inst)
	sandning = {
		"avsandare": part,
		"mottagare": part,
		"kollin": [
			{
				"kollityp": "Pall",
				"langd_cm": 120,
				"bredd_cm": 80,
				"hojd_cm": 100,
				"vikt_kg": 200,
				"antal": 1,
				"stapelbar": 0,
				"flakmeter": 0,
				"beskrivning": _("Exempelsändning"),
			},
		],
		"referens_id": "ERPNext exempelsändning",
	}
	svar = priser_for_tillfallig_sandning(sandning, upphamtningstid(nasta_arbetsdag(), inst.upphamtning_fran))
	return len(svar["priser"])
