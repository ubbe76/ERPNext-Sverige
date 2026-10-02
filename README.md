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
- OCR-nummer med längd- och kontrollsiffra (Bankgirots standard) om **OCR-nummer på fakturor** är ikryssat på bolaget (inte på kreditfakturor och kassafakturor)
- kreditfakturor skrivs ut som "Kreditfaktura" med hänvisning till originalfakturan, utan förfallodatum
- **fakturanummer utan luckor**: fältet *Fakturanummer* sätts när fakturan bokförs, i en serie per bolag och år
  (2026-0001, 2026-0002 …) som även omfattar kreditfakturor. ERPNext ger fakturan sitt namn (ACC-SINV-…)
  redan som utkast, så raderade utkast lämnar luckor i det namnet. Fakturanumret är det som skrivs ut och som
  kreditfakturor hänvisar till; ERPNext:s namn är kvar som internt id. Fakturor bokförda före funktionen visar
  ERPNext:s namn

Mallen följer kundens språk: svenska, eller engelska för kunder med engelska som språk.

PDF kräver att wkhtmltopdf är installerat, eller att Chrome-generatorn väljs i Utskriftsinställningar.

### Bankfiler

**Bankgiroinbetalning** (Inbetalningar): ladda upp inbetalningsfilen från banken eller Bankgirot (BgMax) och
klicka **Läs in fil**. Varje betalning matchas mot en bokförd kundfaktura via OCR-numret och blir en betalning i
utkastläge på bolagets bankkonto (1930). Betalningar som inte matchar listas; välj kundfaktura på raden och klicka
**Skapa betalningar för valda fakturor**. **Bokför betalningar** bokför alla utkast. Samma betalning (Bankgirots
löpnummer) kan inte registreras två gånger.

**Leverantörsbetalning** (Utbetalningar): välj bolagets bankkonto och betalningsdag, klicka **Hämta förfallna
fakturor** och sedan **Skapa betalfil**. Filen följer ISO 20022 pain.001.001.03 och laddas upp i internetbanken.
Samtidigt skapas betalningar i utkastläge som bokförs med **Bokför betalningar** när banken har betalat.

- Leverantörens betalningsuppgifter hämtas från leverantörens Bank Account (bankgiro, plusgiro, clearing- och
  kontonummer eller IBAN/BIC). Bank Account kräver en bank; skapa t.ex. banken "Bankgirot" för bankgirokonton.
- Leverantörens OCR-nummer skrivs i fältet **OCR / betalningsreferens** på leverantörsfakturan och skickas som
  strukturerad referens. Annars används leverantörens fakturanummer.
- Bara fakturor i SEK.

Filformaten är skrivna enligt Bankgirots och bankernas anvisningar men **ska provas mot banken** innan skarp användning.

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
- Brevhuvudet **Brevhuvud Sverige** (logotyp och bolagsnamn) som standard i stället för ERPNext:s, som
  skriver ut dokumenttypen på engelska. Ett eget standardbrevhuvud behålls.

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

**Lås perioden** låser bokföringen till och med periodens slutdatum när deklarationen är inlämnad och
momsomföringen bokförd (bolagets *Accounts Frozen Till Date*). Därefter går det inte att bokföra, ändra eller
makulera något med datum i perioden, inte heller som Administrator. Knappen vägrar om det finns utkast i
perioden, låser aldrig framtida datum och flyttar aldrig ett låsdatum bakåt. Bara Accounts Manager och System
Manager kan låsa. Ett felaktigt låsdatum ändras på bolaget av System Manager.

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

### Frakt via Sendify

