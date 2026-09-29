# Rollladensteuerung

Diese Anpassung basiert auf der Rollladensteuerung V2 von TheRealSimon42.
Pro Rollladen wird eine Automation mit einem binären Fensterkontakt erstellt.
0 % bedeutet geschlossen, 100 % vollständig geöffnet.

## Einrichtung und Umstellung

- Rollladen und binären Fensterkontakt auswählen.
- Gemeinsame Wetter-Entität im Abschnitt „Wetter“ auswählen; für die Temperaturprüfung
  muss sie tägliche Vorhersagen liefern. Temperaturen werden in °C erwartet.
- Der optionale Tageshöchsttemperatur-Sensor entfällt. Alte `shading_temp_sensor`-Eingaben
  aus bestehenden Instanzen entfernen. Der Sonnenschutz verwendet ausschließlich die
  Tagesvorhersage der Wetter-Entität.
- `window_open_position` ersetzt die bisherige Kipp-Position; Standard ist 35 %.
  Ein weiter geöffneter Rollladen wird beim Öffnen des Fensters nicht abgesenkt.
- Alte Eingaben `tilted_position`, `treat_open_as_tilted`, `notification_timeout_tilted`
  sowie `mosquito_enabled`, `mosquito_after_time`, `mosquito_area` und `mosquito_exclude`
  aus bestehenden Instanzen entfernen. Kipp-Erkennung und Moskito-Modus entfallen.
  Bisherige Drei-Zustands-Sensoren müssen durch binäre Kontakte ersetzt werden.
- Für Sonnenschutz einen eigenen Status-Helfer pro Rollladen auswählen.
  Morgen-/Abendzeiten benötigen reine Uhrzeit-Helfer ohne Datum.
- Sonnenheizen ist entfernt. Alte Eingaben `solar_heating_enabled`,
  `solar_heating_status_helper`, `solar_heating_temp_threshold`,
  `solar_heating_temp_hysteresis`, `solar_heating_min_position` und
  `solar_heating_position` aus bestehenden Instanzen entfernen. Die früheren
  Sonnenheizen-Helfer werden nicht mehr verwendet; vor dem Löschen andere Verwendungen prüfen.
- Sturmschutz einschließlich Panzer-Modus ist entfernt. Alte Eingaben `storm_enabled`,
  `storm_wind_sensor`, `wind_speed_threshold`, `panzer_mode` und `force_storm_action`
  aus bestehenden Instanzen entfernen. Der Blueprint benötigt keinen Windsensor mehr
  und löst keine windabhängigen Fahrten oder Sperren aus. Die Wetter-Entität bleibt
  für Temperaturvorhersagen und den optionalen Wetterlagenfilter des Sonnenschutzes erhalten.

## Pausieren

Der optionale Pausier-Helfer hat eine feste Bedeutung: **AN pausiert die Automatik,
AUS gibt sie wieder frei.** Bei mehreren ausgewählten Helfern wird wie bisher nur
pausiert, wenn alle eingeschaltet sind. Ohne Auswahl ist die Pause inaktiv.
Die Auswahl „Logik des Pausier-Helfers“ entfällt; alte `pause_mode`-Eingaben können
aus bestehenden Instanzen entfernt werden. Auch bisher mit `off_pauses` konfigurierte
Instanzen pausieren nach dem Update bei eingeschalteten Helfern.

Der manuelle „Rollladen schließen“-Knopf, das Löschen von Fenstermeldungen und das
Zurücksetzen des Beschattungsstatus bei globaler Sperre bleiben während einer Pause
aktiv. Beim Ende der Pause wird ein aktiver Nachtmodus nachgeholt; die Beschattung
wird beim nächsten regulären Takt geprüft.

## Abend und Nacht

Der standardmäßig deaktivierte Abendmodus prüft sowohl die gewählte feste Uhrzeit
als auch Sonnenuntergang plus Offset (Standard: 30 Minuten danach). Negative Offsets
sind möglich. Ohne Uhrzeit-Helfer bleibt nur der Sonnenuntergangs-Trigger.
Der Abendmodus führt eine einzelne Fahrt aus und speichert keinen eigenen Zustand.
Beide Abendtermine prüfen ihre Bedingungen erneut. Der Rollladen fährt nur bei
geschlossenem Fenster und ohne aktiven Nachtmodus auf `evening_position`,
und nur, wenn er aktuell weiter geöffnet ist. Bei offenem Fenster entfällt die Fahrt;
sie wird beim späteren Schließen nicht eigens nachgeholt.

Ein zusätzlicher Datum-und-Uhrzeit-Helfer oder eine Abend-Endzeit ist nicht erforderlich.
Nachtmodus und morgendliches Öffnen übernehmen über ihre jeweiligen Auslöser.
Falls bereits konfiguriert, die Eingaben `evening_until_helper` und `evening_end_time`
aus der Automation entfernen. Ein eventuell angelegter Helfer wird nicht mehr verwendet.
Die Fenster-Rückfahr-Logik wird durch den Morgenbefehl wie unten beschrieben aufgehoben.

