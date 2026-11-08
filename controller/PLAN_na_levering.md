# Plan na levering van de controllerprint

Besteld op 8-11-2026 bij JLCPCB: 4-laags print, SMD-onderdelen op de top geplaatst door JLCPCB.
U1 (ESP32) en alle THT-onderdelen soldeer je zelf. Ontwerpbestanden staan in `EASyEDA/`; de ESPHome-configuratie
staat in `controller/esphome/`.

Dit plan is bedoeld om stap voor stap samen met Claude uit te voeren. Per stap staat wie wat doet:
**[jij]** voor handwerk en metingen, **[Claude]** voor wat Claude in deze repository of op deze computer kan doen.
Vink af wat klaar is en noteer meetwaarden in de tabellen, zodat een volgende sessie weet waar we zijn.

## 0. Voorbereiding (kan al vóór de levering)

- [ ] **[Claude]** ESPHome installeren in een venv en `kattenmat.yaml` compileren met de actuele ESPHome-versie
      (`pip install esphome`, `esphome compile kattenmat.yaml`). Waarschuwingen of verouderde opties oplossen.
- [ ] **[jij]** Gegevens voor `esphome/secrets.yaml` aanleveren: wifi-naam en -wachtwoord van het netwerk bij
      het chalet. **[Claude]** maakt `secrets.yaml` aan (api-sleutel en wachtwoorden genereren). Blijft buiten git.
- [ ] **[Claude]** `LEESMIJ.md` bijwerken naar de print zoals besteld:
      - matconnector J4 bestaat niet meer: per segment een 4-polige connector U5–U9, bimetaal op P1;
      - "Nog geen printontwerp" vervangen door een verwijzing naar `EASyEDA/`;
      - LCSC-nummers, zekeringwaarden en de geverifieerde punten (L1, AP63203-condensatoren) bijwerken.
- [ ] **[jij]** Klaarleggen:
      - USB-serieel adapter op **3,3 V-niveau** (CP2102, CH340 of FTDI) plus losse draadjes;
      - regelbare labvoeding met stroombegrenzing (of een 12 V-adapter plus een zekering van 1 A);
      - multimeter;
      - een 12 V-lampje of een weerstand van ongeveer 100 Ω / 2 W als testbelasting;
      - een losse NTC van 10 kΩ of een vaste weerstand van 10 kΩ.
- [ ] **[jij]** De losse onderdelen besteld en binnen: schroefklemmen, pinheaders, zekeringhouders,
      U5–U9 (C49291885), Q7, ATO-zekeringen van 20 A en 15 A, plus voor de eerste test een kleine zekering van 2–5 A.

## 1. Ontvangst en controle

- [ ] **[jij]** Print bekijken (loep of telefooncamera): bruggen tussen pinnen van U2, U3 en U4, scheve of
      ontbrekende onderdelen, draairichting van D1, D3, D4 (streep = kathode), C1 (+) en de LED.
- [ ] **[jij]** Foto's van de bovenkant (scherp, recht van boven) naar Claude sturen. **[Claude]** vergelijkt die
      met de bestukking en de Gerbers.
- [ ] **[jij]** Weerstand meten **zonder spanning**. Verwacht geen kortsluiting (ruwe waarden, de multimeter laadt
      condensatoren op, dus de waarde loopt op):

| Meetpunt | Verwacht | Gemeten |
|---|---|---|
| J1: 12VIN ↔ GND | > 1 kΩ, oplopend | |
| +12V (F1-kant) ↔ GND | > 1 kΩ, oplopend | |
| 3V3 (J6 pin 4) ↔ GND | > 100 Ω, oplopend | |
| HEAT+ ↔ HEAT− (J2) | open | |

## 2. Solderen

Volgorde: van laag naar hoog, de ESP32 eerst.

1. [ ] **U1 ESP32-WROOM-32UE.**
   - Uitlijnen en twee hoekpinnen vastzetten.
   - Positie controleren, dan de andere randpads solderen. Gebruik veel flux.
   - Het GND-vlak onder de module is elektrisch niet nodig (pin 1, 15 en 38 zijn ook GND). Als er via's in
     zitten, soldeer je het vanaf de onderkant door de via's.
   - Daarna meten: 3V3 ↔ GND geen kortsluiting, en tussen naast elkaar liggende pinnen geen bruggen.
2. [ ] **Pinheaders** J6, J7 en J8.
3. [ ] **Schroefklemmen** J1, J2, J3, J5 en P1. Draadingang naar de printrand.
4. [ ] **U5–U9** (segmentconnectoren).
5. [ ] **Zekeringhouders** F1 en F2. Ruim tin: hier loopt 8–10 A.
6. [ ] **Q7** IRLB8721. Pinvolgorde G-D-S met de vierkante pad = gate, eventueel met een clip-koelplaatje.
7. [ ] Flux verwijderen met isopropylalcohol.

