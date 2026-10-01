"""Kolliförslag från artikelrader (egna mått eller förpackningstyp)."""

import frappe
from frappe import _
from frappe.utils import flt

EGNA_MATT = "Egna mått"
FORPACKNING = "Förpackning"
PALLPLATS_FLAKMETER = 0.4


def validera_artikel(doc, method=None):
	"""Item.validate: pallplatser → flakmeter, och förpackning kräver typ och antal."""
	if doc.fraktsatt == EGNA_MATT and flt(doc.frakt_pallplatser) and not flt(doc.frakt_flakmeter):
		doc.frakt_flakmeter = flt(doc.frakt_pallplatser) * PALLPLATS_FLAKMETER
	if doc.fraktsatt == FORPACKNING and (not doc.forpackningstyp or flt(doc.antal_per_forpackning) <= 0):
		frappe.throw(_("Ange förpackningstyp och antal per förpackning (större än noll)"))
