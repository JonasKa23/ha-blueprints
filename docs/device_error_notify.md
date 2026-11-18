# Better Thermostat: Benachrichtigungen

Der Blueprint [device_error_notify.yaml](../automations/device_error_notify.yaml)
meldet Gerätefehler und optional das Erreichen der Zieltemperatur. Die Nachrichten
enthalten den Raum, der dem Better-Thermostat-Gerät zugewiesen ist.

## Updates vom Original

Der Workflow
[update-device-error-upstream.yml](../.github/workflows/update-device-error-upstream.yml)
prüft montags um **07:38 UTC** (08:38 MEZ / 09:38 MESZ) sowie bei manuellem Start
über **Actions → Update Better Thermostat notification blueprint → Run workflow**
die Originaldatei aus `KartoffelToby/better_thermostat`.

Bei geändertem Dateiinhalt führt er einen Drei-Wege-Merge durch: gespeichertes
Original, unsere aktuelle Version und neues Original. Unabhängige Änderungen
werden zusammengeführt; lokale Anpassungen wie Raumangabe und eigene `source_url`
bleiben dabei erhalten. Der gespeicherte Originalstand wird über seinen Git-Hash
geprüft, und Downloads erfolgen von einer festen Commit-ID.

- **Erfolgreicher Merge:** Nach YAML-, Blueprint- und Regressionstests wird ein
  Entwurfs-Pull-Request auf `automation/device-error-upstream` erstellt oder
  aktualisiert. Er enthält den Blueprint sowie den neuen Originalstand.
- **Konflikt:** Der Workflow schlägt fehl. Blueprint und Vergleichsbasis bleiben
  unverändert. Im Workflow-Artefakt `device-error-upstream-review` stehen die
  Quelllinks und ein Merge-Vorschlag mit Konfliktmarkierungen für die manuelle
  Auflösung. Konfliktmarkierungen niemals in Home Assistant importieren.
- **Keine Dateiänderung:** Es entsteht kein Pull Request. Andere Änderungen am
  Ursprungsrepository lösen kein Blueprint-Update aus.

Der Bot-Branch ist für generierte Updates reserviert; manuelle Änderungen dort
können beim nächsten Lauf ersetzt werden. Ein geschlossener, nicht gemergter PR
ist keine dauerhafte Ablehnung: Solange die Vergleichsbasis unverändert ist,
kann derselbe Stand erneut angeboten werden.

Vor dem Merge insbesondere Input-Kompatibilität, Raumangabe und
Benachrichtigungsverhalten prüfen. Ein textuell konfliktfreier Merge garantiert
keine unveränderte Semantik. Der Workflow führt keinen automatischen Merge und
keine Änderung an einer Home-Assistant-Installation durch.

## Aktivierung auf GitHub

1. Workflow, Script, Tests und Dateien unter `upstream/` auf dem Standardbranch
   veröffentlichen. Erst dann läuft die geplante Prüfung.
2. Unter **Settings → Actions → General → Workflow permissions** die Option
   **Allow GitHub Actions to create and approve pull requests** aktivieren.
   Der Workflow benötigt `contents: write` und `pull-requests: write`.
3. In einem Fork gegebenenfalls geplante Actions aktivieren. GitHub kann
   geplante Läufe verzögern oder bei Inaktivität deaktivieren.
4. Den Workflow einmal manuell ausführen. Bei unverändertem Original ist
   `unchanged` das erwartete Ergebnis.

Bei automatisch erstellten PRs kann GitHub eine Freigabe **Approve workflows to
run** für die PR-Checks verlangen. Die oben genannten Prüfungen laufen bereits
im Update-Workflow vor der PR-Erstellung.
Siehe [GitHub: Workflow-Auslösung](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow)
und [Create Pull Request: Berechtigungen](https://github.com/peter-evans/create-pull-request#workflow-permissions).

Nach Prüfung und Merge den Blueprint in Home Assistant über seine bestehende
Quelle erneut importieren und die Automationen neu laden. Die Quelle bleibt
unsere Datei unter `JonasKa23/ha-blueprints`, damit lokale Erweiterungen auch
bei späteren Re-Imports erhalten bleiben.

## Lokale Prüfung und Übernahme

Voraussetzungen: Python 3 und Git; für die Validierung zusätzlich `pyyaml`,
`jinja2` und `yamllint`. Optional erhöht `GH_TOKEN` das GitHub-API-Limit.

```sh
# Nur vergleichen, keine Repository-Dateien ändern:
python3 scripts/update_device_error_upstream.py --report-dir /tmp/device-error-review

# In einem eigenen Branch konfliktfreie Änderungen übernehmen:
python3 scripts/update_device_error_upstream.py --apply --report-dir /tmp/device-error-review
yamllint automations/device_error_notify.yaml
python3 skills/ha-blueprint-dev/scripts/validate_blueprint.py automations/device_error_notify.yaml
python3 -m unittest discover -s tests
git diff --check
```

Exit-Code `2` bedeutet Merge-Konflikt; Download-, Integritäts- und andere Fehler
brechen ebenfalls mit einem Fehlerstatus ab. Bei Konflikten den Kandidaten
manuell auflösen und validieren; anschließend den exakten neuen Originalinhalt
als `upstream/device_error_notify.original.txt` speichern und `reviewed_commit`
sowie `reviewed_blob` aus `summary.json` gemeinsam im Manifest aktualisieren.
Alle drei Dateien gehören in denselben geprüften Commit.

Die Ausgangsbasis ist das am 18.11.2026 abgerufene Original, Commit
`aed2036b3c6d90b4e1e6ea774f0f47852a05d25d`. Sie ist unverändert als `.txt`
gespeichert, damit Formatter ihren Git-Hash nicht verändern. Die aktuelle
Automation behält ihre bisherige Logik. Der Lizenztext des Originals liegt unter
[LICENSES/Better-Thermostat-AGPL-3.0.txt](../LICENSES/Better-Thermostat-AGPL-3.0.txt).
