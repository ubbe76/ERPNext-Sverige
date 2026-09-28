"""Tolka Bankgirots inbetalningsfil BgMax (Bankgiro Inbetalningar).

Filen har poster om 80 tecken där de två första tecknen är transaktionskoden. Positioner nedan är
1-baserade som i Bankgirots tekniska manual. Belopp anges i öre.

Verifiera mot Bankgirots aktuella manual för BgMax och en riktig fil från banken innan skarp användning.
"""

from dataclasses import dataclass, field
from datetime import date

ENCODING = "iso-8859-1"


@dataclass
class BgMaxPayment:
	amount: float
	reference: str = ""
	reference_code: str = ""  # 2 = OCR/betalningsreferens, 3-5 = annan referens, 0/1 = ingen
	payer_bankgiro: str = ""
	bgc_serial: str = ""  # Bankgirots löpnummer, unikt per betalning
	payer_name: str = ""
	payer_address: str = ""
	payer_org_nr: str = ""
	information: list[str] = field(default_factory=list)
	is_deduction: bool = False
	payment_date: date | None = None
	receiving_bankgiro: str = ""


@dataclass
class BgMaxFile:
	created: str = ""
	test_mark: bool = False
	payments: list[BgMaxPayment] = field(default_factory=list)


class BgMaxError(ValueError):
	pass


def _field(line: str, start: int, end: int) -> str:
	"""Tecken start..end (1-baserat, inklusive)."""
	return line[start - 1 : end]


def _amount(value: str) -> float:
	value = value.strip() or "0"
	if not value.isdigit():
		raise BgMaxError(f"Ogiltigt belopp: {value!r}")
	return int(value) / 100


def _date(value: str) -> date:
	return date(int(value[0:4]), int(value[4:6]), int(value[6:8]))


def parse_bgmax(content: bytes | str) -> BgMaxFile:
	text = content.decode(ENCODING) if isinstance(content, bytes) else content
	lines = [line.rstrip("\r\n") for line in text.splitlines() if line.strip()]
	if not lines or not lines[0].startswith("01BGMAX"):
		raise BgMaxError("Filen är inte en BgMax-fil (startposten 01BGMAX saknas)")

	result = BgMaxFile(created=_field(lines[0], 25, 44).strip(), test_mark=_field(lines[0], 45, 45) == "T")
	section: list[BgMaxPayment] = []  # betalningar i aktuell insättning
	receiving_bankgiro = ""
	current: BgMaxPayment | None = None

	for number, line in enumerate(lines[1:], start=2):
		code = line[:2]
		if code == "05":  # öppningspost
			receiving_bankgiro = _field(line, 3, 12).lstrip("0")
			section = []
		elif code in ("20", "21"):  # betalnings- och avdragspost
			amount = _amount(_field(line, 38, 55))
			current = BgMaxPayment(
				amount=-amount if code == "21" else amount,
				payer_bankgiro=_field(line, 3, 12).lstrip("0"),
				reference=_field(line, 13, 37).strip(),
				reference_code=_field(line, 56, 56),
				bgc_serial=_field(line, 58, 69).strip(),
				is_deduction=code == "21",
				receiving_bankgiro=receiving_bankgiro,
			)
			section.append(current)
			result.payments.append(current)
		elif current and code in ("22", "23"):  # extra referensnummer
			current.information.append(f"Extra referens: {_field(line, 13, 37).strip()}")
		elif current and code == "25":  # informationspost
			current.information.append(_field(line, 3, 52).strip())
		elif current and code == "26":  # namnpost
			current.payer_name = " ".join(
				filter(None, (_field(line, 3, 37).strip(), _field(line, 38, 72).strip()))
			)
		elif current and code == "27":  # adresspost 1
			current.payer_address = " ".join(
				filter(None, (_field(line, 3, 37).strip(), _field(line, 38, 46).strip()))
			)
		elif current and code == "29":  # organisationsnummerpost
			current.payer_org_nr = _field(line, 3, 14).strip()
		elif code == "15":  # insättningspost: betalningsdag för betalningarna i insättningen
			payment_date = _date(_field(line, 38, 45))
			for payment in section:
				payment.payment_date = payment_date
			section = []
			current = None
		elif code == "70":  # slutpost
			expected = int(_field(line, 3, 10) or 0)
			found = sum(1 for p in result.payments if not p.is_deduction)
			if expected != found:
				raise BgMaxError(f"Slutposten anger {expected} betalningar men filen innehåller {found}")
		elif code not in ("28",):
			raise BgMaxError(f"Okänd transaktionskod {code!r} på rad {number}")

	return result
