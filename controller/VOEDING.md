# Voeding van de chalet

Uitwerking van het gesprek van 9-11-2026. Elke uitspraak is gelabeld:
**keuze** (besloten), **voorkeur** (advies, nog niet besloten) of **aanname** (nog te controleren).

## Samenvatting

- **Keuze, fase 1 (nu):** alles wordt gevoed vanuit de schuur. Een netvoeding van 24 V staat in de schuur en een laagspanningskabel loopt naar de chalet. In de chalet zet een gewone Victron Orion-Tr 24/12-20 de 24 V om naar een vaste 12,2 V voor de controller. Er komt geen 230 V bij de chalet en geen accu.
- **Keuze, fase 2 (later):** het accusysteem komt op 24 V **in de schuur**: accu, zonnepaneel met MPPT-lader en noodstroom vanuit het net. De chalet krijgt altijd 24 V over dezelfde kabel, uit de accu, de zon of het net. In de chalet verandert dan niets, behalve de meting van de 24 V.
- **Keuze, gevolg:** de Orion hoeft nooit instelbaar te zijn en hoeft niet uitgelezen te worden. De Smart-versie, die ongeveer 100 euro duurder is, is daarom niet nodig.

## 1. Energiebehoefte van de bovenkamer bij 8 °C

Berekend met het warmteverliesmodel in `bouwplan/berekening.py` (`heat()`), met T_IN = 8 °C.

| Onderdeel | W/K |
|---|---|
| Raam 100 x 50 (Uw 1,3 volgens de specificatie) | 0,65 |
| Zijwanden | 0,38 |
| Trapgat (aanname: 3 W/m²K, koude lucht blijft beneden) | 0,25 |
| Achterwand | 0,25 |
| Plafond | 0,19 |
| Vloer | 0,19 |
| **Totaal H** | **1,90** |

**Raam.** De specificatie geeft U 1,3 en Ug 1,1 (4/16/4). Een Uw geldt voor het referentieraam van 1,23 x 1,48 m. Voor een raam van 100 x 50 is het aandeel kozijn en glasrand groter.
- **Aanname:** de Uw is ongeveer 1,6–1,7, bij een kozijn plus vleugel van 70–100 mm, Uf 1,3–1,6 en een aluminium afstandhouder met Ψ ≈ 0,08. Dan wordt H ongeveer **2,1 W/K**. Meet de kozijnbreedte en het type afstandhouder bij levering na.

**Benodigd vermogen**, met Uw ≈ 1,7. Inclusief de minimale ventilatie voor ≤75 % RV, bij 5–10 g/h vocht van de kat (aanname).

| Buiten | Vermogen | Per nacht (16 u) |
|---|---|---|
| −3 °C (gewone vorstnacht) | 31–38 W | 500–610 Wh |
| −5 °C | 35–42 W | 560–670 Wh |
| −8 °C (zware vorst) | 41–48 W | 650–770 Wh |
| −10 °C | 45–53 W | 720–850 Wh |

- **Aanname:** reken met ongeveer 30 % marge voor kieren, wind, koudebruggen en een trapgat dat meer lekt dan aangenomen. De PTC-kachel van 100 W is ruim genoeg.
- **Aanname, gratis warmte:** een slapende kat geeft 10–15 W af. Vrijwel alle warmte van de mat (17 W) komt ook in de kamer terecht.
- **Verbruik per dag:** de mat draait zolang de kamer onder 15 °C is, dus vrijwel de hele winter. Dat is ongeveer 408 Wh per dag, plus 12 Wh voor de ESP32.
  - Op een gewone decemberdag (4,5 °C) is het verbruik 430–450 Wh per dag, met weinig kachel.
  - Bij aanhoudende vorst is het 0,8–1,2 kWh per dag.
- **Voorkeur, besparing:** laat de mat alleen aan als de kat erop ligt. Aanwezigheid zou je kunnen afleiden uit het warmteverloop van de NTC's. Dit is nog niet uitgewerkt.
- **Voorkeur, ventilatierooster:** houd het rooster in de winter grotendeels dicht. De Ø100 trekt bij −5 °C op natuurlijke trek ongeveer 11 m³/h. Volledig open kost dat ongeveer 50 W extra, terwijl 2–3 m³/h genoeg is.
- **Aanname, condens:** bij 8 °C en 75 % RV ligt het dauwpunt rond 3,7 °C. Het midden van het glas blijft bij −5 °C buiten ongeveer 6 °C. De onderrand van het glas wordt met een aluminium afstandhouder ongeveer 2–3 °C, dus daar kun je bij vorst condens verwachten.