## 3. Eerste spanning (zonder ESP-programma, zonder belasting)

- [ ] **[jij]** F1 plaatsen met de **kleine zekering** (2–5 A); F2 nog leeg laten.
- [ ] **[jij]** Labvoeding 12 V, stroombegrenzing 150 mA, op J1 (let op de polariteit: 12VIN / GND).

| Meting | Verwacht | Gemeten |
|---|---|---|
| Ruststroom bij 12 V | ca. 20–80 mA (ESP start op, probeert te verbinden; aanname) | |
| 3V3 op J6 pin 4 | 3,25–3,35 V | |
| +12V na F1 | ≈ 12 V | |
| Gate Q1–Q6, Q9 en de UCC27511-ingang | 0 V (pulldowns) | |

- [ ] Wordt iets warm of loopt de stroom tegen de begrenzing aan: meteen uit en foto's naar Claude.

## 4. ESPHome flashen (eerste keer via J6)

Aansluiten van de USB-serieel adapter op J6 (opschrift BO-EN-3V-RX-TX-GD):

| Adapter | J6 |
|---|---|
| GND | GD |
| RX | TX (de TX van de ESP) |
| TX | RX (de RX van de ESP) |
| 3V3 | **niet aansluiten**; de print krijgt 12 V via J1 |

- [ ] **[jij]** Print aan 12 V. Op de print: BOOT ingedrukt houden, EN kort indrukken, BOOT loslaten
      (download-modus). Een adapter zonder DTR/RTS-aansluiting heeft dit altijd nodig.
- [ ] **[Claude]** `esphome run kattenmat.yaml --device /dev/ttyUSB0` (poort controleren met `ls /dev/ttyUSB* /dev/ttyACM*`).
      Daarna EN indrukken om op te starten en de log lezen.
- [ ] **[Claude]** Controleren in de log:
      - wifi verbonden;
      - I2C-scan vindt de INA226 op 0x40 (en de SHT40 op 0x44 zodra die aangesloten is);
      - geen bootloop.
- [ ] Vanaf nu gaan updates via wifi (OTA): `esphome run kattenmat.yaml --device kattenmat.local`.
      Webinterface: http://kattenmat.local.

## 5. Functietest per blok (nog zonder mat en verwarmer)

**[Claude]** leest de log en de webinterface mee en past zo nodig de configuratie aan.
**[jij]** sluit de testbelastingen aan en meet. Tijdens het testen kan Claude een tijdelijke testversie maken met
handmatige schakelaars per uitgang; die gaat er daarna weer uit.

| Blok | Test | Verwacht | OK |
|---|---|---|---|
| Accuspanning | INA226 en ADC (GPIO33) vergelijken met de multimeter op J1 | verschil < 0,1 V (INA) en < 0,3 V (ADC) | |
| SHT40 (J7: 3V-DA-CL-GD) | aansluiten, waarde bekijken | plausibele temperatuur en RV | |
| DS18B20 (J8: 3V-OW-GD) | aansluiten | buitentemperatuur zichtbaar | |
| NTC-ingangen 1–5 | 10 kΩ op U5–U9 pin 3 ↔ pin 4 | ≈ 25 °C | |
| NTC open | niets aangesloten | segment "NTC defect" na ongeveer 10 s, uitgang blijft uit | |
| Hoofdschakelaar mat (Q8) | MAT_EN aan | 12 V op U5–U9 pin 1 (via P1: bimetaal of brug) | |
| Segmentuitgang 1–5 | lampje tussen U5–U9 pin 1 en pin 2, uitgang aan | lampje aan, INA226 ziet de stroom | |
| Ventilator (J5) | ventilator of lampje, FAN_EN aan | draait, en uit bij reset | |
| Verwarmeruitgang (J2, Q7) | **eerst** lampje op J2, F2 met een kleine zekering | lampje aan; Q7 blijft koel | |
| SSR (J3) | multimeter op J3 | 3,3 V-niveau bij aan (aanname: controleren in het schema) | |
| Reset/flash | EN indrukken tijdens bedrijf | alle uitgangen uit tijdens het opstarten | |

## 6. Mat aansluiten

Per segment: MAT+ op pin 1 via de bimetaalschakelaar op P1, segment-min op pin 2, NTC op pin 3 en 4.

- [ ] **[jij]** Eerst **één segment** aansluiten op U5, met de andere connectoren leeg.
- [ ] **[Claude]** Stroomstap bij inschakelen aflezen.
      - Nominaal 0,28 A per segment.
      - Controleren of `i_min` (0,15) en `i_max` (0,45) in `kattenmat.yaml` passen bij de gemeten waarde.
      - Zo nodig aanpassen.
