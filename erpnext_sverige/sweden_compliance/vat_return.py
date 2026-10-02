"""Momsdeklaration: Skatteverkets rutor ur huvudboken, eSKD-fil och momsomföring.

Rutorna räknas fram från kontosaldon per BAS-kontonummer. Verifikationer från bokslut (Period Closing
Voucher) och tidigare momsomföringar räknas inte med, så att rapporten visar samma siffror före och efter
omföringen.
"""

import calendar
import re
from dataclasses import dataclass
from datetime import date, timedelta
from xml.sax.saxutils import escape

import frappe
from erpnext.accounts.utils import get_fiscal_year
from frappe import _
from frappe.utils import flt, getdate

CREDIT = "credit"  # kredit - debet (intäkter, utgående moms)
DEBIT = "debit"  # debet - kredit (kostnader, ingående moms)

VAT_ACCOUNT_RANGE = ("2610", "2649")
SETTLEMENT_ACCOUNT = "2650"
ROUNDING_ACCOUNT = "3740"


@dataclass(frozen=True)
class Box:
	number: str
	label: str
	ranges: tuple[tuple[str, str], ...]
	sign: str
	eskd: str


# Ordningen följer eSKD-filens elementordning
BOXES = (
	Box(
		"05",
		"Momspliktig försäljning som inte ingår i ruta 06, 07 eller 08",
		(("3000", "3799"),),
		CREDIT,
		"ForsMomsEjAnnan",
	),
	Box("06", "Momspliktiga uttag", (), CREDIT, "UttagMoms"),
	Box("07", "Beskattningsunderlag vid vinstmarginalbeskattning", (), CREDIT, "UlagMargbesk"),
	Box("08", "Hyresinkomster vid frivillig skattskyldighet", (), CREDIT, "HyrinkomstFriv"),
	Box("20", "Inköp av varor från ett annat EU-land", (("4515", "4517"),), DEBIT, "InkopVaruAnnatEg"),
	Box("21", "Inköp av tjänster från ett annat EU-land", (("4535", "4537"),), DEBIT, "InkopTjanstAnnatEg"),
	Box("22", "Inköp av tjänster från ett land utanför EU", (("4531", "4533"),), DEBIT, "InkopTjanstUtomEg"),
	Box(
		"23",
		"Inköp av varor i Sverige som köparen är skattskyldig för",
		(("4415", "4417"),),
		DEBIT,
		"InkopVaruSverige",
	),
	Box(
		"24",
		"Övriga inköp av tjänster i Sverige som köparen är skattskyldig för",
		(("4425", "4427"),),
		DEBIT,
		"InkopTjanstSverige",
	),
	Box("50", "Beskattningsunderlag vid import", (("4545", "4547"),), DEBIT, "MomsUlagImport"),
	Box("35", "Försäljning av varor till ett annat EU-land", (("3108", "3108"),), CREDIT, "ForsVaruAnnatEg"),
	Box("36", "Försäljning av varor utanför EU", (("3105", "3105"),), CREDIT, "ForsVaruUtomEg"),
	Box("37", "Mellanmans inköp av varor vid trepartshandel", (), DEBIT, "InkopVaruMellan3p"),
	Box("38", "Mellanmans försäljning av varor vid trepartshandel", (), CREDIT, "ForsVaruMellan3p"),
	Box(
		"39",
		"Försäljning av tjänster till näringsidkare i ett annat EU-land",
		(("3308", "3308"),),
		CREDIT,
		"ForsTjSkskAnnatEg",
	),
	Box(
		"40",
		"Övrig försäljning av tjänster omsatta utanför Sverige",
		(("3305", "3305"),),
		CREDIT,
		"ForsTjOvrUtomEg",
	),
	Box(
		"41",
		"Försäljning när köparen är skattskyldig i Sverige",
		(("3231", "3231"),),
		CREDIT,
		"ForsKopareSkskSverige",
	),
	Box("42", "Övrig försäljning m.m.", (("3004", "3004"),), CREDIT, "ForsOvrigt"),
	Box("10", "Utgående moms 25 %", (("2610", "2613"),), CREDIT, "MomsUtgHog"),
	Box("11", "Utgående moms 12 %", (("2620", "2623"),), CREDIT, "MomsUtgMedel"),
	Box("12", "Utgående moms 6 %", (("2630", "2633"),), CREDIT, "MomsUtgLag"),
	Box("30", "Utgående moms 25 % på inköp i ruta 20–24", (("2614", "2614"),), CREDIT, "MomsInkopUtgHog"),
	Box("31", "Utgående moms 12 % på inköp i ruta 20–24", (("2624", "2624"),), CREDIT, "MomsInkopUtgMedel"),
	Box("32", "Utgående moms 6 % på inköp i ruta 20–24", (("2634", "2634"),), CREDIT, "MomsInkopUtgLag"),
	Box("60", "Utgående moms 25 % vid import", (("2615", "2615"),), CREDIT, "MomsImportUtgHog"),
	Box("61", "Utgående moms 12 % vid import", (("2625", "2625"),), CREDIT, "MomsImportUtgMedel"),
	Box("62", "Utgående moms 6 % vid import", (("2635", "2635"),), CREDIT, "MomsImportUtgLag"),
	Box("48", "Ingående moms att dra av", (("2640", "2649"),), DEBIT, "MomsIngAvdr"),
	Box("49", "Moms att betala eller få tillbaka", (), CREDIT, "MomsBetala"),
)