## 2. Fase 1: voeding vanuit de schuur (keuze)

```
schuur                   kabel 2 x 2,5 mm², ~7-10 m          chalet (bovenkamer, bij de controller)
230 V ─ netvoeding 24 V ═══════════════════════════ Orion-Tr 24/12-20 ─ 12,2 V ─ controller (J1)
        (binnen, droog)        waterdichte stekker      (geïsoleerd)
```

### Onderdelen

| Onderdeel | Keuze | Waarom | Gegevens (bron: distributeurs, geen eigen meting) |
|---|---|---|---|
| Netvoeding | **24 V, 250 W, IP67, met stekker**, bijvoorbeeld LightingWill 24V 250W (fabrikant HUAKE, Amazon) (voorkeur, 9-11-2026) | Wordt met stekker geleverd: er hoeft niets aan 230 V aangesloten te worden. IP67, geschikt voor een onverwarmde schuur. Beveiligingen opgegeven. 250 W is genoeg samen met de zachte start van de kachel. | Ingang 90–265 V AC, uitgang 24 V, 10,41 A, 250 W. Beveiliging tegen kortsluiting, overbelasting, overspanning, overstroom en te hoge temperatuur, in hiccup-modus. Een instelbare uitgang wordt niet genoemd. Er is geen onafhankelijke keuring gevonden. Ongeveer € 50 (Amazon, 9-11-2026). |
| Omzetter | **Victron Orion-Tr 24/12-20, geïsoleerd, zonder Bluetooth (ORI241224110)** (keuze) | Een vaste uitgang is genoeg, omdat in fase 2 alles in de schuur geregeld wordt. | 12,2 V nominaal, 20 A (240 W), IP43. Ingang 16–35 V (sommige bronnen noemen 18–35 V). Volgens retailers is de uitgang instelbaar, maar hoe is niet gevonden. Niet bedoeld om accu's te laden; dat doet hij hier ook niet. |

**Waarom 24 V naar de chalet (keuze):** bij 12 V hangt de spanning bij de chalet af van de belasting. Als de kachel aanslaat (8 A) zakt hij in de kabel ongeveer 0,8 V. Met de omzetter bij de chalet staat de spanning vast. Door de kabel loopt bij 24 V ook maar de helft van de stroom. In fase 2 komt de 24 V-accu dan op dezelfde kabel.

**Afgevallen:**
- **De Mean Well GST280A24-C6P (280 W):** goede beveiligingen en geen netwerk nodig, maar de gebruiker vindt hem te duur. Met de zachte start is 280 W niet nodig.
- **De Jandei 24 V 250 W IP20 (Amazon B077P6WSK4, € 19,99):** de netaansluiting moet je zelf maken, er zijn geen beveiligingen opgegeven, alleen CE, en hij is alleen voor binnen (IP20). Wel ±1 V instelbaar.
- **De Orion-Tr Smart (ORI241224120):** instelbaar via de app, met Bluetooth en een laadmodus. Ongeveer 100 euro duurder, en in dit ontwerp niet nodig.
- **De GST220A24 (220 W):** te krap zonder zachte start.
- **De HLG-240H-24A:** IP65, −40 tot +60 °C, 22,4–25,6 V instelbaar. De netkant zijn losse draden, en netaansluitingen zijn volgens de projectregels werk voor een installateur.
- **Een kleine bufferaccu parallel in de chalet:** op de vaste spanning raakt de accu nooit vol, de laadstroom na een stroomuitval is niet te begrenzen, en de accu zou in de ruimte van de kat staan.
- **De PTC-kachel op 24 V:** de kachel en zijn fan zijn 12 V. Q7 (30 V) zou op 80 % van zijn maximum werken. HEAT+ op J2 is de 12 V-rail, en er is een mogelijke vrijloopdiode naar +12 V. Bovendien vangt de stroomgrens van de Orion de piek dan niet meer op.

### Belasting

