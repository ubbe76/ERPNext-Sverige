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

### Momskategori för utländska kunder och leverantörer

Momskategorin (Svensk moms, EU eller Utanför EU) sätts automatiskt utifrån landet i adressen när den sparas,
och kunden eller leverantören får samma kategori om den saknar en. ERPNext använder adressens kategori på
fakturan, så en kund med adresser i flera länder får rätt moms per faktura.

- Privatpersoner i andra EU-länder får svensk moms (omvänd skattskyldighet gäller bara företag).
- En manuellt vald kategori skrivs inte över, utom när adressens land eller kundtypen ändras.
- Momsregistreringsnumret för EU-företag kontrolleras (landskod och format) när kunden sparas, och en
  EU-faktura kan inte bokföras utan kundens momsregistreringsnummer.
- Knappen **Kontrollera i VIES** på kund och leverantör frågar EU-kommissionens register om numret är giltigt
  och visar företagets namn och adress.

### Fakturamall "Faktura Sverige"

Standardmall för kundfakturor med det som mervärdesskattelagen kräver:

- organisationsnummer och momsregistreringsnummer (räknas fram ur bolagets Tax ID)
- underlag och moms per momssats, samt kundens momsregistreringsnummer
- hänvisning vid EU-försäljning ("Omvänd skattskyldighet", "Unionsintern leverans") och export, på svenska och engelska
- "Godkänd för F-skatt" om rutan **Godkänd för F-skatt** är ikryssad på bolaget
- bankgiro, plusgiro, clearing- och kontonummer, IBAN och BIC från bolagets bankkonto (Bank Account med
  "Company Account"; bankgiro och plusgiro är nya fält)
- OCR-nummer med längd- och kontrollsiffra (Bankgirots standard) om **OCR-nummer på fakturor** är ikryssat på bolaget

Mallen följer kundens språk: svenska, eller engelska för kunder med engelska som språk.

PDF kräver att wkhtmltopdf är installerat, eller att Chrome-generatorn väljs i Utskriftsinställningar.

### Grunduppsättning av bokföring och moms

`erpnext_sverige.setup.company.setup_swedish_company` sätter upp ett bolag med BAS-kontoplan för svensk
bokföring. Funktionen går att köra flera gånger utan att något dubbleras.

- Svenskt talformat (1 234,56), kronor efter beloppet (1 234,56 kr) och måndag som första veckodag
- Standardkonton på bolaget (kundfordringar 1510, leverantörsskulder 2440, bank, kassa, kostnad för sålda varor,
  kursdifferenser, öresutjämning, kassarabatt m.m.)
- **Immutable Ledger**, så att verifikationer inte kan ändras i efterhand, bara rättas (Bokföringslagen)
- Momsmallar som bokför på rätt BAS-konton (2611/2621/2631/2641)
- Momskategorier med skatteregler för Sverige, EU (omvänd skattskyldighet) och länder utanför EU
- Artikelmomsmallar för 12 %, 6 % och momsfritt

```bash
bench --site <site> execute erpnext_sverige.setup.company.setup_swedish_company --kwargs "{'company': '<bolag>'}"
```

### Automatiskt kontoval på fakturor

På kund- och leverantörsfakturor sätter appen intäkts- och kostnadskonto enligt BAS utifrån fakturans
momskategori, artikelns momssats och om artikeln är en vara eller en tjänst (nytt fält
**Vara eller tjänst (moms)** på artikeln; tomt = lagerartiklar är varor, övriga tjänster).

| Momskategori | Försäljning | Inköp |
|---|---|---|
| Svensk moms | 3001 (25 %), 3002 (12 %), 3003 (6 %), 3004 (momsfri) | ändras inte |
| EU | 3108 varor, 3308 tjänster | 4515–4517 varor, 4535 tjänster |
| Utanför EU | 3105 varor, 3305 tjänster | 4545 varor, 4531 tjänster |

Ett konto som har valts manuellt utanför dessa, till exempel 3590, lämnas orört. Inköp av lagerartiklar bokförs
som tidigare mot lagret.

### Momsdeklaration

Rapporten **Momsdeklaration** (Redovisning → rapporter, modul Sweden Compliance) räknar fram Skatteverkets
rutor 05–62 och 49 ur huvudboken för vald period, utifrån BAS-kontonummer. Makulerade verifikationer, bokslut
och momsomföringar räknas inte med. Beloppen anges i hela kronor, och öretal stryks.

- **Ladda ner eSKD-fil**: fil för uppladdning i Skatteverkets e-tjänst för momsdeklaration.
  **Verifiera formatet mot Skatteverkets aktuella specifikation innan filen används på riktigt.**
- **Skapa momsomföring**: skapar en journalpost som **utkast**, daterad periodens sista dag, som nollställer
  momskontona (2610–2649) mot 2650. Öresavrundningen bokförs på 3740. Granska och bokför den själv.

Rutorna 06, 07, 08, 37 och 38 stöds inte än och är alltid 0.

### SIE-export

Rapporten **SIE-export** (modul Sweden Compliance) sammanställer verifikationerna per serie för valt
räkenskapsår. Knappen **Ladda ner SIE-fil** ger en SIE 4-fil (PC8) till revisor eller bokslutsprogram med:

- bolagsuppgifter, kontoplan och kontotyper
- ingående och utgående balanser (`#IB`/`#UB`) och periodens resultat (`#RES`), även för föregående år om det finns
- resultatenheter som dimension 1 (kostnadsställe) och projekt som dimension 6
- alla verifikationer med rader (`#VER`/`#TRANS`) i serierna A journalposter, B kundfakturor,
  C leverantörsfakturor, D betalningar, E lager och F övrigt, numrerade i datumordning. ERPNext-namnet står
  i verifikationstexten. En makulering exporteras som en egen verifikation, "Makulering av …".

Bokslutsverifikationer (Period Closing Voucher) exporteras inte, eftersom det mottagande programmet gör eget bokslut.

### Kontrollskript för nya strängar

När Frappe eller ERPNext uppdateras kan nya strängar med särskrivningar tillkomma. Skriptet
`erpnext_sverige/scripts/sarskrivningar.py` listar dem:

```bash
bench --site <site> execute erpnext_sverige.scripts.sarskrivningar.report --kwargs "{'title_case_only': True}"
```

Utan `title_case_only` listas fler kandidater, men då följer också fler falsklarm med.

## Planerat

Se [TODO.md](TODO.md). Det viktigaste:

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

### Tester

Integrationstesterna skapar ett eget testbolag, `_Test Svenska AB`, med ERPNext:s BAS-kontoplan och kör
appens grunduppsättning på det. Kör dem på en testsite, inte på den riktiga:

```bash
bench --site <testsite> set-config allow_tests true
bench --site <testsite> run-tests --module erpnext_sverige.tests.test_account_selection
bench --site <testsite> run-tests --module erpnext_sverige.tests.test_vat_return
bench --site <testsite> run-tests --module erpnext_sverige.tests.test_sie_export
bench --site <testsite> run-tests --module erpnext_sverige.tests.test_invoice
bench --site <testsite> run-tests --module erpnext_sverige.tests.test_tax_category
```

Stilregler för översättningarna:
- Skriv sammansatta ord ihop: Artikelgrupp, Leverantörsgrupp, Bankkonto.
- Stor bokstav bara först i en etikett eller mening, och i egennamn.
- Följ BAS-terminologin där den finns, till exempel Resultatenhet och Bokföringsår.

## Licens

Copyright (C) 2026 Urban Källefors

GPL-3.0, samma licens som ERPNext. Se [LICENSE](LICENSE).