# Ruta 05 omfattar 3000-3799 utom konton som hör till andra rutor och öresutjämning
EXCLUDED_FROM_05 = {
	number for box in BOXES if box.number != "05" for low, high in box.ranges for number in (low, high)
} | {ROUNDING_ACCOUNT}
OUTPUT_VAT_BOXES = ("10", "11", "12", "30", "31", "32", "60", "61", "62")


def get_account_balances(company: str, from_date, to_date) -> dict[str, float]:
	"""Saldo (debet - kredit) per kontonummer för perioden."""
	rows = frappe.db.sql(
		"""
		select acc.account_number, sum(gle.debit) - sum(gle.credit) as balance
		from `tabGL Entry` gle
		join `tabAccount` acc on acc.name = gle.account
		left join `tabJournal Entry` je
			on gle.voucher_type = 'Journal Entry' and je.name = gle.voucher_no
		where gle.company = %(company)s
			and gle.posting_date between %(from_date)s and %(to_date)s
			and gle.is_cancelled = 0
			and gle.voucher_type != 'Period Closing Voucher'
			and ifnull(je.se_vat_settlement_period, '') = ''
			and ifnull(acc.account_number, '') != ''
		group by acc.account_number
		""",
		{"company": company, "from_date": from_date, "to_date": to_date},
		as_dict=True,
	)
	return {row.account_number: flt(row.balance) for row in rows}


def compute_boxes(balances: dict[str, float]) -> dict[str, int]:
	"""Rutor i hela kronor (öretal stryks) ur saldon per kontonummer."""
	boxes = {}
	for box in BOXES:
		if box.number == "49":
			continue
		total = 0.0
		for number, balance in balances.items():
			if _in_ranges(number, box.ranges) and not (box.number == "05" and number in EXCLUDED_FROM_05):
				total += balance
		if box.sign == CREDIT:
			total = -total
		boxes[box.number] = int(total)  # hela kronor, öretal stryks

	boxes["49"] = sum(boxes[b] for b in OUTPUT_VAT_BOXES) - boxes["48"]
	return boxes


def get_vat_return(company: str, from_date, to_date) -> dict[str, int]:
	return compute_boxes(get_account_balances(company, from_date, to_date))


def box_accounts(box: Box) -> str:
	ranges = ", ".join(low if low == high else f"{low}–{high}" for low, high in box.ranges)
	if box.number == "05":
		ranges += " (utom konton i ruta 35–42 och 3740)"
	if box.number == "49":
		ranges = "10+11+12+30+31+32+60+61+62 − 48"
	return ranges


