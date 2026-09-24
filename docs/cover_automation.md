# Rollladensteuerung

Diese Anpassung basiert auf der Rollladensteuerung V2 von TheRealSimon42.
Pro Rollladen wird eine Automation mit einem binären Fensterkontakt erstellt.
0 % bedeutet geschlossen, 100 % vollständig geöffnet.

## Einrichtung und Umstellung

- Rollladen und binären Fensterkontakt auswählen.
- Gemeinsame Wetter-Entität im Abschnitt „Wetter“ auswählen; für die Temperaturprüfung
  muss sie tägliche Vorhersagen liefern. Temperaturen werden in °C erwartet.
- `window_open_position` ersetzt die bisherige Kipp-Position; Standard ist 35 %.
  Ein weiter geöffneter Rollladen wird beim Öffnen des Fensters nicht abgesenkt.
- Alte Eingaben `tilted_position`, `treat_open_as_tilted`, `notification_timeout_tilted`
  sowie `mosquito_enabled`, `mosquito_after_time`, `mosquito_area` und `mosquito_exclude`
  aus bestehenden Instanzen entfernen. Kipp-Erkennung und Moskito-Modus entfallen.
  Bisherige Drei-Zustands-Sensoren müssen durch binäre Kontakte ersetzt werden.
- Für Sonnenschutz und Sonnenheizen jeweils einen eigenen Status-Helfer pro Rollladen
  auswählen. Morgen-/Abendzeiten benötigen reine Uhrzeit-Helfer ohne Datum.

## Abend und Nacht

Der standardmäßig deaktivierte Abendmodus prüft sowohl die gewählte feste Uhrzeit
als auch Sonnenuntergang plus Offset (Standard: 30 Minuten danach). Negative Offsets
sind möglich. Ohne Uhrzeit-Helfer bleibt nur der Sonnenuntergangs-Trigger.
Der Abendmodus führt eine einzelne Fahrt aus und speichert keinen eigenen Zustand.
Beide Abendtermine prüfen ihre Bedingungen erneut. Der Rollladen fährt nur bei
geschlossenem Fenster, ohne aktiven Nachtmodus und ohne Sturm auf `evening_position`,
und nur, wenn er aktuell weiter geöffnet ist. Bei offenem Fenster entfällt die Fahrt;
sie wird beim späteren Schließen nicht eigens nachgeholt.

Ein zusätzlicher Datum-und-Uhrzeit-Helfer oder eine Abend-Endzeit ist nicht erforderlich.
Nachtmodus und morgendliches Öffnen übernehmen über ihre jeweiligen Auslöser.
Falls bereits konfiguriert, die Eingaben `evening_until_helper` und `evening_end_time`
aus der Automation entfernen. Ein eventuell angelegter Helfer wird nicht mehr verwendet.
Die bestehende Fenster-Rückfahr-Logik bleibt erhalten.

Der Nachtmodus wird durch einen input_boolean eingeschaltet. Bei geschlossenem Fenster
wird `night_closed_position`, bei offenem Fenster `night_ventilation_position` verwendet.
Abend und Nacht haben jeweils eine eigene Temperaturschwelle (Standard: 15 °C).
Die vorhergesagte Tiefsttemperatur für das heutige lokale Datum muss kleiner oder gleich
der Schwelle sein. Fehlen Wetterdaten, ein heutiger Eintrag oder eine gültige Tiefsttemperatur,
entfällt diese Prüfung. Fehler beim Forecast-Aufruf sollen die restliche Aktion nicht abbrechen.

Auch bei Fenster-Interaktion und nach dem Rückfahr-Warten wird die Nacht-Temperaturprüfung
angewendet. Ist es zu warm, gilt beim Öffnen die Tages-Lüftungsposition und beim Schließen
wird die vorherige Position wiederhergestellt. Sturm und Pause verhindern das Zurückfahren.
Der Nachtmodus-Helfer blockiert Sonnenschutz und Sonnenheizen unabhängig von der Temperatur.

## Sonnenschutz und Sonnenheizen

Der Sonnenschutz verwendet den optionalen Temperatursensor oder die vorhergesagte
Höchsttemperatur für heute. Ohne gültige Temperatur beginnt keine neue Beschattung;
ein fehlender Wert allein beendet eine laufende Beschattung nicht.
Sonnenheizen prüft jetzt ebenfalls die erwartete Tageshöchsttemperatur. Der optionale
Sensor muss daher einen Tageshöchstwert liefern, keinen aktuellen Messwert.
Ohne gültigen Höchstwert startet weder Sonnenheizen noch Beschattung.
Sonnenheizen fährt nur, wenn seine Zielposition weiter geöffnet ist als die aktuelle.

Eine aktive Beschattung führt innerhalb der Temperatur-Hysterese weiter nach:
bei Startschwelle 23 °C und Hysterese 2 °C auch zwischen 21 und 23 °C.
Bei 21 °C oder darunter endet sie. Ein fehlender Messwert allein löst keine Fahrt aus.
Sonnenschutz hat Vorrang vor Sonnenheizen, auch wenn ein kalter Morgen mit heißer
Tagesvorhersage beide Temperaturbedingungen erfüllt.

Bei erzwungener Beschattung bestimmt `shading_min_position` den Mindestspalt, auch bei
offenem Fenster. Der Standard ist 25 %; ein eingestellter Wert von 0 % lässt vollständiges Schließen zu; für Terrassentüren
ist diese Option wegen Aussperr-Gefahr nicht empfohlen.

## Bekannte Grenzen

Die Automation läuft parallel, damit Fenster-Wartezeiten andere Funktionen nicht blockieren.
Unabhängige Bewegungsbefehle können sich zeitlich überschneiden; es gibt keine zentrale
Befehlswarteschlange. Dynamische Rückfahr-Szenen überleben keinen Home-Assistant-Neustart.
Ohne gespeicherten Abendstatus können Beschattung oder Sonnenheizen nach der
Abendfahrt erneut fahren, solange ihre Bedingungen erfüllt sind und der Nachtmodus
aus ist. Bei einer frühen Abendzeit ist das zu berücksichtigen.
Ein fehlender heutiger Forecast wird nicht durch die morgige Vorhersage ersetzt.

Technische Referenzen: [Wetter](https://www.home-assistant.io/integrations/weather/),
[Script-Aktionen](https://www.home-assistant.io/docs/scripts/) und
[Dauer-Selektor](https://www.home-assistant.io/docs/blueprint/selectors/#duration-selector).

## Wartung und Prüfungen

Ein gemeinsamer Sonnen-Takt prüft alle fünf Minuten zuerst Beschattung, dann
Sonnenheizen. Beide verwenden dieselbe Vorhersage; nachts bzw. außerhalb des
Fenstersichtfelds entfällt die Forecast-Abfrage für den
Sonnen-Takt. Mit eigenem Tageshöchsttemperatur-Sensor wird ebenfalls keine
Vorhersage für diese Prüfung benötigt.

Die Forecast-Abfrage und Datumsauswertung stehen einmal als YAML-Anker
`refresh_daily_forecast` im Blueprint. Weitere Verwendungen referenzieren diese
Sequenz; zusätzliche Skripte oder Jinja-Dateien müssen nicht installiert werden.
Nach dem Lüftungs-Warten werden die Wetterwerte weiterhin neu eingelesen.

Lokale Regressionstests: `python -m unittest discover -s tests`
(benötigt `pyyaml` und `jinja2`). Sie prüfen die Entscheidungslogik mit simulierten
Zuständen und ersetzen keinen Live-Test mit Home Assistant und dem Rollladen.