| Verbruiker | Stroom bij 12,2 V |
|---|---|
| PTC-kachel 100 W | ~8,2 A (aanname: tot ~12 A, zie hieronder) |
| Mat (5 segmenten) | ~1,4 A |
| Ventilator, ESP32, sensoren | ~0,3 A |
| **Totaal** | **~10 A, ~125 W (tot ~170 W)** |

**Aanname, de PTC bij kou:** de 100 W geldt waarschijnlijk bij kamertemperatuur. Met de fan en lucht van 0–8 °C wordt een PTC kouder gehouden en trekt hij meer, schatting tot ongeveer 150 W. Bij het inschakelen is hij kort nog hoger.

**Vermogen van de netvoeding**, met een rendement van de Orion van ongeveer 87 % (aanname) en de kabel van ongeveer 10 m hieronder:

| Situatie | Uit de Orion | Uit de netvoeding |
|---|---|---|
| Normaal (kachel 100 W) | ~125 W | ~150 W |
| Kachel bij kou (~150 W) | ~170 W | ~205 W |
| Inschakelpiek, de Orion op zijn grens van 20 A | ~245 W | ~300 W |

- **Gevolg:** zonder maatregel kan een voeding van 250 W bij de inschakelpiek in hiccup gaan. Dan starten de Orion, de ESP32 en de kachel telkens opnieuw op, juist in de koudste nacht. Het vermogen van de Orion (240 W) is de bovengrens. Een voeding die die grens altijd aankan, moet ongeveer 290 W leveren.
- **Keuze, zachte start (9-11-2026):** de controller stuurt de kachel via PWM op GPIO 23 (LEDC, 20 kHz). Na elke inschakeling loopt het vermogen op van 30 % naar het maximum. In de webinterface stel je in:
  - "Verwarmer zachte start" (standaard 60 s, 0 = uit);
  - "Verwarmer maximaal vermogen" (standaard 100 %).
  - De gemiddelde stroom blijft daardoor tijdens het opwarmen laag. De piekstroom per PWM-puls blijft wel even hoog, maar die vangen de condensatoren en de regeling van de Orion op (aanname).
- **Aanname, fan in de kachel:** als de FABULETTA een ingebouwde fan op dezelfde voeding heeft, krijgt die fan ook PWM. Controleer dat bij levering. Bromt of stopt de fan tijdens de zachte start, overleg dan.
- **Test:** zet de kachel bij de eerste vorst een keer aan en kijk of alles blijft draaien. Gaat de voeding toch in hiccup, verleng dan de zachte start of verlaag het maximale vermogen, bijvoorbeeld naar 80 %.

### Kabel schuur naar chalet

De schuur ligt hemelsbreed ongeveer 7 m van de chalet, gemeten in Google Maps. Over de route gemeten reken ik met ongeveer 10 m.

| Kabel | Weerstand (heen en terug) | Normaal (~7 A) | Piek (~12,5 A) |
|---|---|---|---|
| **2 x 2,5 mm² (keuze)** | 0,14 Ω | ~1,0 V en ~7 W verlies | ~1,8 V en ~22 W verlies |

- De ingang van de Orion blijft altijd boven 22 V. In fase 2 komt hij met een lege 24 V-accu op ongeveer 20–21 V, nog ruim boven het minimum van 16 V.
- **Keuze, kabel (9-11-2026):** **H07RN-F 3G2,5**, een rubber buitenkabel, bestand tegen UV en ozon en soepel bij vorst. **Koop 12–15 m.** De 2-aderige versie is in bouwmarkten zelden te koop.
  - Bruin is **+24 V**, blauw is **0 V**.
  - **Geel-groen niet gebruiken:** knip hem aan beide kanten kort af en isoleer hem. Die kleur is gereserveerd voor de beschermingsaarde, en iemand die later aan de kabel werkt, verwacht daar geen +24 V of 0 V op. Verbind hem ook niet met de aarde in de schuur: het 24 V-circuit is niet geaard.
  - Ligt de kabel onder de tegels door, gebruik dan in plaats daarvan YMvK 3 x 2,5 in een PVC-buis van 16–20 mm, met dezelfde aderindeling.
  - Niet geschikt: een gewoon verlengsnoer of een binnenkabel (H05VV-F, VMvL), die bij vorst en UV hard worden en scheuren.