def _in_ranges(number: str, ranges) -> bool:
	return any(low <= number <= high and len(number) == len(low) for low, high in ranges)


# eSKD-fil ---------------------------------------------------------------------------------------


def build_eskd_xml(company: str, from_date, to_date) -> bytes:
	boxes = get_vat_return(company, from_date, to_date)
	org_nr = format_org_nr(frappe.get_cached_value("Company", company, "tax_id"))
	period = getdate(to_date).strftime("%Y%m")

	# Som Skatteverkets exempel: utan DOCTYPE och utan indrag ("felaktiga mellanslag eller tabbar" avvisas)
	lines = [
		'<?xml version="1.0" encoding="ISO-8859-1"?>',
		'<eSKDUpload Version="6.0">',
		f"<OrgNr>{escape(org_nr)}</OrgNr>",
		"<Moms>",
		f"<Period>{period}</Period>",
	]
	for box in BOXES:
		value = boxes[box.number]
		if value or box.number == "49":
			lines.append(f"<{box.eskd}>{value}</{box.eskd}>")
	lines += ["</Moms>", "</eSKDUpload>", ""]
	return "\n".join(lines).encode("iso-8859-1")


def format_org_nr(tax_id: str | None) -> str:
	"""Organisations- eller personnummer med tio siffror och bindestreck (xxxxxx-xxxx), som Skatteverket kräver."""
	value = (tax_id or "").strip().upper()
	digits = re.sub(r"\D", "", value)
	if value.startswith("SE") and len(digits) == 12 and digits.endswith("01"):  # momsregistreringsnummer
		digits = digits[:10]
	elif len(digits) == 12:  # personnummer med sekel eller organisationsnummer med prefixet 16
		digits = digits[2:]
	if len(digits) != 10:
		frappe.throw(_("Organisationsnumret (Tax ID) på bolaget måste ha 10 eller 12 siffror"))
	return f"{digits[:6]}-{digits[6:]}"


@frappe.whitelist()
def download_eskd(company: str, from_date: str, to_date: str):
	frappe.has_permission("GL Entry", "read", throw=True)
	kontrollera_period(company, from_date, to_date)
	frappe.response["filename"] = f"momsdeklaration-{getdate(to_date).strftime('%Y%m')}.xml"
	frappe.response["filecontent"] = build_eskd_xml(company, from_date, to_date)
	frappe.response["type"] = "download"


# Momsomföring -----------------------------------------------------------------------------------


def settlement_period(from_date, to_date) -> str:
	return f"{getdate(from_date)} – {getdate(to_date)}"


@frappe.whitelist()
def create_vat_settlement(company: str, from_date: str, to_date: str) -> str:
	"""Skapa momsomföringen som utkast: nollställ 2610-2649 mot 2650. Returnerar Journal Entry-namnet."""
	frappe.has_permission("Journal Entry", "create", throw=True)
	kontrollera_period(company, from_date, to_date)
	period = settlement_period(from_date, to_date)

	existing = frappe.db.get_value(
		"Journal Entry",
		{"company": company, "se_vat_settlement_period": period, "docstatus": ["<", 2]},
	)
	if existing:
		return existing

	balances = get_account_balances(company, from_date, to_date)
	boxes = compute_boxes(balances)
	vat_balances = {
		number: balance
		for number, balance in balances.items()
		if VAT_ACCOUNT_RANGE[0] <= number <= VAT_ACCOUNT_RANGE[1] and len(number) == 4 and flt(balance, 2)
	}
	if not vat_balances:
		frappe.throw(_("Det finns inga momssaldon att föra om för perioden"))

	rows = [_je_row(company, number, -balance) for number, balance in sorted(vat_balances.items())]
	# Summan av omföringsraderna (debet - kredit) motsvarar -saldot; 2650 får ruta 49 och öresresten 3740
	closing = -sum(vat_balances.values())
	rows.append(_je_row(company, SETTLEMENT_ACCOUNT, -boxes["49"]))
	remainder = flt(closing - boxes["49"], 2)
	if remainder:
		rows.append(_je_row(company, ROUNDING_ACCOUNT, -remainder, with_cost_center=True))

	je = frappe.get_doc(
		{
			"doctype": "Journal Entry",
			"voucher_type": "Journal Entry",
			"company": company,
			"posting_date": to_date,
			"se_vat_settlement_period": period,
			"user_remark": _("Momsomföring {0}").format(period),
			"accounts": rows,
		}
	)
	je.insert()
	return je.name


