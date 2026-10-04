<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset=".github/images/erpnext-sverige-dark.svg">
    <img alt="ERPNext Sverige" src=".github/images/erpnext-sverige.svg" width="420">
  </picture>
</p>

# ERPNext Sverige

> [!IMPORTANT]
> **Under utveckling.** Appen har automatiska tester, och eSKD-filen för momsdeklarationen är provad hos
> Skatteverket. Bankfilerna och frakten är däremot ännu inte provade skarpt mot bank och transportör. Prova på
> en testsite först och stäm av resultatet mot bokföringen. Vad som återstår står i [TODO.md](TODO.md).

Svensk lokalisering av [ERPNext](https://github.com/frappe/erpnext) version 16.

Appen installeras ovanpå ERPNext och anpassar systemet för svenska bolag, utan att ändra i ERPNext:s egen kod.

## Vad appen gör i dag

### Rättade svenska översättningar

ERPNext:s svenska översättning skriver isär sammansatta ord, använder engelska versaler och har många rena
felöversättningar. Appen levererar en egen översättningskatalog (`erpnext_sverige/locale/sv.po`) med drygt
11 000 rättade strängar från Frappe och ERPNext. Katalogen laddas efter deras egna, och därför ersätter den
deras översättningar. Alla ERPNext-moduler är granskade, och begreppen följer svensk bokförings- och
affärsterminologi:

| Engelska | ERPNext | ERPNext Sverige |
|---|---|---|
| Cost Center | Resultat Enheter | Resultatenhet |
| Party | Parti (batch) | Part |
| Journal Entry | Journalpost | Verifikation |
| General Ledger | Bokföringsregister | Huvudbok |
| Balance Sheet / Profit and Loss | Balansrapport / Resultatrapport | Balansräkning / Resultaträkning |
| Accounts Receivable / Payable | Fordringar / Skulder | Kundreskontra / Leverantörsreskontra |
| Sales / Purchase Invoice | Försäljningsfaktura / Inköpsfaktura | Kundfaktura / Leverantörsfaktura |
| Tax Withholding | Momsavdrag | Källskatt |
| Purchase Receipt | Inköpsföljesedel | Inleverans |
| Work Order / Job Card | Arbetsorder / Jobbkort | Tillverkningsorder / Operationskort |
| Operation / Workstation | Åtgärd / Arbetsplats | Operation / Arbetsstation |
| Stores (standardlager) | Butiker | Lager |

Hela ordlistan finns under [Ändra översättningar](#ändra-översättningar).

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

### Svenska utskriftsmallar

Appen har svenska mallar som är standard för respektive dokument: **Faktura Sverige** (kundfaktura), **Offert
Sverige**, **Orderbekräftelse Sverige**, **Följesedel Sverige** och **Inköpsorder Sverige**. De har samma
utseende, med brevhuvud, dokumentuppgifter, artikelrader och en sidfot med bolagets adress, organisationsnummer,
momsregistreringsnummer och F-skatt.

Fakturamallen har det som mervärdesskattelagen kräver:

- organisationsnummer (bolagets Tax ID) och momsregistreringsnummer (bolagets fält **Momsregistreringsnummer**,
  som fylls i som SE + organisationsnummer + 01; töm det om bolaget inte är momsregistrerat, då skrivs inget
  nummer ut)
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

Båda finns i menyn **Svensk bokföring** under *Bankfiler*.

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
- Brevhuvudet **Brevhuvud Sverige** som standard i stället för ERPNext:s, som skriver ut dokumenttypen på
  engelska. Det visar bolagets logotyp (fältet Logotyp, bilden i bolagsformulärets sidopanel), eller
  bolagsnamnet om logotyp saknas. Ett eget standardbrevhuvud behålls.

```bash
bench --site <site> execute erpnext_sverige.setup.company.setup_swedish_company --kwargs "{'company': '<bolag>'}"
```

Bolaget får också fälten **Momsregistreringsnummer**, **Godkänd för F-skatt**, **OCR-nummer på fakturor** och
**Redovisningsperiod för moms**. ERPNext:s standardlager *Stores* heter **Lager**, och befintliga lager med det
gamla namnet "Butiker" döps om vid migrering.

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

Rapporten **Momsdeklaration** (menyn **Svensk bokföring**) räknar fram Skatteverkets rutor 05–62 och 49 ur
huvudboken för vald period, utifrån BAS-kontonummer. Makulerade verifikationer, bokslut och momsomföringar
räknas inte med. Beloppen anges i hela kronor, och öretal stryks.

**Redovisningsperiod**: bolagets fält **Redovisningsperiod för moms** (Månad, Kvartal eller År enligt
Skatteverkets beslut; År är räkenskapsåret, även brutet). Rapporten öppnas med den senaste avslutade perioden,
under bolagets första år med det pågående året. Rutorna kan visas för valfria datum, men knapparna nedan kräver
en hel redovisningsperiod.

- **Ladda ner eSKD-fil**: fil för Skatteverkets e-tjänst "Lämna momsdeklaration via fil". Organisationsnumret
  skrivs som xxxxxx-xxxx, utan DOCTYPE och indrag, enligt Skatteverkets anvisningar. Formatet är provat genom
  uppladdning i e-tjänsten.
- **Skapa momsomföring**: skapar en verifikation som **utkast**, daterad periodens sista dag, som nollställer
  momskontona (2610–2649) mot 2650. Öresavrundningen bokförs på 3740. Granska och bokför den själv.

Rutorna 06, 07, 08, 37 och 38 stöds inte än och är alltid 0.

**Lås perioden** låser bokföringen till och med periodens slutdatum när deklarationen är inlämnad och
momsomföringen bokförd (bolagets *Accounts Frozen Till Date*). Därefter går det inte att bokföra, ändra eller
makulera något med datum i perioden, inte heller som Administrator. Knappen vägrar om det finns utkast i
perioden, låser bara vid slutet av en redovisningsperiod, låser aldrig framtida datum och flyttar aldrig ett
låsdatum bakåt. Bara Accounts Manager och System Manager kan låsa. Ett felaktigt låsdatum ändras på bolaget av
System Manager.

### Grundbok

Rapporten **Grundbok** (Svensk bokföring) visar bokföringsposterna i **registreringsordning**, som
bokföringslagen (5 kap. 1 §) kräver: registreringstidpunkt, bokföringsdatum, verifikation, konto, belopp, part
och vem som registrerade. Huvudboken i ERPNext sorteras i stället efter bokföringsdatum. Makuleringar visas som
egna rader där de registrerades.

### SIE-export

Rapporten **SIE-export** (menyn **Svensk bokföring**) sammanställer verifikationerna per serie för valt
räkenskapsår. Knappen **Ladda ner SIE-fil** ger en SIE 4-fil (PC8) till revisor eller bokslutsprogram med:

- bolagsuppgifter, kontoplan och kontotyper
- ingående och utgående balanser (`#IB`/`#UB`) och periodens resultat (`#RES`), även för föregående år om det finns
- resultatenheter som dimension 1 (kostnadsställe) och projekt som dimension 6
- alla verifikationer med rader (`#VER`/`#TRANS`) i serierna A verifikationer, B kundfakturor,
  C leverantörsfakturor, D betalningar, E lager och F övrigt, numrerade i datumordning. ERPNext-namnet står
  i verifikationstexten. En makulering exporteras som en egen verifikation, "Makulering av …".

Bokslutsverifikationer (Period Closing Voucher) exporteras inte, eftersom det mottagande programmet gör eget bokslut.

### Frakt via Sendify

Transportbokning via [Sendify](https://www.sendify.se), som förmedlar bland annat DHL, UPS, DSV, PostNord och
Schenker. Modulen **Frakt** bygger på ERPNext:s Shipment (försändelse).

**Inställningar** (Fraktinställningar): miljö (Sandlåda eller Produktion), API-nyckel (skapas i Sendify under
*Settings → API*, sparas krypterad), avsändande bolag, adress och kontakt, upphämtningstider, påslag på
fraktpriset (procent och/eller kronor) och fraktartikeln. Allt finns i menyn **Frakt**.

**Upphämtningstider** anges per veckodag (Från och Till), till exempel kortare fredag. En dag utan rad har ingen
upphämtning, och röda dagar i bolagets helglista har aldrig upphämtning (vanliga veckohelger räknas inte, så en
lördagsrad fungerar). En ny försändelse får nästa dag med upphämtning och den dagens tider. Ändras dagen på
försändelsen byts tiderna, och en dag utan upphämtning stoppar prishämtning och bokning. **Testa anslutning** kontrollerar nyckeln och
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

## Planerat

Se [TODO.md](TODO.md). Det viktigaste:

- **Frakt, etapp 2 och 3**: leverans till ombud för privatpersoner och tullinformation vid export utanför EU,
  och prov med riktiga bokningar (i dag provat mot Sendifys sandlåda)
- **E-faktura för Sverige**: skicka och ta emot fakturor enligt Peppol BIS Billing 3.0, vilket är krav vid
  fakturering till offentlig sektor
- **Momsdeklaration**: rutorna 06, 07, 08, 37 och 38

Lönefrågor (personal, frånvaro, stämpling och löneunderlag till lönesystem via PAXml) finns i den separata appen
[HRMS Sverige](https://github.com/ubbe76/HRMS-Sverige).

## Installation

Krav: en [bench](https://github.com/frappe/bench) med `frappe` och `erpnext` på branchen `version-16`.

Senast testad med frappe 16.36.1 och erpnext 16.37.0 (2026-10-04). CI kör testerna mot senaste `version-16` av
frappe och erpnext vid varje pull request.

```bash
cd ~/frappe-bench
bench get-app https://github.com/ubbe76/ERPNext-Sverige --branch version-16
bench --site <site> install-app erpnext_sverige
bench compile-po-to-mo --app erpnext_sverige --locale sv
bench --site <site> clear-cache
```

Sätt sedan upp bolaget med `setup_swedish_company` (se [Grunduppsättning](#grunduppsättning-av-bokföring-och-moms)).

Användaren måste ha språket **Svenska (sv)** valt för att se översättningarna. Ladda om sidan i webbläsaren
med Ctrl+Shift+R efter installationen.

Efter en uppdatering av appen: `bench --site <site> migrate`, och sedan `compile-po-to-mo` och `clear-cache`
som ovan om översättningarna har ändrats.

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

Ändra aldrig `sv.po` i `apps/frappe` eller `apps/erpnext`. De filerna skrivs över vid `bench update`. Appar som
installeras efter den här (till exempel `hrms`) kan skriva över samma strängar; kontrollera det vid ändringar.

Stilregler och ordlista:
- Skriv sammansatta ord ihop: Artikelgrupp, Leverantörsgrupp, Bankkonto.
- Stor bokstav bara först i en etikett eller mening, och i egennamn.
- Följ BAS-terminologin och bokföringslagens termer där de finns, till exempel Resultatenhet och Räkenskapsår.
- Bokföring: Verifikation (Journal Entry), Huvudbok (General Ledger), Balansräkning/Resultaträkning,
  Saldobalans (Trial Balance), Kundreskontra/Leverantörsreskontra (Accounts Receivable/Payable), Kundfaktura
  och Leverantörsfaktura (Sales/Purchase Invoice), Räkenskapsår (Fiscal Year), Källskatt (Tax Withholding,
  inte momsavdrag), Beskattningsunderlag (Taxable Amount), Part (Party, aldrig "Parti", som är batch).
- Försäljning, inköp och lager: Offert och Offertförfrågan (Quotation/RFQ), Följesedel (Delivery Note),
  Inleverans (Purchase Receipt), Materialinleverans (Material Receipt), Materialuttag (Material Issue),
  Lagerinventering (Stock Reconciliation), Beställningspunkt (Reorder Level), Affärsmöjlighet (Opportunity),
  Transportör (Carrier). ERPNext:s standardlager Stores heter Lager.
- Tillverkning: Operation (inte Åtgärd), Operationsföljd (Routing), Arbetsstation (Workstation),
  Tillverkningsorder (Work Order), Operationskort (Job Card), Färdigartikel (Finished Good).
- Utskriftsmallarnas egna etiketter har `msgctxt "Swedish print"` och ändras bara medvetet.
- Var försiktig med korta ord som delas med andra sammanhang ("Left" är också justeringen Vänster).

### Kontrollskript för nya strängar

När Frappe eller ERPNext uppdateras kan nya strängar med särskrivningar tillkomma. Skriptet
`erpnext_sverige/scripts/sarskrivningar.py` listar dem:

```bash
bench --site <site> execute erpnext_sverige.scripts.sarskrivningar.report --kwargs "{'title_case_only': True}"
```

Utan `title_case_only` listas fler kandidater, men då följer också fler falsklarm med.

### Tester

Integrationstesterna skapar ett eget testbolag, `_Test Svenska AB`, med ERPNext:s BAS-kontoplan och kör
appens grunduppsättning på det. Kör dem på en testsite, inte på den riktiga, och kör hela appen (enskilda
moduler kan stoppas av ERPNext:s egna testposter):

```bash
bench --site <testsite> set-config allow_tests true
bench --site <testsite> run-tests --app erpnext_sverige
```

### Testdata för tillverkning

`scripts/demodata_tillverkning.py` lägger in en påhittad plåt- och svetsverkstad i ett bolag på en test- eller
demosite: råmaterial, halvfabrikat och produkter med stycklistor (material och operationer), arbetsstationer
med timkostnad, leverantörer, kunder (även EU), priser och ett ingående lager av råmaterial. Lagren kopplas till
BAS-kontona 1410, 1440 och 1450. Skriptet skapar bara det som saknas och körs bara där `allow_tests` är på:

```bash
bench --site <demosite> set-config allow_tests true
bench --site <demosite> execute erpnext_sverige.scripts.demodata_tillverkning.skapa --kwargs "{'company': '<bolag>'}"
```

## Licens

Copyright (C) 2026 Urban Källefors

GPL-3.0, samma licens som ERPNext. Se [LICENSE](LICENSE).
