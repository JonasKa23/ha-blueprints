# Home Assistant Blueprints by simon42

A collection of Home Assistant automation blueprints.

## Automations

### Rollladensteuerung

**File:** `automations/cover_automation.yaml`

Pro Fenster/Rollladen wird eine eigene Automation mit einem binären Fensterkontakt erstellt.
Gemeinsame Helfer (Uhrzeit, Nachtmodus) wählen alle Instanzen identisch aus.

- Morgens öffnen und einstellbare Lüftungsposition mit Rückfahr-Logik
- Abendmodus zu fester Uhrzeit und Sonnenuntergang mit Offset
- Abend-/Nachtmodus anhand der vorhergesagten Tagestiefsttemperatur, mit eigenen Zielpositionen
- Sonnenschutz anhand des Sonnenstands und der vorhergesagten Tageshöchsttemperatur
- Sonnenheizen, Sturmschutz und Benachrichtigungen bei offenem Fenster

Mindestversion: Home Assistant 2024.10.

📖 **[Dokumentation und Umstellung](docs/cover_automation.md)**

[![Import Blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https://github.com/JonasKa23/ha-blueprints/blob/main/automations/cover_automation.yaml)

### Synchronisiere Datum+Uhrzeit zu Uhrzeit-Helfer

**File:** `automations/convert_datetime_helper_to_time_helper.yaml`

Synchronisiert die Uhrzeit eines `input_datetime`-Helfers (mit Datum+Uhrzeit) in einen reinen Uhrzeit-Helfer. Nützlich, wenn man nur die Zeitkomponente braucht.

[![Import Blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https://github.com/TheRealSimon42/ha-blueprints/blob/main/automations/convert_datetime_helper_to_time_helper.yaml)

## Entwicklung

### Agent-Skill für die Blueprint-Entwicklung

**Folder:** `skills/ha-blueprint-dev/`

Ein Agent Skill für Claude (Code), der die Arbeitsweise, Patterns und Learnings aus der
Entwicklung dieser Blueprints destilliert — damit Weiterentwicklungen auf demselben
Niveau passieren, unabhängig davon, wer (oder welches Modell) sie umsetzt. Enthält:

- `SKILL.md` — Workflow, Kern-Regeln und die typischen Fallen (1-basierter `repeat.index`,
  `!input` in Templates, Selector-Defaults, Blueprint-Cache, Race Conditions bei `mode: parallel`)
- `references/patterns.md` — erprobte Baupläne (Status-Helfer, Manual-Override-Erkennung,
  Snapshot/Restore, Beschattungs-Geometrie, Notification-Routing u.a.)
- `scripts/validate_blueprint.py` — Linter für Blueprint-YAML, findet die häufigsten
  Fehlerklassen vor dem Deploy:
  `python3 skills/ha-blueprint-dev/scripts/validate_blueprint.py <blueprint.yaml>`

Installation für Claude Code: Ordner nach `~/.claude/skills/ha-blueprint-dev/` kopieren.
Einige Angaben in `SKILL.md` (HA-Share-Pfad, MCP-Tools, Repo-Workflow) sind auf das Setup
des Repo-Autors zugeschnitten und müssen ggf. ans eigene Setup angepasst werden.
