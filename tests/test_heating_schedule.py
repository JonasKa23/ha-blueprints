"""Exercise the shipped Jinja templates, including HA-style native result parsing."""

import ast
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
import unittest
from zoneinfo import ZoneInfo

from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment
import yaml

ROOT = Path(__file__).resolve().parents[1]


class Input(str):
    pass


class Loader(yaml.SafeLoader):
    pass


Loader.add_constructor("!input", lambda loader, node: Input(loader.construct_scalar(node)))
BLUEPRINT = yaml.load((ROOT / "automations/smart_heating_schedule.yaml").read_text(), Loader=Loader)
INPUTS = {}
for section in BLUEPRINT["blueprint"]["input"].values():
    INPUTS.update(section["input"])


def substitute(value, inputs):
    if isinstance(value, Input):
        return inputs[str(value)]
    if isinstance(value, dict):
        return {key: substitute(item, inputs) for key, item in value.items()}
    if isinstance(value, list):
        return [substitute(item, inputs) for item in value]
    return value


class HeatingTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 10, 2, tzinfo=ZoneInfo("Europe/Berlin"))
        self.entities = {}
        self.inputs = {key: deepcopy(value["default"]) for key, value in INPUTS.items() if "default" in value}
        self.inputs["thermostat_entities"] = ["climate.test"]
        self.env = SandboxedEnvironment(undefined=StrictUndefined)
        self.env.globals.update(
            now=lambda: self.now,
            states=lambda entity: self.entities.get(entity, SimpleNamespace(state="unknown")).state,
            is_state=lambda entity, value: entity in self.entities and self.entities[entity].state == value,
            state_attr=lambda entity, attr: self.entities[entity].attributes.get(attr) if entity in self.entities else None,
            is_state_attr=lambda entity, attr, value: entity in self.entities and self.entities[entity].attributes.get(attr) == value,
            expand=lambda entity: [self.entities[entity]] if entity in self.entities else [],
        )

    def entity(self, name, state, age=3600, **attrs):
        self.entities[name] = SimpleNamespace(state=state, last_changed=self.now - timedelta(seconds=age), attributes=attrs)

    def render(self, template, context):
        text = self.env.from_string(template).render(context).strip()
        try:
            return ast.literal_eval(text)
        except (ValueError, SyntaxError):
            return text

    def evaluate(self):
        context = substitute(BLUEPRINT["variables"], self.inputs)
        for name, template in BLUEPRINT["actions"][1]["variables"].items():
            context[name] = self.render(template, context)
        context["repeat"] = {"item": self.inputs["thermostat_entities"][0]}
        for name, template in BLUEPRINT["actions"][-1]["repeat"]["sequence"][0]["variables"].items():
            context[name] = self.render(template, context)
        return context

    def test_equivalent_time_formats_normalize_before_comparison(self):
        self.now = self.now.replace(day=9, hour=6, minute=30)
        for time in ["6:30:00", "06:30", "06:30:00"]:
            self.inputs["slot1_time_weekday"] = time
            result = self.evaluate()["schedule_info"]
            self.assertIs(result["valid"], True)
            self.assertEqual(result["slot"], 1)
        self.inputs.update(slot1_time_weekday="06:30", slot2_time_weekday="06:30:00")
        self.assertIs(self.evaluate()["schedule_info"]["valid"], False)

    def test_previous_day_across_weekend_and_monday(self):
        for day, expected in [(10, "eco"), (11, "sleep"), (12, "away")]:
            with self.subTest(day=day):
                self.now = self.now.replace(day=day)
                self.inputs.update(slot4_preset_weekday="eco", slot4_preset_saturday="sleep", slot4_preset_sunday="away")
                result = self.evaluate()["schedule_info"]
                self.assertEqual(result["preset"], expected)
                self.assertIs(result["previous_day"], True)

    def test_exact_slot_boundaries_all_day_types(self):
        for date, kind in [(9, "weekday"), (10, "saturday"), (11, "sunday")]:
            for slot in range(1, 5):
                with self.subTest(day=kind, slot=slot):
                    hour, minute, second = map(int, self.inputs[f"slot{slot}_time_{kind}"].split(":"))
                    self.now = self.now.replace(day=date, hour=hour, minute=minute, second=second)
                    result = self.evaluate()["schedule_info"]
                    self.assertEqual(result["slot"], slot)
                    self.assertEqual(result["day"], kind)
                    self.assertIs(result["previous_day"], False)

    def test_optional_fifth_slot_and_previous_night(self):
        self.inputs.update(enable_slot5=True, slot5_preset_weekday="activity")
        self.assertEqual(self.evaluate()["desired_preset"], "activity")
        self.now = self.now.replace(day=9, hour=23, minute=45)
        self.assertEqual(self.evaluate()["schedule_info"]["slot"], 5)
        self.inputs["enable_slot5"] = False
        self.assertEqual(self.evaluate()["schedule_info"]["slot"], 4)

    def test_invalid_order_is_rejected_in_each_day_type(self):
        for kind in ["weekday", "saturday", "sunday"]:
            with self.subTest(kind=kind):
                key = f"slot2_time_{kind}"
                old = self.inputs[key]
                self.inputs[key] = self.inputs[f"slot1_time_{kind}"]
                self.assertIs(self.evaluate()["schedule_info"]["valid"], False)
                self.inputs[key] = old

    def test_unknown_presence_never_means_away(self):
        self.inputs.update(enable_presence_mode=True, presence_entity=["person.a", "input_boolean.b"])
        self.entity("person.a", "not_home")
        for state in ["unknown", "unavailable", "unexpected"]:
            self.entity("input_boolean.b", state)
            self.assertEqual(self.evaluate()["presence_status"], "uncertain")
        self.entity("input_boolean.b", "on")
        self.assertEqual(self.evaluate()["presence_status"], "home")
        self.entity("person.a", "unknown")
        self.assertEqual(self.evaluate()["presence_status"], "home")

    def test_all_away_requires_delay_for_every_entity(self):
        self.inputs.update(enable_presence_mode=True, presence_entity=["person.a", "person.b"])
        self.entity("person.a", "work")
        self.entity("person.b", "not_home", age=119)
        self.assertEqual(self.evaluate()["presence_status"], "pending")
        self.entity("person.b", "not_home", age=120)
        self.assertEqual(self.evaluate()["presence_status"], "away")
        self.assertEqual(self.evaluate()["desired_preset"], "away")

    def test_empty_and_scalar_presence(self):
        self.inputs["enable_presence_mode"] = True
        self.assertEqual(self.evaluate()["presence_status"], "uncertain")
        self.inputs["presence_entity"] = "person.a"
        self.entity("person.a", "home")
        self.assertEqual(self.evaluate()["presence_status"], "home")
        self.inputs["enable_presence_mode"] = False
        self.inputs["presence_entity"] = []
        self.assertEqual(self.evaluate()["presence_status"], "home")

    def test_multiple_pause_helpers_and_unknown_states(self):
        self.inputs.update(enable_pause_switch=True, pause_switch=["input_boolean.a", "input_boolean.b"])
        self.entity("input_boolean.a", "off")
        for state in ["on", "unknown", "unavailable"]:
            self.entity("input_boolean.b", state)
            self.assertIs(self.evaluate()["pause_blocked"], True)
        self.entity("input_boolean.b", "off")
        self.assertIs(self.evaluate()["pause_blocked"], False)
        self.inputs["pause_switch"] = []
        self.assertIs(self.evaluate()["pause_blocked"], True)

    def test_manual_timer_restore_and_expired_while_offline(self):
        self.inputs.update(enable_manual_override=True, manual_override_timer="timer.test", manual_override_button="input_button.test")
        for state in ["active", "paused", "unknown", "unavailable"]:
            self.entity("timer.test", state)
            self.assertIs(self.evaluate()["pause_blocked"], True)
        self.entity("timer.test", "idle")
        self.assertIs(self.evaluate()["pause_blocked"], False)
        self.inputs["manual_override_timer"] = []
        self.assertIs(self.evaluate()["pause_blocked"], True)

    def test_thermostat_filter_skips_unchanged_offline_off_and_unsupported(self):
        template = BLUEPRINT["actions"][-1]["repeat"]["sequence"][1]["if"][0]["value_template"]
        context = {**self.evaluate(), "heating_entity": "climate.test", "desired_preset": "comfort"}
        for state, preset, modes, expected in [
            ("heat", "eco", ["eco", "comfort"], True),
            ("heat", "comfort", ["comfort"], False),
            ("off", "eco", ["comfort"], False),
            ("unavailable", "eco", ["comfort"], False),
            ("heat", "eco", ["eco"], False),
        ]:
            self.entity("climate.test", state, preset_mode=preset, preset_modes=modes)
            self.assertIs(self.render(template, context), expected)

    def run_schedule(self, after_service):
        """Small executor for the shipped branches; inject changes during service calls."""
        context = substitute(BLUEPRINT["variables"], self.inputs)
        calls = []

        def condition(value):
            if value["condition"] == "trigger":
                return False  # A regular schedule/reconciliation run.
            return bool(self.render(value["value_template"], context))

        def execute(sequence):
            for step in sequence:
                if "variables" in step:
                    for name, template in step["variables"].items():
                        context[name] = self.render(template, context)
                elif "repeat" in step:
                    for item in self.render(step["repeat"]["for_each"], context):
                        context["repeat"] = {"item": item}
                        execute(step["repeat"]["sequence"])
                elif "if" in step:
                    if all(condition(value) for value in step["if"]):
                        execute(step["then"])
                elif "condition" in step:
                    if not condition(step):
                        return
                elif "action" in step:
                    if step["action"] == "climate.set_preset_mode":
                        entity = self.render(step["target"]["entity_id"], context)
                        preset = self.render(step["data"]["preset_mode"], context)
                        calls.append((entity, preset))
                        self.entities[entity].attributes["preset_mode"] = preset
                        after_service()
                elif "sequence" in step:
                    execute(step["sequence"])
                else:
                    self.fail(f"Unexpected action in schedule executor: {step}")

        execute(substitute(BLUEPRINT["actions"], self.inputs))
        return calls

    def test_state_changes_during_first_service_protect_second_thermostat(self):
        self.inputs.update(thermostat_entities=["climate.a", "climate.b"],
                           enable_pause_switch=True, pause_switch=["input_boolean.pause"],
                           enable_presence_mode=True, presence_entity=["person.a"])
        for name, state in [("input_boolean.pause", "on"), ("person.a", "unknown")]:
            self.entity("input_boolean.pause", "off")
            self.entity("person.a", "home")
            for entity in self.inputs["thermostat_entities"]:
                self.entity(entity, "heat", preset_mode="eco", preset_modes=["eco", "sleep"])
            calls = self.run_schedule(lambda: self.entity(name, state))
            self.assertEqual(calls, [("climate.a", "sleep")])

    def test_slot_boundary_during_service_is_recomputed_for_second_thermostat(self):
        self.now = self.now.replace(day=9, hour=6, minute=29, second=59)
        self.inputs["thermostat_entities"] = ["climate.a", "climate.b"]
        for entity in self.inputs["thermostat_entities"]:
            self.entity(entity, "heat", preset_mode="eco", preset_modes=["eco", "sleep", "comfort"])
        def advance_clock():
            self.now += timedelta(seconds=2)
        self.assertEqual(self.run_schedule(advance_clock), [("climate.a", "sleep"), ("climate.b", "comfort")])

    def test_schedule_across_dst_folds(self):
        self.inputs.update(slot4_preset_saturday="eco", slot4_preset_sunday="away")
        for fold in [0, 1]:
            self.now = datetime(2026, 10, 25, 2, 30, tzinfo=ZoneInfo("Europe/Berlin"), fold=fold)
            self.assertEqual(self.evaluate()["desired_preset"], "eco")

    def test_examples_use_known_inputs_and_disable_initial_execution(self):
        files = list((ROOT / "examples/heating").glob("*.yaml"))
        self.assertEqual(len(files), 6)
        for path in files:
            example = yaml.safe_load(path.read_text())
            self.assertIs(example["initial_state"], False)
            self.assertFalse(set(example["use_blueprint"]["input"]) - set(INPUTS))

    def load_room(self, room):
        example = yaml.safe_load((ROOT / f"examples/heating/{room}.yaml").read_text())
        self.inputs.update(example["use_blueprint"]["input"])
        for entity in self.inputs["presence_entity"]:
            self.entity(entity, "home")

    def test_room_plans_match_user_schedule_at_every_boundary(self):
        # Independent acceptance table from the user's plan; includes the desired
        # midnight state, not the implementation's redundant fourth slot.
        plans = {
            "wohnzimmer": (
                [(0, "sleep"), (360, "home"), (1320, "sleep")],
                [(0, "sleep"), (420, "home"), (1350, "sleep")],
            ),
            "arbeitszimmer": (
                [(0, "sleep"), (360, "home"), (1290, "sleep")],
                [(0, "sleep"), (480, "home"), (1290, "sleep")],
            ),
            "bad": (
                [(0, "sleep"), (335, "comfort"), (405, "eco"), (1080, "home"), (1320, "sleep")],
                [(0, "sleep"), (540, "home"), (1350, "sleep")],
            ),
            "schlafzimmer": (
                [(0, "sleep"), (340, "comfort"), (430, "eco"), (1200, "sleep")],
                [(0, "eco"), (390, "sleep"), (1320, "eco")],
            ),
            "kueche": (
                [(0, "eco"), (360, "home"), (1260, "eco")],
                [(0, "eco"), (420, "home"), (1260, "eco")],
            ),
            "klo": (
                [(0, "eco"), (390, "home"), (1320, "eco")],
                [(0, "eco"), (390, "home"), (1320, "eco")],
            ),
        }
        for room, day_plans in plans.items():
            self.load_room(room)
            for date in range(5, 12):  # Monday through Sunday, October 2026.
                midnight = datetime(2026, 10, date, tzinfo=ZoneInfo("Europe/Berlin"))
                plan = day_plans[int(midnight.weekday() >= 5)]
                moments = {0, 12 * 3600, 86339, 86340, 86399}
                for minute, _ in plan:
                    moments.update(minute * 60 + offset for offset in [-1, 0, 1])
                for second in sorted(moments):
                    self.now = midnight + timedelta(seconds=second)
                    applicable = day_plans[int(self.now.weekday() >= 5)]
                    current_minute = self.now.hour * 60 + self.now.minute
                    expected = [preset for minute, preset in applicable if minute <= current_minute][-1]
                    with self.subTest(room=room, time=self.now.isoformat()):
                        result = self.evaluate()
                        self.assertIs(result["schedule_info"]["valid"], True)
                        self.assertEqual(result["desired_preset"], expected)

    def test_bedroom_midnight_changes_have_exact_triggers_and_recover(self):
        self.load_room("schlafzimmer")
        for day in ["weekday", "saturday", "sunday"]:
            self.assertEqual(self.inputs[f"slot1_time_{day}"], "00:00:00")
        triggers = substitute(BLUEPRINT["triggers"], self.inputs)
        self.assertTrue(any(t["trigger"] == "time" and t["at"] == "00:00:00" for t in triggers))
        for timestamp, expected in [
            ("2026-10-09T23:59:59+02:00", "sleep"),
            ("2026-10-10T00:00:00+02:00", "eco"),
            ("2026-10-10T02:00:00+02:00", "eco"),
            ("2026-10-11T00:00:00+02:00", "eco"),
            ("2026-10-11T23:59:59+02:00", "eco"),
            ("2026-10-12T00:00:00+02:00", "sleep"),
            ("2026-10-12T02:00:00+02:00", "sleep"),
        ]:
            with self.subTest(timestamp=timestamp):
                self.now = datetime.fromisoformat(timestamp)
                self.assertEqual(self.evaluate()["desired_preset"], expected)

    def test_room_presence_changes_apply_without_confirmation_delay(self):
        for room in ["wohnzimmer", "arbeitszimmer", "bad", "schlafzimmer", "kueche", "klo"]:
            self.load_room(room)
            self.assertEqual(self.inputs["away_delay"], 0)
            for entity in self.inputs["presence_entity"]:
                self.entity(entity, "not_home", age=0)
            self.assertEqual(self.evaluate()["desired_preset"], "away")
            first = self.inputs["presence_entity"][0]
            self.entity(first, "home", age=0)
            result = self.evaluate()
            self.assertEqual(result["presence_status"], "home")
            self.assertEqual(result["desired_preset"], result["schedule_info"]["preset"])
            self.entity(first, "unknown", age=0)
            self.assertEqual(self.evaluate()["presence_status"], "uncertain")


if __name__ == "__main__":
    unittest.main()
