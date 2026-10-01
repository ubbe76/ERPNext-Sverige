> Ändrat 2026-10-01: frakten faktureras som artikelraden Fraktartikel (Fraktinställningar.fraktartikel), inte som skatterad på fraktkonto.

# Transportbokning via Sendify – design (etapp 1)

## Bakgrund

ERPNext har en doctype **Shipment** (försändelse) med avsändare, mottagare, kollitabell (Shipment Parcel: längd,
bredd, höjd, vikt, antal) och fält för transportörens svar (`carrier`, `carrier_service`, `shipment_id`,
`awb_number`, `tracking_url`, `tracking_status`, `shipment_amount`, `status` med värdet *Booked*). Följesedeln
kan redan skapa en Shipment. ERPNext har däremot ingen koppling till någon transportör, och artiklar har bara
vikt (`weight_per_unit`, `weight_uom`), inga mått.

**Sendify** (https://api.sendify.com/docs) är en svensk fraktaggregator (DHL, UPS, DSV, PostNord, Schenker med
flera) med ett REST-API:

- Autentisering med headern `x-api-key`. Sandlåda `https://app.dev.sendify.se/external/v1`, produktion
  `https://app.sendify.se/external/v1`.
- Bokningsflöde: `POST /shipments` (skapa) → `POST /shipments/rates` (priser, var och ett med `booking_token`)
  → `POST /shipments/book` → `POST /shipments/print` (etikett/fraktsedel som PDF-länk).
- Även `PUT /shipments/{id}`, `DELETE /shipments/{id}`, avbokning av bokad sändning,
  `GET /shipments/{id}/tracking`, `GET /carriers`, `GET /status`, ombud och webhooks.
- Kolli (`packages[]`): `width_cm`, `height_cm`, `depth_cm`, `weight_kg`, `quantity`, `type`
  (`PACKAGE`/`PALLET`/`UNSPECIFIED`), `stackable`, `description`, `loading_meters` (per enhet).
- Sändning: `from`/`to` (namn, adress, kontakt), `reference_id`, `sender_reference` och `receiver_reference`
  (de två senare trycks på etiketten).
- Prissvar: `carrier_code`, `carrier_name`, `product_name`, `price`, `currency`, ledtid i arbetsdagar,
  `expires_at`, upphämtningsfönster, beräknad leverans, samt `warnings` för transportörer som föll bort.

Kundfakturan visar redan frakt som en egen rad (skatterad på icke-momskonto, t.ex. 3520), och följesedelns
utskrift visar `transporter_name` ("Transportör") och `lr_no` ("Fraktsedelsnr").

## Mål

Etapp 1 (den här specen):

- Artiklar kan beskrivas för frakt: antingen **egna mått** eller **förpackningstyp med antal per förpackning**.
- Från en godkänd följesedel skapas en Shipment med **föreslagna kollin**, som användaren kan ändra.
- På Shipment visas **alla transportörers priser** i en dialog. Användaren kan boka, spara valet och boka senare,
  eller bara titta. Kunder kan ha en **förvald transportör/produkt** som bokas med ett klick.
- Bokning ger **fraktsedel och etikett** som PDF-bilaga, transportör och fraktsedelsnummer på följesedeln.
- **Avbokning** i Sendify när Shipment avbryts.
- **Spårning** hämtas regelbundet och visas på Shipment.
- **Frakt på fakturan**: Sendifys pris plus påslag, ändringsbart, som fraktrad.
- **Prisförfrågan på offert och försäljningsorder** som kan lägga frakt på ordern.
- Upphämtning beställs alltid.
- Sendify-koden är isolerad så att fler leverantörer kan läggas till senare utan omskrivning.

Senare etapper (egna specar):

- **Etapp 2 – Ombud:** leverans till privatpersoner via service points.
- **Etapp 3 – Export:** tullinformation för leveranser utanför EU.

