# Smart Heating Schedule

Ein Wochenplan pro Raum für Better Thermostat. Vier Zeitfenster mit eigenen
Startzeiten und Presets für Montag–Freitag, Samstag und Sonntag; ein fünftes
Zeitfenster lässt sich zuschalten. Die Temperaturen der Presets werden in
Better Thermostat konfiguriert, nicht durch diesen Blueprint gesetzt.

## Installation

Voraussetzung: Home Assistant **2026.9.0** oder neuer, Better Thermostat und
Thermostat-Entitäten, die die ausgewählten Presets unterstützen.

[Blueprint importieren](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https://github.com/JonasKa23/ha-blueprints/blob/main/automations/smart_heating_schedule.yaml)

Der Import-Link funktioniert, sobald die Datei auf GitHub veröffentlicht wurde.
In Home Assistant unter **Einstellungen → Automatisierungen & Szenen → Blueprints**
importieren, anschließend pro Raum eine Automation erstellen und die
Better-Thermostat-Entität auswählen. Bei manuellem Import einen Pfad
`JonasKa23/smart_heating_schedule.yaml` verwenden oder den `use_blueprint.path`
in den Beispielen entsprechend anpassen.

Die sechs Dateien unter [examples/heating](../examples/heating/) können in den
YAML-Editor jeweils einer neuen Automation eingefügt werden. Alle Entitäten mit
`ersetzen_` sind Platzhalter. Die Beispiele starten mit `initial_state: false`.
Nach dem Ersetzen und Prüfen diese Zeile entfernen und die Automation einschalten;
sonst wird sie bei jedem Neustart wieder ausgeschaltet.

Die ursprünglichen `night_mode`- und `presence_away_preset`-Automationen dürfen
dieselben Thermostate nicht gleichzeitig steuern. Bei der Umstellung bestehende
Heizungsautomationen prüfen und gezielt deaktivieren. Andere Better-Thermostat-
Funktionen, etwa die Fenstererkennung, bleiben Aufgabe der Integration.

## Verhalten

- **Zeitplan:** Die Zeiten jedes Tagestyps müssen streng aufsteigend sein.
  Gleiche oder rückwärts angeordnete Zeiten blockieren alle Preset-Änderungen.
  Der deaktivierte fünfte Slot wird bei der Prüfung ignoriert.
- **Nach Mitternacht:** Bis zum ersten Slot gilt der letzte aktivierte Slot des
  vorherigen Tages. Ein Slot um **00:00** überschreibt diesen mit dem Preset
  des neuen Tages. Die Schlafzimmer-Vorlage nutzt das ausdrücklich: Samstag ab
  00:00 `eco`, Montag ab 00:00 `sleep`.
- **Anwesenheit:** Eine Person/ein Tracker mit `home` oder ein binärer
  Sensor/Helfer mit `on` reicht für Anwesenheit. Andere bekannte Personen- und
  Tracker-Standorte, einschließlich benannter Zonen, gelten als abwesend;
  binäre Sensoren/Helfer nur bei `off`.
- **Unklarer Status:** Wenn niemand sicher zuhause ist und mindestens ein
  Anwesenheitssignal `unknown`/`unavailable` ist, bleibt das aktuelle Preset
  unverändert. Eine aktivierte, aber leere Anwesenheitsauswahl blockiert ebenfalls.
- **Abwesenheit:** Alle ausgewählten Entitäten müssen für mindestens die
  eingestellte Dauer sicher abwesend sein (Standard zwei Minuten). Anschließend
  wird beim nächsten Abgleich das Abwesenheits-Preset gesetzt, spätestens etwa
  eine weitere Minute später. Ein Standortwechsel oder Neustart beginnt die
  Bestätigungsdauer für die betroffene Entität neu. Heimkehr wirkt sofort.
  Die sechs Raumvorlagen setzen `away_delay: 0`: Sobald alle sicher abwesend
  sind, gilt ohne Bestätigungswartezeit `away`. Unklare Anwesenheit blockiert weiterhin.
- **Neustart und Wiederverfügbarkeit:** Ein minütlicher Abgleich ergänzt die
  exakten Uhrzeit- und Zustands-Trigger. Damit werden verpasste Schaltzeiten,
  Automation-Reloads und spät verfügbare Thermostate nachgeholt.
- **Thermostate:** Nur verfügbare, eingeschaltete Entitäten mit Unterstützung
  für das Ziel-Preset werden geändert. Bereits passende Presets werden nicht
  erneut gesetzt. Der Blueprint schaltet den HVAC-Modus nicht ein oder aus.

## Pausen

Für eine dauerhafte Pause unter **Einstellungen → Geräte & Dienste → Helfer**
einen Schalter (`input_boolean`) anlegen und auswählen. Solange mindestens ein
ausgewählter Helfer `on` ist, bleibt der Zeitplan pausiert. Erst wenn alle `off`
sind, wird er fortgesetzt. Fehlende/unbekannte Helfer und eine leere aktivierte
Auswahl blockieren Änderungen ebenfalls.

Für eine zeitlich begrenzte manuelle Übersteuerung je Raum einen **Taster**
(`input_button`) und einen eigenen **Timer** erstellen. Beim Timer
**Wiederherstellung** aktivieren. Beide im Blueprint auswählen, Funktion
aktivieren und die Dauer einstellen.

1. Taster drücken und prüfen, dass der Timer läuft.
2. Temperatur oder Preset am Thermostat manuell einstellen.
3. Nach Timer-Ende übernimmt der Plan wieder das dann gültige Preset.

Erneutes Drücken beginnt die Dauer neu. Timer-Abbruch beendet die Pause sofort;
ein pausierter Timer hält auch den Heizplan an. Eine permanente Pause hat weiterhin
Vorrang. Eine manuelle Änderung am Thermostat startet **nicht automatisch** eine
Pause. Ohne Pause kann ein abweichendes Preset beim nächsten minütlichen Abgleich
wieder ersetzt werden. Änderungen der Temperatur bei unverändertem Preset werden
nicht erkannt: Der Blueprint synchronisiert Presets, keine Solltemperaturen.

Ein wiederhergestellter aktiver Timer schützt die Pause über einen Neustart hinweg.
Wenn er während eines HA-Ausfalls endet, holt der minütliche Abgleich die Rückkehr
zum Zeitplan nach. Das ist erforderlich, weil dann kein `timer.finished`-Ereignis
nachgeliefert wird ([Home-Assistant-Timer-Dokumentation](https://www.home-assistant.io/integrations/timer/)).

## Raumvorlagen und Temperaturen

Diese Temperaturzuordnung stammt aus der Planung des Nutzers. Sie muss in den
jeweiligen Better-Thermostat-Presets hinterlegt werden; die Beispielautomationen
ändern diese Konfiguration nicht.

| Raum          | away  | eco   | sleep | home  | comfort |
| ------------- | ----- | ----- | ----- | ----- | ------- |
| Wohnzimmer    | 17 °C | 18 °C | 18 °C | 21 °C | 22 °C   |
| Arbeitszimmer | 16 °C | 18 °C | 18 °C | 21 °C | 22 °C   |
| Bad           | 17 °C | 18 °C | 18 °C | 21 °C | 22 °C   |
| Schlafzimmer  | 16 °C | 17 °C | 18 °C | 18 °C | 19 °C   |
| Küche         | 16 °C | 17 °C | 17 °C | 19 °C | 20 °C   |
| Klo           | 16 °C | 17 °C | 17 °C | 19 °C | 20 °C   |

### Zeitpläne – Nutzerübersicht vom 09.10.2026

Die Raumvorlagen enthalten folgende Pläne. Jeder Eintrag gilt ab der angegebenen
Uhrzeit bis zum nächsten Wechsel. Samstag und Sonntag sind jeweils identisch.

| Raum          | Montag–Freitag                                                     | Samstag–Sonntag                        |
| ------------- | ------------------------------------------------------------------ | -------------------------------------- |
| Wohnzimmer    | 00:00 sleep · 06:00 home · 22:00 sleep                             | 00:00 sleep · 07:00 home · 22:30 sleep |
| Arbeitszimmer | 00:00 sleep · 06:00 home · 21:30 sleep                             | 00:00 sleep · 08:00 home · 21:30 sleep |
| Bad           | 00:00 sleep · 05:35 comfort · 06:45 eco · 18:00 home · 22:00 sleep | 00:00 sleep · 09:00 home · 22:30 sleep |
| Schlafzimmer  | 00:00 sleep · 05:40 comfort · 07:10 eco · 20:00 sleep              | 00:00 eco · 06:30 sleep · 22:00 eco    |
| Küche         | 00:00 eco · 06:00 home · 21:00 eco                                 | 00:00 eco · 07:00 home · 21:00 eco     |
| Klo           | 00:00 eco · 06:30 home · 22:00 eco                                 | 00:00 eco · 06:30 home · 22:00 eco     |

Damit gilt im Bad werktags morgens `comfort` (22 °C), ab 18:00 aber **`home`
(21 °C)**. Im Schlafzimmer wechselt der Plan freitags um 20:00 auf `sleep`,
samstags exakt um 00:00 auf `eco` und montags exakt um 00:00 zurück auf `sleep`.
Auch nach einem Neustart innerhalb dieser Nachtabschnitte wird der passende
Tagesplan ermittelt.

**Bestätigungsstand:** Die angepassten Zeiten für Arbeitszimmer, Küche und Klo
sind übernommen. Die ursprünglich aus tado-Diagrammen geschätzten Zeiten für
Wohnzimmer, Bad und Schlafzimmer bleiben gemäß Nutzerübersicht vorläufig,
soweit noch nicht ausdrücklich bestätigt. Sie sind trotzdem genau wie oben
angegeben in den Vorlagen hinterlegt, nicht durch Upstream-Standardzeiten ersetzt.

**Abbildung auf vier Slots:** Bei drei täglichen Einträgen wiederholt Slot 4 um
23:59 lediglich das bereits geltende Nacht-Preset. Das erzeugt keinen zusätzlichen
Temperaturwechsel; ein bereits passendes Preset wird nicht erneut gesetzt.
Im Bad reichen werktags die vier echten Wechsel ab 05:35: Vorher gilt das
`sleep`-Preset vom Vorabend. Der optionale fünfte Slot bleibt überall deaktiviert.

Die optionalen Pausen sind in den Vorlagen deaktiviert, bis echte Helfer ausgewählt
wurden. Entitäts-Platzhalter und die anfängliche Deaktivierung bleiben bestehen.

## Benachrichtigungen und Diagnose

Über den Aktions-Selector lassen sich beliebige Benachrichtigungsaktionen hinzufügen.
Die Variablen `heating_entity`, `desired_preset`, `schedule_info` und
`presence_status` stehen darin zur Verfügung. Beispiel für eine Nachricht:
`{{ heating_entity }}: Heizplan setzt {{ desired_preset }}`.

Die Aktionen laufen nach einem Preset-Aufruf nur, wenn die Entität das Ziel-Preset
bereits bestätigt. Bei verzögerten Geräte-Rückmeldungen kann eine Benachrichtigung
ausbleiben. Behandelbare Laufzeitfehler werden mit `continue_on_error` übergangen;
ungültige Templates, fehlende Aktionen oder ein explizites `stop` können den
aktuellen Lauf dennoch beenden. Der nächste minütliche Abgleich versucht es erneut.
Keine langen Warteaktionen einfügen: Die Automation arbeitet ihre Aufrufe der Reihe
nach ab. Für Verzögerungen ein separates Script starten.

Anwesenheit, Pause und aktuelles Zeitfenster werden unmittelbar vor jedem
Thermostat-Aufruf erneut ermittelt, auch wenn vorherige Aufrufe länger dauerten.

Es werden 20 Traces gespeichert. Im Variablen-Schritt zeigen `schedule_info`,
`presence_status` und `pause_blocked` die Entscheidung. Die optionale Diagnose
schreibt zusätzlich bei jedem Abgleich ins Systemprotokoll; sie ist für kurze
Fehlersuche gedacht. Nicht unterstützte Presets, ausgeschaltete und nicht verfügbare
Thermostate werden im Trace am jeweiligen Bedingungsschritt übersprungen.

## Herkunft, Lizenz und Updates

Abgeleitet von
[Better Thermostat – weekly_heating_schedule.yaml, Commit 5b4496d](https://github.com/KartoffelToby/better_thermostat/blob/5b4496de5659fd2c6ec5c67a9797e6659797866c/blueprints/weekly_heating_schedule.yaml).
Der Lizenztext des Ursprungsprojekts liegt unter
[LICENSES/Better-Thermostat-AGPL-3.0.txt](../LICENSES/Better-Thermostat-AGPL-3.0.txt).
Diese abgeleitete Blueprint-Datei steht unter AGPL-3.0. Dieser Hinweis ändert
nicht die Lizenz anderer, unabhängiger Dateien in diesem Repository.

Änderungen vom 09.10.2026: Vortagesbezug, sichere Anwesenheits-/Pausenprüfung,
gemeinsamer Abgleich aller Auslöser, Wiederanlauf, fünfter Slot, Timer-Pause,
Aktions-Selector für Meldungen und Diagnose. Dies ist ein neuer Blueprint mit
eigenen Inputs: Statt `thermostat_target` wird `thermostat_entities` verwendet;
`enable_notify`/`notify_target` werden durch `notification_actions` ersetzt.
Bestehende Original-Automationen daher nicht allein durch Austausch des Pfads migrieren.

Die Action [check-upstream.yml](../.github/workflows/check-upstream.yml) prüft
montags um **07:23 UTC** (08:23 MEZ / 09:23 MESZ) sowie auf manuellen Aufruf.
Sie benötigt GitHub Actions und Issues im Repository und wird nach Veröffentlichung
auf dem Standardbranch aktiv. Bei einem als Fork geführten Repository geplante
Workflows gegebenenfalls auf GitHub aktivieren. GitHub kann geplante Läufe verzögern
und bei längerer Repository-Inaktivität deaktivieren
([GitHub-Dokumentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)).

Verglichen wird der **Dateiinhalt** mit `reviewed_blob` aus
[upstream/better_thermostat.json](../upstream/better_thermostat.json).
Andere Änderungen am Better-Thermostat-Repository erzeugen keinen Hinweis.
Ein geänderter Inhalt erzeugt einen Issue mit Vergleich, Dateihistorie und
festen Links auf beide Stände. Bereits gemeldete Inhalte werden auch nach dem
Schließen des Issues nicht nochmals gemeldet. API-Fehler machen den Lauf rot,
statt fälschlich „unverändert“ zu melden.

Updates werden **niemals automatisch übernommen**. Nach manueller Prüfung und
gegebenenfalls Übernahme `reviewed_commit` und `reviewed_blob` gemeinsam auf die
im Issue genannten Werte setzen. Auch bewusst abgelehnte Änderungen können so
als geprüft markiert werden. Der Workflow schreibt keine Dateien und benötigt
keine Berechtigung zum Pushen.

Lokale Prüfung ohne Issue-Erstellung:

```sh
python3 scripts/check_heating_upstream.py
python3 -m unittest discover -s tests
python3 skills/ha-blueprint-dev/scripts/validate_blueprint.py automations/smart_heating_schedule.yaml
```

Die Tests rendern die tatsächlichen Blueprint-Templates für Tageswechsel,
Slotgrenzen, Sommerzeit, Anwesenheit und Pausen. Ein Import- und Funktionstest in
der Zielinstallation ist zusätzlich erforderlich; die Raumdateien sind Vorlagen.
