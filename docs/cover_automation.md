# Rollladensteuerung

Diese Anpassung basiert auf der Rollladensteuerung V2 von TheRealSimon42.
Pro Rollladen wird eine Automation mit einem binären Fensterkontakt erstellt.
0 % bedeutet geschlossen, 100 % vollständig geöffnet.

## Einrichtung und Umstellung

- Rollladen und binären Fensterkontakt auswählen.
- Gemeinsame Wetter-Entität im Abschnitt „Wetter“ auswählen; für die Temperaturprüfung
  muss sie tägliche Vorhersagen liefern. Temperaturen werden in °C erwartet.
- `window_open_position` ersetzt die bisherige Kipp-Position; Standard ist 20 %.
  Ein weiter geöffneter Rollladen wird beim Öffnen des Fensters nicht abgesenkt.
- Alte Eingaben `tilted_position`, `treat_open_as_tilted`, `notification_timeout_tilted`
  sowie `mosquito_enabled`, `mosquito_after_time`, `mosquito_area` und `mosquito_exclude`
  aus bestehenden Instanzen entfernen. Kipp-Erkennung und Moskito-Modus entfallen.
  Bisherige Drei-Zustands-Sensoren müssen durch binäre Kontakte ersetzt werden.
- Für Sonnenschutz und Sonnenheizen jeweils einen eigenen Status-Helfer pro Rollladen
  auswählen. Morgen-/Abendzeiten benötigen reine Uhrzeit-Helfer ohne Datum.

## Abend und Nacht

Der standardmäßig deaktivierte Abendmodus prüft sowohl die gewählte feste Uhrzeit
als auch Sonnenuntergang plus Offset (Standard: eine Stunde danach). Negative Offsets
sind möglich. Ohne Uhrzeit-Helfer bleibt nur der Sonnenuntergangs-Trigger.
Beide Ereignisse prüfen erneut; es gibt keine tägliche Einmal-Sperre.
Der Rollladen fährt nur bei geschlossenem Fenster, ohne aktiven Nachtmodus und ohne
Sturm auf `evening_position`, und nur, wenn er aktuell weiter geöffnet ist.

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
Sonnenheizen verwendet weiterhin den optionalen Sensor oder die aktuelle Wettertemperatur.
Sonnenschutz hat Vorrang vor Sonnenheizen, auch wenn ein kalter Morgen mit heißer
Tagesvorhersage beide Temperaturbedingungen erfüllt.

Bei erzwungener Beschattung bestimmt `shading_min_position` den Mindestspalt, auch bei
offenem Fenster. Der Standard ist 25 %; ein eingestellter Wert von 0 % lässt vollständiges Schließen zu; für Terrassentüren
ist diese Option wegen Aussperr-Gefahr nicht empfohlen.

## Bekannte Grenzen

Die Automation läuft parallel, damit Fenster-Wartezeiten andere Funktionen nicht blockieren.
Unabhängige Bewegungsbefehle können sich zeitlich überschneiden; es gibt keine zentrale
Befehlswarteschlange. Dynamische Rückfahr-Szenen überleben keinen Home-Assistant-Neustart.
Die Beschattung kann nach einem Abend-Ereignis erneut starten, solange ihre Bedingungen
erfüllt sind und der Nachtmodus-Helfer aus ist; der Abendmodus ist kein dauerhafter Modus.
Ein fehlender heutiger Forecast wird nicht durch die morgige Vorhersage ersetzt.

Technische Referenzen: [Wetter](https://www.home-assistant.io/integrations/weather/),
[Script-Aktionen](https://www.home-assistant.io/docs/scripts/) und
[Dauer-Selektor](https://www.home-assistant.io/docs/blueprint/selectors/#duration-selector).