Utanför etapp 1: ombud, tull, egen inlämning (`without_pickup`), webhooks, farligt gods, PrintNode,
mottagaren betalar, fler leverantörer än Sendify, flera bolag med olika Sendify-konton.

## Förutsättningar

- **Sendify-konto för sandlåda** måste skapas innan utveckling mot API:t kan testas på riktigt:
  registrera på https://se.sendify-staging.com/sign-up och skapa API-nyckel under *Settings → API*
  (alternativt mejla api@sendify.com). Nyckeln läggs i `site_config.json` för test-erp.local som
  `sendify_sandbox_api_key` (för röktestet) och i Fraktinställningar på den site som ska användas.
- **Produktionsnyckel** skapas i det riktiga Sendify-kontot under *Settings → API* när integrationen tas i drift.
- I sandlådan fungerar fullständig bokning bara med DHL, UPS och DSV, och spårningen ger bara händelsen
  `ORDERED`.

## Datamodell

Ny modul **Frakt** i `modules.txt`. Kod i `erpnext_sverige/frakt/`.

### Nya doctypes

**Förpackningstyp** (`forpackningstyp`) – pall- och kartongtyper.

| Fält | Typ | Beskrivning |
|---|---|---|
| `forpackningstyp_namn` | Data, unik, namn | T.ex. "EUR-pall", "Kartong 60×40" |
| `kollityp` | Select: Paket / Pall | Blir Sendifys `PACKAGE` / `PALLET` |
| `langd_cm`, `bredd_cm`, `hojd_cm` | Float | Mått för full förpackning |
| `egenvikt_kg` | Float | Förpackningens egen vikt |
| `stapelbar` | Check | Paket är alltid stapelbara hos Sendify |
| `flakmeter` | Float | Valfritt; tomt låter transportören räkna från måtten |

**Fraktinställningar** (`fraktinstallningar`, single).

| Fält | Typ | Beskrivning |
|---|---|---|
| `aktiverad` | Check | Knapparna visas bara när aktiverad |
| `leverantor` | Select: Sendify | Förberett för fler leverantörer |
| `miljo` | Select: Sandlåda / Produktion | Väljer bas-URL |
| `api_nyckel` | Password | Krypterad, loggas aldrig |
| `avsandaradress`, `avsandarkontakt` | Link Address / Contact | Standardavsändare (bolagets adress) |
| `paslag_procent`, `paslag_belopp` | Percent / Currency | Kundpris = pris × (1 + procent/100) + belopp, avrundat till hela kronor |
| `fraktkonto` | Link Account | Konto för fraktraden, standard bolagets 3520 |
| `sparning_intervall` | Select: Varje timme / Var fjärde timme / Dagligen | Spårningsjobbets intervall |
| `prisandring_grans_procent` | Percent, standard 5 | Prisändring som kräver bekräftelse vid "Boka vald produkt" |

**Fraktprodukt** (`fraktprodukt`) – transportörsprodukter, skapas automatiskt första gången de förekommer i ett
prissvar. Namn: `{transportor} – {produkt}`.

| Fält | Typ |
|---|---|
| `leverantor` | Data ("Sendify") |
| `transportorskod` | Data (Sendifys `carrier_code`) |
| `transportor` | Data (`carrier_name`) |
| `produkt` | Data (`product_name`) |

**Spårningshändelse** (`sparningshandelse`, undertabell på Shipment): `tidpunkt` (Datetime), `status` (Data),
`beskrivning` (Data), `plats` (Data).

### Custom fields (i `setup/custom_fields.py`)

**Item** – ny flik "Frakt":

| Fält | Typ | Visas när |
|---|---|---|
| `fraktsatt` | Select: (tom) / Egna mått / Förpackning | alltid |
| `frakt_langd_cm`, `frakt_bredd_cm`, `frakt_hojd_cm` | Float | Egna mått |
| `frakt_kollityp` | Select: Paket / Pall | Egna mått |
| `frakt_stapelbar` | Check | Egna mått |
| `frakt_flakmeter` | Float | Egna mått |
| `frakt_pallplatser` | Float | Egna mått; om ifyllt och flakmeter tomt sätts flakmeter = pallplatser × 0,4 vid validering |
| `forpackningstyp` | Link Förpackningstyp | Förpackning |
| `antal_per_forpackning` | Float (> 0) | Förpackning, i lagerenhet |

