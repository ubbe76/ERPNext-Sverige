# ERPNext Sverige

Svensk lokalisering av [ERPNext](https://github.com/frappe/erpnext) version 16.

Appen installeras ovanpå ERPNext och anpassar systemet för svenska bolag, utan att ändra i ERPNext:s egen kod.

## Vad appen gör i dag

### Rättade svenska översättningar

ERPNext:s svenska översättning skriver isär sammansatta ord och använder engelska versaler. Appen levererar
en egen översättningskatalog (`erpnext_sverige/locale/sv.po`) med drygt 11 000 rättade strängar från
Frappe och ERPNext. Katalogen laddas efter deras egna, och därför ersätter den deras översättningar.

| Engelska | ERPNext | ERPNext Sverige |
|---|---|---|
| Cost Center | Resultat Enheter | Resultatenhet |
| Mode of Payment | Betalning Sätt | Betalsätt |
| Payment Terms | Betalning Villkor | Betalningsvillkor |
| Fiscal Year | Bokföring År | Bokföringsår |
| Accounts Settings | Bokföring Inställningar | Bokföringsinställningar |
| Party | Parti | Part |

Utöver särskrivningar och versaler har även böjningsfel och ett antal rena felöversättningar rättats. Ett
exempel är "Party" (motpart), som tidigare översattes med "Parti", det vill säga batch.

### Kontrollskript för nya strängar

När Frappe eller ERPNext uppdateras kan nya strängar med särskrivningar tillkomma. Skriptet
`erpnext_sverige/scripts/sarskrivningar.py` listar dem:

```bash
bench --site <site> execute erpnext_sverige.scripts.sarskrivningar.report --kwargs "{'title_case_only': True}"
```

Utan `title_case_only` listas fler kandidater, men då följer också fler falsklarm med.

## Planerat

Se [TODO.md](TODO.md). Det viktigaste:

- **SIE-export (SIE 4)** till revisor och bokslutsprogram
- **Momsdeklaration** med Skatteverkets rutor
- **Fakturamall** som uppfyller svenska krav: organisationsnummer, momsregistreringsnummer, F-skatt,
  bankgiro och OCR-nummer
- Bankfiler för Bankgirot
- **PAXml-export** av tid och frånvaro till svenska lönesystem (t.ex. Visma Lön, Hogia, Fortnox Lön)
- **Transportbokning i Sverige**: boka frakt, skriv ut fraktsedlar och spåra sändningar hos t.ex. PostNord,
  DHL, Schenker och Bring
- **E-faktura för Sverige**: skicka och ta emot fakturor enligt Peppol BIS Billing 3.0, vilket är krav vid
  fakturering till offentlig sektor

## Installation

Krav: en [bench](https://github.com/frappe/bench) med `frappe` och `erpnext` på branchen `version-16`.

```bash
cd ~/frappe-bench
bench get-app https://github.com/ubbe76/ERPNext-Sverige --branch version-16
bench --site <site> install-app erpnext_sverige
bench compile-po-to-mo --app erpnext_sverige --locale sv
bench --site <site> clear-cache
```

Repot är privat. Datorn som hämtar appen måste vara inloggad på GitHub, till exempel med `gh auth login`.

Användaren måste ha språket **Svenska (sv)** valt för att se översättningarna. Ladda om sidan i webbläsaren
med Ctrl+Shift+R efter installationen.

## Utveckling

Appen använder [pre-commit](https://pre-commit.com/) för ruff, prettier, eslint och grundläggande
filkontroller:

```bash
cd apps/erpnext_sverige
pre-commit install
pre-commit run --all-files
```

När en krok formaterar om en fil markeras den som `Failed` med meddelandet "files were modified by this hook".
Granska ändringen med `git diff`, lägg till filen och committa igen.

### Ändra översättningar

1. Redigera `erpnext_sverige/locale/sv.po`. Använd samma `msgid` (och eventuell `msgctxt`) som i
   Frappe/ERPNext och lägg den rättade texten i `msgstr`.
2. Kompilera och töm cachen:
   ```bash
   bench compile-po-to-mo --app erpnext_sverige --locale sv --force
   bench --site <site> clear-cache
   ```

Ändra aldrig `sv.po` i `apps/frappe` eller `apps/erpnext`. De filerna skrivs över vid `bench update`.

Stilregler för översättningarna:
- Skriv sammansatta ord ihop: Artikelgrupp, Leverantörsgrupp, Bankkonto.
- Stor bokstav bara först i en etikett eller mening, och i egennamn.
- Följ BAS-terminologin där den finns, till exempel Resultatenhet och Bokföringsår.

## Licens

GPL-3.0, samma licens som ERPNext. Se [LICENSE](LICENSE).