Der Nachtmodus wird durch einen input_boolean eingeschaltet. Bei geschlossenem Fenster
wird `night_closed_position`, bei offenem Fenster `night_ventilation_position` verwendet.
Abend und Nacht haben jeweils eine eigene Temperaturschwelle (Standard: 15 °C).
Die vorhergesagte Tiefsttemperatur für das heutige lokale Datum muss kleiner oder gleich
der Schwelle sein. Fehlen Wetterdaten, ein heutiger Eintrag oder eine gültige Tiefsttemperatur,
entfällt diese Prüfung. Fehler beim Forecast-Aufruf sollen die restliche Aktion nicht abbrechen.

Auch bei Fenster-Interaktion und nach dem Rückfahr-Warten wird die Nacht-Temperaturprüfung
angewendet. Ist es zu warm, gilt beim Öffnen die Tages-Lüftungsposition und beim Schließen
wird die vorherige Position wiederhergestellt. Eine Pause verhindert das Zurückfahren.
Der Nachtmodus-Helfer blockiert den Sonnenschutz unabhängig von der Temperatur.

## Morgens öffnen während des Lüftens

Der Morgenbefehl hat Vorrang vor einem bereits laufenden Lüftungsvorgang. Er verwirft
die gespeicherte Rückfahrposition, auch wenn der Rollladen die Morgenzielposition bereits
erreicht hat und deshalb keine weitere Öffnungsfahrt nötig ist.

Beispiel: geschlossen (0 %) → Lüftungsposition (35 %) → Morgenbefehl (100 %) →
Fenster schließen: Der Rollladen bleibt bei 100 %.
Für diesen Lüftungsvorgang entfallen auch die Rückfahrt zur Nachtposition und
„Schließen erzwingen“ nach Ablauf des Zeitfensters. Ein durch die Pause blockierter
Morgenbefehl hebt die Rückfahrt nicht auf.