- [ ] **[jij]** De NTC-temperatuur vergelijken met een losse thermometer op het segment. **[Claude]** stelt zo nodig
      een offset of de B-constante in.
- [ ] Daarna alle 5 segmenten. Controleren dat elke NTC bij het juiste segment hoort: één segment opwarmen met de
      hand en kijken welke temperatuur stijgt.
- [ ] **Beveiliging testen:**
      - NTC losmaken → segment uit en vergrendeld;
      - "Fouten wissen" werkt;
      - bimetaal open (P1 los) → geen stroom en een melding.

## 7. Verwarmer en regeling

- [ ] **[jij]** PTC-verwarmer op J2, met **F2 = 15 A**. Eerste inschakeling met een stroomtang of de INA226-gegevens
      erbij. **[Claude]** bekijkt de inschakelpiek en de temperatuur van Q7 (voelen na 10 minuten; heet = koelplaat nodig).
- [ ] **[jij]** F1 vervangen door 20 A. Zekering bij de accu zelf (inline) plaatsen.
- [ ] **[Claude]** PID-autotune per segment met de mat in de echte opbouw (kussen of deken erop), parameters
      overnemen in `segment.yaml`.
- [ ] **[jij]** Streefwaarden in de webinterface instellen. Standaard:
      - mat 34 °C;
      - mat alleen onder kamertemperatuur 15 °C;
      - verwarmer onder 8 °C;
      - ventilator boven 75 % RV.
- [ ] **[jij + Claude]** Accugrenzen controleren bij de echte loodaccu: verwarmer uit onder 12,2 V, mat uit onder
      12,0 V. Bij gebruik nagaan of de verwarmer niet onnodig vroeg afvalt door spanningsval.

## 8. Plaatsen in het chalet

- [ ] Behuizing, met trekontlasting op alle kabels. Print niet op de bodem (condens), kabels van onderen in.
- [ ] Antenne (u.FL) naar een plek met wifi-bereik; wifisignaal controleren in de webinterface (beter dan −75 dBm).
- [ ] 24-uurstest: logboek van temperaturen, stroom en accuspanning bekijken. **[Claude]** beoordeelt de regeling
      en de beveiligingen.
- [ ] Optioneel: koppelen met Home Assistant (de API met versleuteling staat al aan).

## 9. Afronden

- [ ] **[Claude]** Meetwaarden en wijzigingen verwerken in `LEESMIJ.md` en de ESPHome-bestanden. Commit na akkoord.
- [ ] **[Claude]** Afwijkingen tussen print en schema noteren voor een eventuele v2 van de print, bijvoorbeeld:
      ompolingsbeveiliging, een groter montagegat rechtsonder, het netnaamverschil MAT+Protected / NET_1.

## Vastgestelde gegevens (8-11-2026)

GPIO-toewijzing op de print, uit de EasyEDA-netlijst. Deze komt overeen met `kattenmat.yaml`:

| GPIO | Net | GPIO | Net |
|---|---|---|---|
| 36 | ADC1 (NTC 1) | 25 | SEG1_EN |
| 39 | ADC2 (NTC 2) | 26 | SEG2_EN |
| 34 | ADC3 (NTC 3) | 27 | SEG3_EN |
| 35 | ADC4 (NTC 4) | 13 | SEG4_EN |
| 32 | ADC5 (NTC 5) | 4 | SEG5_EN |
| 33 | VMON (12 V) | 17 | MAT_EN |
| 21 / 22 | SDA / SCL | 23 | HEAT_EN |
| 16 | OW (DS18B20) | 18 | FAN_EN |
| 19 | LED | 0 / EN | BOOT / EN (J6 en knoppen) |

Connectoren:

| Ref | Pinnen |
|---|---|
| J1 | 12VIN, GND |
| J2 | HEAT+, HEAT− (verwarmer) |
| J3 | SSR, GND |
| J5 | +12V, FAN− |
| J6 | GND, TXD, RXD, 3V3, EN, BOOT (pin 1 = GND, vierkant pad) |
| J7 | 3V3, SDA, SCL, GND |
| J8 | 3V3, OW, GND |
| P1 | bimetaal (MAT+ ↔ MAT+Protected) |
| U5–U9 | 1 MAT+Protected, 2 SEGn, 3 NTCn, 4 GND (segment 1–5 van links naar rechts) |

Zekeringen: F1 20 A (hoofdvoeding) en F2 15 A (verwarmer); voor de eerste test kleiner.
Controleer eerst of de XF-507P standaardmaat ATO is.
