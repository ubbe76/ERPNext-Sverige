import frappe
from frappe import _
from frappe.model.document import Document


class Fraktinstallningar(Document):
	def validate(self):
		if not self.aktiverad:
			return
		saknas = [
			self.meta.get_label(falt)
			for falt in ("bolag", "avsandaradress", "fraktkonto")
			if not self.get(falt)
		]
		if not self.api_nyckel:
			saknas.append(self.meta.get_label("api_nyckel"))
		if saknas:
			frappe.throw(_("Fyll i {0} innan transportbokning aktiveras").format(", ".join(saknas)))
		if frappe.db.get_value("Account", self.fraktkonto, "company") != self.bolag:
			frappe.throw(_("Fraktkontot tillhör inte bolaget {0}").format(self.bolag))