Vikt tas från `weight_per_unit` och `weight_uom` (omräknas till kg via UOM Conversion Factor).

**Customer**: `forvald_fraktprodukt` (Link Fraktprodukt). Fraktprodukter finns först efter att priser hämtats
minst en gång; knappen **"Hämta transportörsprodukter"** i Fraktinställningar gör en prisförfrågan på en
exempelsändning (inställningarnas avsändare till sig själv, en EUR-pall) för att fylla registret från början.

**Quotation, Sales Order**: `fraktprodukt` (Link Fraktprodukt, skrivskyddad) – satt av "Kontrollera fraktpris".

**Shipment**:

| Fält | Typ | Beskrivning |
|---|---|---|
| `avsandarens_referens` | Data | → `sender_reference`; förifylls med följesedelsnummer (kommaseparerade) |
| `mottagarens_referens` | Data | → `receiver_reference`; förifylls med följesedelns `po_no` |
| `fraktprodukt` | Link Fraktprodukt | Vald eller bokad produkt |
| `fraktpris` | Currency | Sendifys pris för vald produkt |
| `fraktpris_valuta` | Link Currency | |
| `kundpris` | Currency | Förslag enligt påslag, ändringsbart |
| `pris_hamtat` | Datetime | När priset hämtades |
| `sendify_id` | Data, skrivskyddad | Sendifys sändnings-id (också i `shipment_id`) |
| `etikett_hamtad` | Check, skrivskyddad | |
| `senaste_sparning` | Data, skrivskyddad | Senaste händelsens beskrivning |
| `sparningshandelser` | Table Spårningshändelse | |

Ur ERPNext:s egna fält används: `service_provider` = "Sendify", `carrier` = transportör, `carrier_service` =
produkt, `shipment_id` = Sendifys id, `awb_number` = spårningsnummer (`main_tracking_id`), `tracking_url`,
`tracking_status`, `shipment_amount` = Sendifys pris, `status`.

**Shipment Parcel**: `kollityp` (Select Paket/Pall/Övrigt), `stapelbar` (Check), `flakmeter` (Float, per
enhet), `beskrivning` (Data).

**Delivery Note**: inga nya fält; bokningen fyller `transporter_name` och `lr_no`.

## Kolliförslag – `frakt/kollin.py`

`foresla_kollin(rader) -> (kollin, varningar)`, där `rader` är `[(item_code, stock_qty)]` och `kollin` är en
lista av dict med `kollityp, langd_cm, bredd_cm, hojd_cm, vikt_kg, antal, stapelbar, flakmeter, beskrivning`.
Ren beräkning; läser bara artikel- och förpackningsdata.

- **Egna mått:** en kollirad per artikelrad, `antal` = antalet, vikt per enhet, artikelns mått, kollityp,
  stapelbarhet och flakmeter.
- **Förpackning:** per förpackningstyp summeras fyllnadsgraden `antal / antal_per_forpackning` över alla
  artikelrader; antal förpackningar = summan avrundad uppåt. Vikt per förpackning = egenvikt + (summan av
  artiklarnas vikt / antal förpackningar). Mått, kollityp, stapelbarhet och flakmeter från förpackningstypen.
  Beskrivning = artiklarnas namn, kommaseparerade (kapas till 100 tecken).
  Exempel: A 100 st à 40/pall (2,5) + B 10 st à 20/pall (0,5) → 3 EUR-pallar.
- **Inget fraktsätt:** vikten läggs på de förpackningar som finns (jämnt fördelad); finns inga, skapas en rad
  "Övrigt" med totalvikten och tomma mått.