Transportbokning via [Sendify](https://www.sendify.se), som förmedlar bland annat DHL, UPS, DSV, PostNord och
Schenker. Modulen **Frakt** bygger på ERPNext:s Shipment (försändelse).

**Inställningar** (Fraktinställningar): miljö (Sandlåda eller Produktion), API-nyckel (skapas i Sendify under
*Settings → API*, sparas krypterad), avsändande bolag, adress och kontakt, upphämtningstider, påslag på
fraktpriset (procent och/eller kronor) och fraktartikeln. **Testa anslutning** kontrollerar nyckeln och
**Hämta transportörsprodukter** fyller registret Fraktprodukt. Frakten används först när **Aktiverad** är ikryssad.

**Kollin**: på artikeln anges fraktsätt, antingen egna mått (längd, bredd, höjd, eventuellt pallplatser som räknas
om till flakmeter) eller en förpackningstyp (t.ex. EUR-pall) med antal per förpackning. Utifrån det föreslås kollin.

**Boka**:

1. På en godkänd följesedel skapar **Skapa → Boka transport** en försändelse med föreslagna kollin, som går att
   ändra (**Föreslå kollin igen** gör ett nytt förslag).
2. **Hämta priser** visar alla transportörers priser och kundpris. Välj och **Boka**, eller **Spara val** och boka
   senare. En kund kan ha en förvald fraktprodukt som bokas direkt med **Boka med förval**.
3. Vid bokning beställs alltid upphämtning. Transportör och fraktsedelsnummer skrivs på följesedeln, och
   fraktsedel och etikett sparas som PDF-bilagor på försändelsen (**Hämta fraktsedel** hämtar dem igen).
4. Har priset ändrats mer än **Bekräfta prisändring över (%)** (standard 5 %) sedan valet sparades måste
   ändringen bekräftas. Ett utgånget pris måste hämtas igen.

Avbryts försändelsen i ERPNext avbokas den hos Sendify.

**Spårning** hämtas varje timme för bokade försändelser och visas på försändelsen (**Uppdatera spårning**,
**Öppna spårning**). Vid leverans blir försändelsen *Completed*, och avvikelser hos transportören visas.

**Frakt på fakturan**: när en kundfaktura skapas från en följesedel med bokad försändelse läggs frakten till som
en rad med fraktartikeln (kundpris = Sendifys pris plus påslag). Raden går att ändra. På offert och
försäljningsorder hämtar **Kontrollera fraktpris** priser utan att boka, och **Lägg till frakt** lägger frakten på
ordern, som då inte faktureras igen från försändelsen.

I sandlådan fungerar fullständig bokning bara med DHL, UPS och DSV, och spårningen ger bara händelsen `ORDERED`.
Ombud, tull, egen inlämning och flera Sendify-konton stöds inte än.

### Skyddade bilagor

Ett kvitto eller en inskannad leverantörsfaktura är själva verifikationen och ska bevaras (bokföringslagen 5 och
7 kap.). En bilaga på ett **bokfört eller makulerat** dokument kan därför inte tas bort eller flyttas till ett
annat dokument. Nya bilagor går att lägga till efter bokföring, och bilagor på utkast kan tas bort som vanligt.

### Backup och arkivering

Bokföringslagen (7 kap.) kräver att räkenskapsinformationen bevaras i **7 år** efter räkenskapsårets slut, i
varaktigt skick. `backup/erpnext-backup.sh` tar backup av databas och filer, krypterar den med gpg (AES-256) och
laddar upp den till ett eller flera molnlager via [rclone](https://rclone.org), till exempel OneDrive, Google Drive
och Backblaze B2. Varje mål får en egen, fullständig kopia.

| Mapp per mål och site | Innehåll | Sparas |
|---|---|---|
| `daglig/ÅÅÅÅ-MM-DD/` | daglig backup | 30 dagar (`DAILY_DAYS`) |
| `manad/ÅÅÅÅ-MM/` | första backupen varje månad | 8 år (`MONTHLY_YEARS`) |
| `arkiv/ÅÅÅÅ/` | årsarkiv: backup + SIE 4-fil per bolag | raderas aldrig |

**Inställning** (en gång):

```bash
# 1. Logga in på molntjänsterna (öppnar webbläsaren). Välj t.ex. namnen onedrive, gdrive och b2.
rclone config

# 2. Konfiguration och lösenfras
mkdir -p ~/.config/erpnext-backup
cp apps/erpnext_sverige/backup/config.example ~/.config/erpnext-backup/config   # anpassa REMOTES och SITES
openssl rand -base64 32 > ~/.config/erpnext-backup/passphrase
chmod 600 ~/.config/erpnext-backup/*

# 3. Prova och schemalägg (varje natt kl. 02:30)
apps/erpnext_sverige/backup/erpnext-backup.sh
crontab -e   # 30 2 * * * <bench>/apps/erpnext_sverige/backup/erpnext-backup.sh >> <bench>/logs/erpnext-backup.log 2>&1
```

> **Spara lösenfrasen i en lösenordshanterare.** Utan den går backupen inte att läsa, och den finns annars bara
> på den här datorn.

**Årsarkiv**: kör efter bokslutet för året, t.ex. `erpnext-backup.sh arkiv 2026`.

**Återställning**:

```bash
rclone copy onedrive:ERPNext-backup/<site>/manad/2026-10/ ./aterstall/
gpg -d ./aterstall/<fil>.tar.gpg | tar -xf - -C ./aterstall/
bench --site <site> restore ./aterstall/backup/*-database.sql.gz \
  --with-public-files ./aterstall/backup/*-files.tar --with-private-files ./aterstall/backup/*-private-files.tar
```

Kontrollera loggen regelbundet. En körning som misslyckas skriver `KLART MED FEL` och avslutas med felkod.

### Kontrollskript för nya strängar

När Frappe eller ERPNext uppdateras kan nya strängar med särskrivningar tillkomma. Skriptet
`erpnext_sverige/scripts/sarskrivningar.py` listar dem:

```bash
bench --site <site> execute erpnext_sverige.scripts.sarskrivningar.report --kwargs "{'title_case_only': True}"
```

Utan `title_case_only` listas fler kandidater, men då följer också fler falsklarm med.

## Planerat

Se [TODO.md](TODO.md). Det viktigaste:

- **PAXml-export** av tid och frånvaro till svenska lönesystem (t.ex. Visma Lön, Hogia, Fortnox Lön)
- **Frakt, etapp 2 och 3**: leverans till ombud för privatpersoner och tullinformation vid export utanför EU
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
bench --site <testsite> run-tests --module erpnext_sverige.tests.test_credit_notes
bench --site <testsite> run-tests --module erpnext_sverige.tests.test_bgmax
bench --site <testsite> run-tests --module erpnext_sverige.tests.test_pain001
```

Stilregler för översättningarna:
- Skriv sammansatta ord ihop: Artikelgrupp, Leverantörsgrupp, Bankkonto.
- Stor bokstav bara först i en etikett eller mening, och i egennamn.
- Följ BAS-terminologin där den finns, till exempel Resultatenhet och Bokföringsår.

## Licens

Copyright (C) 2026 Urban Källefors

GPL-3.0, samma licens som ERPNext. Se [LICENSE](LICENSE).