def _je_row(company: str, number: str, amount: float, with_cost_center: bool = False) -> dict:
	"""Rad med belopp som debet (positivt) eller kredit (negativt)."""
	account = frappe.db.get_value("Account", {"company": company, "account_number": number, "is_group": 0})
	if not account:
		frappe.throw(_("Konto {0} saknas i kontoplanen").format(number))
	row = {
		"account": account,
		"debit_in_account_currency": flt(amount, 2) if amount > 0 else 0,
		"credit_in_account_currency": flt(-amount, 2) if amount < 0 else 0,
	}
	if with_cost_center:
		row["cost_center"] = frappe.get_cached_value("Company", company, "cost_center")
	return row


# Redovisningsperiod ------------------------------------------------------------------------------

MANAD, KVARTAL, AR = "Månad", "Kvartal", "År"
BENAMNING = {MANAD: "per månad", KVARTAL: "per kvartal", AR: "per år"}


def perioden(typ: str | None, datum, rakenskapsar) -> tuple[date, date]:
	"""Redovisningsperioden som innehåller datumet. `rakenskapsar(datum)` ger räkenskapsårets start och slut."""
	datum = getdate(datum)
	if typ == MANAD:
		return datum.replace(day=1), datum.replace(day=calendar.monthrange(datum.year, datum.month)[1])
	if typ == KVARTAL:
		forsta = 3 * ((datum.month - 1) // 3) + 1
		sista = forsta + 2
		return date(datum.year, forsta, 1), date(datum.year, sista, calendar.monthrange(datum.year, sista)[1])
	return rakenskapsar(datum)


def _momsperiod(company: str) -> str:
	return frappe.db.get_value("Company", company, "se_momsperiod") or AR


def _rakenskapsar(company: str):
	def ar(datum):
		fy = get_fiscal_year(datum, company=company, as_dict=True)
		return getdate(fy.year_start_date), getdate(fy.year_end_date)

	return ar


def bolagets_period(company: str, datum) -> tuple[date, date]:
	return perioden(_momsperiod(company), datum, _rakenskapsar(company))


def senaste_avslutade_period(company: str, idag=None) -> tuple[date, date]:
	start, _slut = bolagets_period(company, idag or getdate())
	return bolagets_period(company, start - timedelta(days=1))


def kontrollera_period(company: str, from_date, to_date) -> None:
	"""Stoppa om datumen inte är exakt en redovisningsperiod för bolaget."""
	ratt = bolagets_period(company, from_date)
	if (getdate(from_date), getdate(to_date)) != ratt:
		_fel_period(company, ratt)


def kontrollera_periodslut(company: str, to_date) -> None:
	"""Stoppa om datumet inte är sista dagen i en redovisningsperiod."""
	ratt = bolagets_period(company, to_date)
	if getdate(to_date) != ratt[1]:
		_fel_period(company, ratt)


def _fel_period(company: str, ratt: tuple[date, date]) -> None:
	frappe.throw(
		_("Bolaget redovisar moms {0}. Välj en hel period, t.ex. {1} – {2}.").format(
			_(BENAMNING[_momsperiod(company)]), ratt[0], ratt[1]
		)
	)


@frappe.whitelist()
def standardperiod(company: str) -> dict:
	"""Senaste avslutade redovisningsperioden, förval i rapporten."""
	start, slut = senaste_avslutade_period(company)
	return {"from_date": str(start), "to_date": str(slut)}
