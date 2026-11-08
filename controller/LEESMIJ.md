# Controller verwarmde mat

Een ESP32 regelt de 5 matsegmenten elk apart, plus de PTC-verwarmer van 12 V / 100 W en de ventilator.
Alles draait op een 12 V-accu; er is geen netstroom.
Monitoren en instellen via de webinterface of via Home Assistant.

## Bestanden

| Bestand | Inhoud |
|---|---|
| `maak_schema.py` | Genereert `kattenmat.kicad_sch` (KiCad 9). Pas het script aan, niet het schema, zolang het nog gegenereerd wordt |
| `kattenmat.kicad_sch`, `.kicad_pro` | Schema; verbindingen via netlabels. ERC: 0 fouten, 0 waarschuwingen |
| `kattenmat_schema.pdf` | Afdruk van het schema |
| `esphome/kattenmat.yaml` | ESPHome-configuratie (gevalideerd met ESPHome 2026.10.2) |
| `esphome/segment.yaml` | Pakket per segment: NTC, MOSFET, PID, stroomcontrole |
| `esphome/secrets.yaml.example` | Kopieer naar `secrets.yaml` (staat in .gitignore) |

```bash
python3 maak_schema.py && kicad-cli sch erc kattenmat.kicad_sch
cd esphome && esphome run kattenmat.yaml     # eerste keer via USB-serieel op J6, daarna OTA
```

## Toewijzing

| GPIO | Functie | GPIO | Functie |
|---|---|---|---|
| 36 (VP) | NTC 1 | 25 | Segment 1 |
| 39 (VN) | NTC 2 | 26 | Segment 2 |
| 34 | NTC 3 | 27 | Segment 3 |
| 35 | NTC 4 | 13 | Segment 4 |
| 32 | NTC 5 | 4 | Segment 5 |
| 33 | 12 V-bewaking (100k/18k) | 17 | Hoofdschakelaar mat (P-FET) |
| 21 / 22 | I2C: INA226 (0x40) en SHT40 | 23 | Ruimteverwarmer (UCC27511 + IRLB8721, of DC-SSR op J3) |
| 16 | 1-wire DS18B20 buiten | 18 | Ventilator |
| 19 | Status-LED | 0 / EN | BOOT- en EN-knop, programmeerheader J6 |

Alleen ADC1 (ADC2 werkt niet met wifi). GPIO 0, 2, 5, 12, 14 en 15 zijn bewust vrij gelaten (strapping, pulsen bij het opstarten).
Alle MOSFET-gates hebben een pulldown, zodat alles uit staat tijdens reset en flashen.

Matconnector J4 (12-polig): 1 MAT+ (via de bimetaalschakelaar in de mat), 2-6 segment 1-5 min, 7-11 NTC 1-5, 12 NTC-massa.

## Beveiliging (software, naast de bimetaalschakelaar van 45 °C)

- Per segment uit en vergrendeld bij: NTC open of kortgesloten, boven 42 °C, meer dan 6 °C afwijking van de mediaan
  gedurende 2 minuten, geen stroomstap bij inschakelen (3 keer), te grote stroomstap.
- Hele mat uit (P-FET) bij: een segment boven 45 °C, of stroom die blijft lopen na uitschakelen (MOSFET doorgeslagen).
- Fouten blijven bewaard na een herstart; wissen met de knop "Fouten wissen" nadat je de oorzaak hebt gevonden.
- De stroomcontrole werkt bij elk schakelmoment van de langzame PWM (perioden 17-31 s, verschillend per segment,
  zodat ze zelden tegelijk schakelen; bij gelijktijdig schakelen wordt die meting overgeslagen).
- Mat alleen actief als de kamer kouder is dan "Mat alleen onder kamertemp." (standaard 15 °C, hysterese 0,5 °C).
  Zonder kamersensor blijft de mat beschikbaar (de eigen beveiligingen blijven werken). Bij het hervatten wordt de
  integraal van de PID's gewist, zodat er geen doorschot is.
- Ruimteverwarmer (PTC): aan onder de streefwaarde (standaard 8 °C, aan onder 7,5 en uit boven 9 °C), minimaal 2 min
  tussen schakelen, maximaal 60 min aan en dan 10 min pauze; uit als de kamersensor ontbreekt. De buitentemperatuur
  wordt alleen gemeten en getoond.
- Accu: de INA226 meet de accuspanning (30 s gemiddeld, zodat de inschakelpiek van de PTC niet meetelt). Onder
  12,2 V gaat de verwarmer uit, onder 12,0 V ook de mat; weer aan bij 0,4 V hoger. Standaardwaarden voor de huidige
  loodaccu. Na de overstap op LiFePO4 in de webinterface naar ongeveer 12,9 en 12,5 V zetten.
- Wifi weg: de ESP regelt gewoon door.

## Aannames en open punten

- L1 (4,7 uH) en de condensatoren rond de AP63203 volgens de typische schakeling: controleer met de datasheet.
- Q7 (IRLB8721) dissipeert ca. 0,5 W bij 8,3 A: klein koelprofiel. Koude PTC trekt bij inschakelen meer; F2 15 A traag.
- Ompoling van de accu: D1 (TVS) geleidt en F1 brandt door. Er is geen echte ompolingsbeveiliging.
- Eigen verbruik ESP32 met wifi ongeveer 0,5 W, ca. 12 Wh per dag.
- De NTC-meting gebruikt 3,3 V als referentie; een afwijking van de voeding geeft een kleine temperatuurfout.
- PID-startwaarden zijn een gok: gebruik de autotune-knop per segment met de mat in de echte opbouw.
- Nog geen printontwerp (PCB); het schema is de basis daarvoor.