- **Varningar:** artiklar utan fraktsätt, utan vikt, eller med fraktsätt men saknade mått.

Förslaget räknas bara när Shipment skapas och när användaren klickar **"Föreslå kollin igen"** (ersätter
kollitabellen efter bekräftelse).

## Leverantörsgränssnitt – `frakt/sendify.py`

Den enda modulen som känner till Sendify. Tar och returnerar dict:ar i vårt format:

| Funktion | Sendify | Returnerar |
|---|---|---|
| `skapa_sandning(sandning) -> id` | `POST /shipments` med `enable_bookable_validation: true` | Sendifys id |
| `uppdatera_sandning(id, sandning)` | `PUT /shipments/{id}` | – |
| `radera_sandning(id)` | `DELETE /shipments/{id}` | – |
| `hamta_priser(id, upphamtning) -> (priser, varningar)` | `POST /shipments/rates` | `priser`: `token, transportorskod, transportor, produkt, pris, valuta, dagar_min, dagar_max, upphamtning, leverans, giltig_till` |
| `boka(token) -> sparningsnummer` | `POST /shipments/book` | `main_tracking_id` |
| `hamta_dokument(id, typ) -> pdf_bytes` | `POST /shipments/print` (`output_format: url`), sedan nedladdning | PDF |
| `avboka(id)` | avbokningsendpointen | – |
| `hamta_sparning(id) -> handelser` | `GET /shipments/{id}/tracking` | `tidpunkt, status, beskrivning, plats, url` |
| `kontrollera_nyckel() -> team` | `GET /status` | teamnamn |

`sandning` i vårt format: `avsandare` och `mottagare` (namn, adressrad 1–2, postnummer, ort, landskod, kontakt:
namn, telefon, e-post, `privatperson`), `kollin` (enligt ovan), `referens_id`, `avsandarens_referens`,
`mottagarens_referens`.

Fel kastas som `FraktFel(meddelande, falt_fel, request_id)`. Sendifys valideringsfel (`errors`-objektet)
översätts till svenska fältnamn via en tabell (t.ex. `packages[0].weight_kg` → "Kolli 1: vikt").
Timeout 30 s. Nätverksfel och 5xx blir "Sendify svarar inte, försök igen". `X-Sendify-Request-ID` sparas i
felloggen; API-nyckeln loggas aldrig.

En senare leverantör läggs som en egen modul med samma funktioner; `bokning.py` väljer modul efter
`Fraktinställningar.leverantor`.

## Flöden

### 1. Följesedel → Shipment (`bokning.skapa_shipment(delivery_note)`)

Knapp **"Boka transport"** på godkänd följesedel (när Fraktinställningar är aktiverad).

1. Shipment skapas med ERPNext:s `make_shipment` (mottagare, adress, kontakt, värde, följesedelslänk).
2. Avsändare sätts från Fraktinställningar; `pickup_date` = nästa arbetsdag; `pickup_type` = Pickup.
3. Kollitabellen fylls med `foresla_kollin` från följesedelns rader; varningar visas.
4. Referenser förifylls. `fraktprodukt` förväljs: först försäljningsorderns `fraktprodukt`, annars kundens
   `forvald_fraktprodukt`.
5. Shipment sparas som utkast och öppnas.

### 2. Priser på Shipment (`bokning.hamta_priser(shipment)`)

Knapp **"Hämta priser"** på utkast.

1. Sändningen skapas hos Sendify (eller uppdateras om `sendify_id` finns).
2. Priser hämtas med `requested_pickup_time` = `pickup_date` + `pickup_from`.
3. Nya transportörsprodukter sparas som Fraktprodukt.
4. Dialogen visar en tabell sorterad på pris: transportör, produkt, pris, kundpris (med påslag), ledtid,
   upphämtning, beräknad leverans. Förvald produkt markeras. Varningar från Sendify listas under tabellen.
5. Knappar: **Boka** (vald rad), **Spara val**, **Stäng**.
   - *Spara val* sätter `fraktprodukt`, `fraktpris`, `kundpris`, `pris_hamtat` utan att boka.