- **Voorkeur, invoer bij de chalet:** van onderen, met een druppellus, door een kabelwartel (IP68). Markeer plus en min aan beide kanten.
- **Voorkeur, bescherming:** waar de kat of knaagdieren bij de kabel kunnen, gaat hij in ribbelbuis of een metalen buis. Dat geldt vooral bij de veranda en de trap.
- **Voorkeur, stekker:** een waterdichte stekker van IP67 of beter, bijvoorbeeld een M12 met 2 polen, of een Anderson-stekker in een kap.
- **Aansluiten in de schuur:** de DC-stekker van de voeding afknippen en in een lasdoos op de buitenkabel zetten. Of een bijpassende contrastekker kopen. Welk type DC-stekker erop zit, controleer je bij levering.

### Instellen en controleren

- **Afschakelgrenzen in de config (keuze, 9-11-2026):** kachel uit onder **11,5 V**, mat uit onder **11,3 V**. Ze gaan weer aan bij 0,4 V hoger, dus bij 11,9 en 11,7 V.
  - Dit is een vangnet onder de vaste 12,2 V van de Orion. Met de oude grenzen (12,2 en 12,0 V, voor een 12 V-loodaccu) zou de kachel op de normale uitgangsspanning al afvallen.
  - De waarden worden onthouden (restore_value). Is de ESP32 al eerder geflasht, pas ze dan in de webinterface aan.
  - Meet wat de INA226 ziet terwijl de kachel aan staat. Dat moet ruim boven 11,9 V blijven.
- **Remote on/off (aanname):** de Orion heeft een aansluiting voor remote on/off. Controleer bij levering dat de doorverbinding erin zit, anders schakelt hij niet in.
- **Zekering:** de controller heeft zijn eigen zekeringen F1 (20 A) en F2 (15 A traag). Tussen de Orion en de controller is geen extra zekering nodig.
- **Plaats van de Orion (voorkeur):** in de bovenkamer, bij de controller. Zijn verlieswarmte (10–20 W bij vollast) komt dan ten goede aan de kamer. Monteer hem buiten het bereik van de kat, in dezelfde dichte kast als de controller, met ventilatieopeningen.
- **Stroomuitval:** valt de stroom in de schuur weg, dan staat in fase 1 alles stil: mat, kachel en controller. De ESP32 is dan ook offline, dus Home Assistant ziet hem verdwijnen. Stel daar een melding op in.
- **Verbruik uit het net (aanname):** het verbruik bij de chalet plus 15–20 % verlies in de netvoeding, de kabel en de Orion. Dat is ongeveer 0,5–1,4 kWh per dag in de winter.

## 3. Fase 2: 24 V-accu, zon en noodstroom in de schuur (keuze, uitwerking later)

```
schuur                                                         chalet
zonnepaneel ─ MPPT 24 V ─┬─ accu 24 V ── zekering
                         │                                     
                         └─[ideale diode 1]─┐
                                            ├─ 24 V ═══ kabel ═══ Orion → 12,2 V → controller
230 V ─ netvoeding (instelbaar) ─[ideale diode 2]─┘                 └ GPIO 33 meet de 24 V (aanpassing)
```

### Werking (diode-OR)

- **Accu boven de overnamespanning:** de accu voedt de kabel. Diode 2 spert, het net levert niets.
- **Accu eronder:** de netvoeding neemt het over. Diode 1 spert, dus de accu wordt niet verder ontladen en ook niet vanuit het net geladen. De accu blijft vrij voor de zonnestroom.
- **Zon laadt de accu op:** de accuspanning stijgt en de accu neemt de chalet vanzelf weer over. De zon gaat dus altijd eerst.
- **Geen stroom van het net:** automatisch op de accu.

| Onderdeel | Eis (voorkeur, type niet nagezocht) |
|---|---|
| Netvoeding | Instelbaar op de overnamespanning: ~24,8 V voor lood (2 x 12 V), ~26,0 V voor LiFePO4 (8s). Voor zover bekend staat de GST280A24 vast op 24 V. Daarmee neemt het net pas over bij een bijna lege accu (12,0 V per loodblok, 3,0 V per cel). Zoek dus een instelbare voeding, of kies een andere manier om over te nemen. |
| 2 ideale-diodemodules | Op basis van een MOSFET, bijvoorbeeld met de LM74700 of LTC4357, ≥15 A bij 24 V. Geen gewone of Schottky-diode. |
| Zekering bij de accu | Direct op de pluspool, ongeveer 15 A. Een accu levert bij kortsluiting honderden tot duizenden ampère. |