Beim nächsten Öffnen des Fensters wird wieder eine neue Ausgangsposition gespeichert.
Andere, später ausgelöste Fahrbefehle (etwa Nachtmodus oder Sonnenschutz) gelten weiterhin.
Technisch wird die dynamische Rückfahr-Szene mit
[`scene.delete`](https://www.home-assistant.io/integrations/scene/#deleting-dynamically-created-scenes)
entfernt; der Lüftungsvorgang prüft nach seinen Wartephasen, ob sie noch vorhanden ist.

## Sonnenschutz

### Gemeinsame Freigabe

Die lokale Einstellung **Sonnenschutz aktivieren** bleibt erhalten. Zusätzlich kann unter
**Globale Sonnenschutz-Freigabe (optional)** ein gemeinsamer `input_boolean` ausgewählt
werden (`shading_control_helper`). Ohne Auswahl gilt das bisherige Verhalten.

1. Unter **Einstellungen → Geräte & Dienste → Helfer → Helfer erstellen → Schalter**
   einen Helfer anlegen, beispielsweise `input_boolean.sonnenschutz_freigabe`.
2. Den aktualisierten Blueprint in Home Assistant erneut importieren und in allen
   gewünschten Rollladen-Automationen denselben Helfer auswählen.
3. **Sonnenschutz aktivieren** in diesen Automationen eingeschaltet lassen und den
   Helfer als Schalter im Dashboard verwenden.

**AN:** Prüft sofort Sonnenstand, Temperatur und die übrigen Beschattungsbedingungen.
Der Schalter erzwingt keine Fahrt; Nachtmodus, Fensterbedingungen und die
allgemeine Pause bleiben wirksam. Während einer Pause erfolgt keine sofortige Prüfung;
nach deren Ende greift wieder der regelmäßige Fünf-Minuten-Takt.

**AUS:** Beendet die Beschattung ohne neuen Fahrbefehl und setzt den jeweiligen
Beschattungsstatus zurück, auch während einer allgemeinen Pause. Bereits gestartete
Motorfahrten werden nicht gestoppt. Weitere Sonnenschutzfahrten, einschließlich des
automatischen Öffnens am Beschattungsende, bleiben gesperrt. Morgen-, Abend-, Nacht-
und Fensterfunktionen arbeiten weiterhin nach ihren eigenen Regeln.
Ein ausgewählter Helfer mit Zustand `unknown` oder `unavailable` sperrt die Beschattung ebenfalls.

Die Freigabe ist ein **separater gemeinsamer Helfer**. Der bestehende
`shading_status_helper` bleibt ein **eigener Status-Speicher pro Rollladen** und darf
nicht als globaler Schalter verwendet werden. Beim erneuten Freigeben kann die
Beschattung neu beginnen, auch wenn die Position zwischenzeitlich manuell verändert wurde.

### Temperatur und Nachführung

Der Sonnenschutz verwendet die vorhergesagte Höchsttemperatur für heute aus der
Wetter-Entität. Ohne Wetter-Entität oder gültige heutige Höchsttemperatur beginnt keine neue Beschattung;
ein fehlender Wert allein beendet eine laufende Beschattung nicht.

Eine aktive Beschattung führt innerhalb der Temperatur-Hysterese weiter nach:
bei Startschwelle 23 °C und Hysterese 2 °C auch zwischen 21 und 23 °C.
Bei 21 °C oder darunter endet sie. Ein fehlender Messwert allein löst keine Fahrt aus.

Bei erzwungener Beschattung bestimmt `shading_min_position` den Mindestspalt, auch bei
offenem Fenster. Der Standard ist 25 %; ein eingestellter Wert von 0 % lässt vollständiges Schließen zu; für Terrassentüren
ist diese Option wegen Aussperr-Gefahr nicht empfohlen.

## Benachrichtigungen bei Anwesenheit

Unter **Benachrichtigungen** lässt sich **Nur Personen benachrichtigen, die zuhause sind**
einschalten. Standardmäßig ist die Prüfung ausgeschaltet. Wähle die gewünschten
**Benachrichtigungs-Geräte** aus und füge unter **Personen je Benachrichtigungsgerät**
für jedes Gerät einen Eintrag mit seiner Person hinzu. Eine Person kann mehrere Geräte
haben. Die Zuordnung erfolgt ausdrücklich über das Gerät, nicht über die Reihenfolge
in den Auswahllisten.

Bei aktivierter Prüfung wird unmittelbar vor jeder Nachricht nur die zu diesem Gerät
gehörende Person geprüft. Beispiel: Anna ist zuhause, Ben unterwegs → nur Annas Gerät
erhält die Erinnerung. Sind beide zuhause, erhalten beide die Nachricht; ist niemand
zuhause, erhält niemand eine Nachricht. Ohne eindeutige Zuordnung oder bei unbekanntem
bzw. nicht verfügbarem Personenstatus wird das betreffende Gerät übersprungen.
Bei späterer Heimkehr wird keine Nachricht nachgeholt. Bereits gesendete Meldungen
werden beim Schließen des Fensters weiterhin auf allen ausgewählten Geräten entfernt.

Auch bei nur einem Gerät wird die Person über die Zuordnungsliste festgelegt.

Die Zuordnung verwendet ein Formular mit wiederholbaren Einträgen
([Home-Assistant-Objektselektor](https://www.home-assistant.io/docs/blueprint/selectors/#object-selector)).

Die gleichen Einstellungen gibt es im Blueprint
`automations/fenster-offen-benachrichtigung.yaml` für Fenster ohne motorisierten Rollladen.

## Bekannte Grenzen

Die Automation läuft parallel, damit Fenster-Wartezeiten andere Funktionen nicht blockieren.
Unabhängige Bewegungsbefehle können sich zeitlich überschneiden; es gibt keine zentrale
Befehlswarteschlange. Dynamische Rückfahr-Szenen überleben keinen Home-Assistant-Neustart.
Ohne gespeicherten Abendstatus kann die Beschattung nach der
Abendfahrt erneut fahren, solange sie freigegeben ist, ihre Bedingungen erfüllt sind und der Nachtmodus
aus ist. Bei einer frühen Abendzeit ist das zu berücksichtigen.
Ein fehlender heutiger Forecast wird nicht durch die morgige Vorhersage ersetzt.

Technische Referenzen: [Wetter](https://www.home-assistant.io/integrations/weather/),
[Script-Aktionen](https://www.home-assistant.io/docs/scripts/) und
[Dauer-Selektor](https://www.home-assistant.io/docs/blueprint/selectors/#duration-selector).

## Wartung und Prüfungen

Ein Sonnen-Takt prüft alle fünf Minuten die Beschattung. Bei gesperrter Freigabe
oder außerhalb des Fenstersichtfelds entfällt die Forecast-Abfrage für diesen Takt.
Das Einschalten der Freigabe löst dieselbe Prüfung sofort aus. Die Freigabe wird nach
der Wetterabfrage und vor Beschattungsfahrten erneut geprüft.

Die Forecast-Abfrage und Datumsauswertung stehen einmal als YAML-Anker
`refresh_daily_forecast` im Blueprint. Weitere Verwendungen referenzieren diese
Sequenz; zusätzliche Skripte oder Jinja-Dateien müssen nicht installiert werden.
Nach dem Lüftungs-Warten werden die Wetterwerte weiterhin neu eingelesen.

Lokale Regressionstests: `python -m unittest discover -s tests`
(benötigt `pyyaml` und `jinja2`). Sie prüfen die Entscheidungslogik mit simulierten
Zuständen und ersetzen keinen Live-Test mit Home Assistant und dem Rollladen.