Om användaren klickar Boka efter att priset gått ut (`giltig_till`) hämtas priserna om och dialogen uppdateras.

### 3. Boka

- **Boka** (från dialogen): bokar med radens token.
- **"Boka vald produkt"** (Shipment med sparad `fraktprodukt`): hämtar nya priser och bokar samma
  transportörskod + produkt. Om priset avviker mer än `prisandring_grans_procent` från sparat pris visas båda
  och användaren bekräftar. Finns produkten inte öppnas prisdialogen med ett meddelande.
- **"Boka med förval"** (när `fraktprodukt` kommer från kund eller order men inget pris sparats): samma som
  ovan, utan prisjämförelse.

Efter lyckad bokning (allt i en transaktion efter Sendifys bekräftelse):

1. Shipment: `fraktprodukt`, `carrier`, `carrier_service`, `fraktpris`, `shipment_amount`, `kundpris`
   (behålls om användaren ändrat det), `shipment_id`/`sendify_id`, `awb_number`, `tracking_url`,
   `service_provider`; godkänns (`status` = Booked).
2. Följesedlarna i `shipment_delivery_note`: `transporter_name` = transportör, `lr_no` = spårningsnummer,
   `lr_date` = upphämtningsdatum (via `db_set`, dokumenten är godkända).
3. Etikett och fraktsedel hämtas och bifogas Shipment som privata filer
   (`Fraktsedel-{shipment}.pdf`, `Etikett-{shipment}.pdf`). Misslyckas det är bokningen ändå sparad, ett
   meddelande visas och knappen **"Hämta fraktsedel"** finns kvar.

### 4. Avbokning

`doc_events` Shipment `before_cancel`: om `sendify_id` finns och status är Booked anropas `avboka`. Vägrar
Sendify stoppas avbrytandet med Sendifys felmeddelande. Följesedlarnas `transporter_name`/`lr_no` töms.

Ett utkast med `sendify_id` som raderas raderar också sändningen hos Sendify (`on_trash`, fel ignoreras och
loggas).

### 5. Prisförfrågan på offert och order (`fraktpris.kontrollera(doctype, name)`)

Knapp **"Kontrollera fraktpris"** på Quotation och Sales Order (utkast och godkänd).

1. Kollin föreslås från dokumentets rader (`stock_qty`).
2. Mottagare = `shipping_address_name` (annars `customer_address`) och kundens kontakt; avsändare från
   inställningarna; upphämtning = `delivery_date` (order) eller nästa arbetsdag.
3. Tillfällig sändning skapas hos Sendify, priser hämtas, sändningen raderas.
4. Samma prisdialog utan kollitabell, med knapparna **Lägg till frakt** och **Stäng**.
5. *Lägg till frakt* lägger en skatterad (Actual, `fraktkonto`, "Frakt {transportör} {produkt}", kundpriset)
   och sätter `fraktprodukt`. Finns redan en rad på `fraktkonto` ersätts beloppet. *Lägg till frakt* finns bara
   på utkast. På godkänd offert/order visar dialogen priserna och knappen **Spara val**, som bara sätter
   `fraktprodukt` (via `db_set`); fraktraden läggs då på fakturan enligt flöde 6.

### 6. Frakt på fakturan

`doc_events` Sales Invoice `before_insert` (när fakturan skapas från följesedel):

- För varje följesedel i fakturan med en bokad Shipment: lägg till en skatterad (Actual, `fraktkonto`,
  "Frakt {transportör} {produkt}", Shipmentens `kundpris`), om fakturan inte redan har en rad på `fraktkonto`.
- Momsen räknas av fakturans momsmall som vanligt.

### 7. Spårning (`frakt/sparning.py`)

- Schemalagt jobb (`scheduler_events` "hourly"; hoppar över körningar enligt `sparning_intervall`) för
  Shipments med status Booked och `tracking_status` ≠ Delivered/Returned/Lost.