**Voordelen van de schuur (keuze):** geen accu in de ruimte van de kat, geen laadgas in de chalet, en meer plaats voor een groter zonnepaneel.

### Accu

Per vorstnacht van 16 uur is in de chalet ongeveer 575 Wh nodig. Met ongeveer 15 % verlies in de Orion en de kabel komt dat neer op ongeveer **680 Wh uit de accu**.

| | Lood 24 V (2 x 12 V in serie) | LiFePO4 24 V (8s) |
|---|---|---|
| Bruikbaar deel (aanname) | 50 % ontlaaddiepte × ~80 % bij kou = 40 % | ~90 %, bij kou ~80 % |
| Minimaal voor één nacht | ~70 Ah | ~35 Ah |
| Voorkeur | ~100 Ah (met 30 % marge) | **50 Ah (~1280 Wh)**: twee vorstnachten of één etmaal vorst |

- **Kou in de schuur:** hoe koud het in de schuur wordt, is niet bekend. Een loodaccu verliest bij vorst capaciteit. LiFePO4 mag niet laden onder 0 °C, dus neem een accu met een BMS dat laden bij kou blokkeert, of met ingebouwde verwarming, of zet hem in een geïsoleerde kast.
- **De huidige oude loodaccu (12 V):** past niet in een systeem van 24 V. Dan heb je twee gelijke blokken in serie nodig.
- **Laden van een loodaccu:** in de schuur mag dat; het laadgas komt dan niet bij de kat. Zorg voor ventilatie.

### Afschakelgrenzen in fase 2

De ESP32 moet dan de 24 V meten. Aan de 12 V-kant zie je een lege accu niet aankomen: de Orion levert 12,2 V tot hij bij ongeveer 14 V ingangsspanning abrupt uitvalt.

- **Meting op GPIO 33 (voorkeur):** gebruik de reservemeting op GPIO 33, nu een deler 100k/18k op de 12 V.
  - Plaats de bovenste weerstand van 100k niet, en zet er een weerstand van ongeveer 220k voor in de plaats, met een draad naar de 24 V-ingang.
  - Dan geeft 29 V ongeveer 2,2 V op de pin. Met 100k zou 24 V al 3,7 V geven, te veel voor de ADC.
  - **Massa:** verbind de min van 24 V met de massa van de controller, want de Orion is geïsoleerd.
  - **Print:** de exacte plek van de deler op de print kan ik niet nakijken, omdat het schemascript niet in de repo staat.
- **De INA226 blijft nuttig:** hij blijft de stroom van de mat en de 12 V-uitgang van de Orion meten.

**Grenzen** (aanname, richtwaarden, gemeten bij de chalet, ongeveer 0,5–1 V onder de accuspanning door de kabel; 30 s gemiddeld):

| Accu in de schuur | Kachel uit | Mat uit |
|---|---|---|
| Lood 2 x 12 V | ~24,2 V | ~23,8 V |
| LiFePO4 8s | ~25,6 V | ~24,8 V |

Met de netvoeding als noodstroom komen deze grenzen alleen in beeld als ook het net wegvalt. De 12 V-grenzen (11,5 en 11,3 V) blijven als vangnet staan.

### Zonnepaneel en lader

- **Opbrengst in december (bron: `berekening.py`):** 18–32 kWh per kWp per maand, dus 0,6–1,0 kWh per kWp per dag. Dat geldt voor een paneel op het zuiden zonder schaduw.
- **Benodigd paneel:**
  - Voor een gewone decemberdag (~450 Wh bij de chalet, ~530 Wh uit de accu): ongeveer 650–1000 Wp.
  - Voor vorst: 1–2 kWp.
- **Conclusie (aanname):** met een paneel van een paar honderd Wp red je het van maart tot oktober. In december en januari levert het een deel, en de rest komt van het net.
- **Plaats (voorkeur):** op of bij de schuur. Daar heb je meer plaats dan de 1,42 x 1,04 m van het dak van de chalet. Monteer het steil (ongeveer 60°) voor de lage winterzon, die in december 's middags maar ongeveer 15° hoog staat. Niet aan de schutting: de palen staan niet in beton.
- **Lader (voorkeur):** een MPPT-regelaar voor 24 V, bijvoorbeeld uit de Victron SmartSolar-serie, passend bij het paneel. Model en specificaties zijn nog niet nagezocht.