- Nya händelser läggs till i `sparningshandelser`, `senaste_sparning` och `tracking_url` uppdateras.
- `tracking_status` från Sendifys senaste `status` (`UNKNOWN, ORDERED, CONFIRMED, PICKUP, IN_TRANSIT,
  DELIVERY, DELIVERED, EXCEPTION, OUT_FOR_DELIVERY, ARRIVED, DEPARTED, NOT_FOUND`): `DELIVERED` → *Delivered*
  och `status` → *Completed*; alla andra → *In Progress*. Sendify har ingen status för retur eller förlorat
  gods; *Returned* och *Lost* sätts manuellt. `EXCEPTION` visas som indikator (röd) på Shipment.
- Knapp **"Uppdatera spårning"** på Shipment.
- Följesedeln visar Shipmentens spårningslänk via ett fält i sidopanelen (`frm.dashboard`/indikator i JS).

## Felhantering

- `FraktFel` visas med `frappe.throw`; fältfel listas som punktlista med svenska fältnamn.
- Inga ERPNext-ändringar sparas förrän Sendify bekräftat bokningen.
- Inställningar ofullständiga (ingen nyckel, ingen avsändaradress) → tydligt fel med länk till Fraktinställningar.
- Knappen **"Testa anslutning"** i Fraktinställningar anropar `kontrollera_nyckel` och visar teamnamnet.

## Kodstruktur

```
erpnext_sverige/frakt/
  __init__.py
  doctype/forpackningstyp/
  doctype/fraktinstallningar/
  doctype/fraktprodukt/
  doctype/sparningshandelse/
  sendify.py      Sendify-API (enda modulen som känner till Sendify)
  kollin.py       kolliförslag
  bokning.py      whitelistade metoder för Shipment och följesedel
  fraktpris.py    påslag, prisförfrågan på offert/order, fraktrad på faktura
  sparning.py     spårningsjobb
erpnext_sverige/public/js/frakt_shipment.js     Shipment: knappar, prisdialog
erpnext_sverige/public/js/frakt_forsaljning.js  Quotation/Sales Order/Delivery Note: knappar
```

`hooks.py`: `doctype_js` (Shipment, Quotation, Sales Order, Delivery Note), `doc_events` (Shipment
`before_cancel`/`on_trash`, Sales Invoice `before_insert`), `scheduler_events` (`hourly`). Custom fields i
`setup/custom_fields.py`. Strängar på engelska i koden, översatta i `locale/sv.po`.

## Test

Körs på test-erp.local: `bench --site test-erp.local run-tests --app erpnext_sverige`.

- `tests/test_frakt_kollin.py` – egna mått; ihopfyllda förpackningar (2,5 + 0,5 = 3); viktfördelning;
  inget fraktsätt med och utan förpackningar; enhetsomräkning (g → kg, alternativ enhet → lagerenhet);
  pallplatser → flakmeter; varningar.
- `tests/test_frakt_sendify.py` – översättning till/från Sendifys format; valideringsfel → svenska fältnamn;
  5xx och nätverksfel; nyckeln finns inte i loggade fel. HTTP mockas med `unittest.mock` (som
  `test_tax_category.py`).
- `tests/test_frakt_bokning.py` – med mockat `sendify`: följesedel → Shipment med kollin och referenser;
  förval från order före kund; priser och Fraktprodukt skapas; spara val; boka (Shipment, följesedel, bilagor);
  boka vald produkt med prisändring; etikettfel efter bokning; avbokning och vägrad avbokning; fraktrad på
  faktura och ingen dubbel frakt; prisförfrågan på order lägger fraktrad; spårningsjobbet sätter status.
- `tests/test_frakt_sandlada.py` – röktest mot Sendifys sandlåda som bara körs om `sendify_sandbox_api_key`
  finns i site_config: skapa sändning, hämta priser, boka med DHL/UPS/DSV, hämta etikett, avboka.