### Monitoren

- **De ESP32 in de chalet:** ziet via de 24 V-meting of het systeem draait en hoe vol de accu ongeveer is.
- **Laadgegevens (voorkeur):** paneelvermogen, laadstroom en lading van de MPPT kun je in de schuur uitlezen met een tweede ESP32. Dat kan via Bluetooth (ESPHome `victron_ble`, nagaan welke modellen ondersteund worden) of via VE.Direct. Hij stuurt de gegevens naar Home Assistant.
- **Bluetooth vanuit de chalet:** de ESP32 in de chalet zit ongeveer 7 m verder en door muren. Dat is waarschijnlijk niet betrouwbaar (aanname).

### Mat alleen als de kat erop ligt (idee, voor elke fase)

De mat is de grootste verbruiker: ongeveer 408 Wh per dag, ook als de mat leeg is. Je zou aanwezigheid kunnen afleiden uit het warmteverloop van de NTC's. Dit is niet uitgewerkt.

## 4. Open punten

- Lengte van de kabelroute. Ik heb gerekend met ongeveer 10 m, hemelsbreed is het ongeveer 7 m.
- De netvoeding: werktemperatuur, de DC-aansluiting (losse draden of stekker), en de werkelijke kwaliteit. Het is een merkloze voeding zonder onafhankelijke keuring. Hang hem op een onbrandbare ondergrond.
- Handleiding van de Orion-Tr 24/12-20 (ORI241224110). Te controleren: de werkelijke uitgangsspanning, of en hoe die in te stellen is, het ingangsbereik (16–35 of 18–35 V), en de remote on/off.
- Het werkelijke vermogen van de PTC-kachel bij kou en met de fan, het gedrag bij inschakelen, en of de zachte start genoeg is. Meet het met de INA226 of een losse meter.
- De zachte start is niet gevalideerd met ESPHome, want ESPHome is niet geïnstalleerd. Voer `esphome config kattenmat.yaml` uit voor het flashen.
- Fase 2: instelbare netvoeding, accusoort, temperatuur in de schuur, MPPT en paneel, en de 24 V-meting op GPIO 33.
- De echte Uw van het raam (kozijnbreedte, afstandhouder).
- `bouwplan/berekening.py` en de tekst in het plan rekenen nog met 11 °C, −5 °C en netvoeding. Die zijn niet bijgewerkt.
- Prijzen zijn niet nagezocht.

## Bronnen

- Orion-Tr 24/12-20 (ORI241224110): [Wholesale Marine](https://www.wholesalemarine.com/victron-orion-tr-dc-dc-converter-24-vdc-to-12-vdc-20amp-isolated/),
  [FV Componentes](https://fvcomponentes.com/en/?p=15085), [Solar-Electric](https://www.solar-electric.com/victron-energy-orion-tr-24-12-20a-dc-dc-converter.html),
  [Victron-datasheet Orion-Tr geïsoleerd 250 W (kopie)](https://portal.segensolar.co.za/reseller/docs/Datasheet-Orion-Tr-DC-DC-converters-isolated-250W-EN.pdf)
- Orion-Tr Smart 24/12-20 (afgevallen): [offgridtec](https://www.offgridtec.com/en/victron-orion-tr-smart-24-12-20a-240w-dc-dc-converter.html),
  [navstore](https://navstore.com/products/victron-orion-tr-smart-24-12-20a-240w-isolated-dc-dc-charger-ori241224120)
- GST280A24 (afgevallen): [Mean Well-datasheet (via Mean Well Australia)](https://meanwellaustralia.com.au/sites/default/files/2024-12/MEAN%20WELL%20GST280A%20DATA%20SHEET.pdf),
  [RS](https://uk.rs-online.com/web/p/ac-dc-adapters/1176162), [Master Electronics](https://masterelectronics.com/en/mean-well/gst280a24c6p-48236195.html)
- GST220A24-R7B (afgevallen): [octopart](https://octopart.com/part/mean-well/GST220A24-R7B)
- HLG-240H-24A (afgevallen): [RS](https://hkcn.rs-online.com/web/p/led-drivers/7647366)
