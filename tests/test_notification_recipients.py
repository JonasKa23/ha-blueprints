"""Check recipient selection using the templates from both notification blueprints."""
import ast
from pathlib import Path
import unittest

import yaml
from jinja2 import StrictUndefined
from jinja2.nativetypes import NativeEnvironment


class Loader(yaml.SafeLoader):
    pass


Loader.add_constructor('!input', lambda loader, node: loader.construct_scalar(node))
ROOT = Path(__file__).resolve().parents[1]
BLUEPRINTS = ('cover_automation.yaml', 'fenster-offen-benachrichtigung.yaml')


class NotificationRecipientsTests(unittest.TestCase):
    def recipients(self, filename, states, *, enabled=True, devices=None,
                   mappings=None, legacy=None, trigger='window_open_long'):
        doc = yaml.load((ROOT / 'automations' / filename).read_text(), Loader=Loader)
        env = NativeEnvironment(undefined=StrictUndefined)
        env.filters['slugify'] = lambda value: value.lower().replace(' ', '_')
        env.globals.update(
            device_attr=lambda device, attr: device,
            is_state=lambda entity, state: states.get(entity) == state,
        )
        ctx = dict(
            notification_device=devices if devices is not None else ['anna', 'ben'],
            notification_device_persons=mappings if mappings is not None else [
                {'person': 'person.ben', 'device': 'ben'},
                {'person': 'person.anna', 'device': 'anna'},
            ],
            notification_only_when_home=enabled,
            notification_person=legacy if legacy is not None else [],
            sleep_mode_boolean=[],
        )
        def render(template):
            value = env.from_string(template).render(ctx)
            # HA strips rendered whitespace before parsing native template values.
            if isinstance(value, str):
                try:
                    return ast.literal_eval(value.strip())
                except (ValueError, SyntaxError):
                    return value.strip()
            return value

        ctx['device_name_map'] = render(doc['variables']['device_name_map'])
        branches = next(step['choose'] for step in doc['actions'] if 'choose' in step)
        branch = next(b for b in branches if b['conditions'][0].get('id') == trigger)
        for condition in branch['conditions'][1:]:
            if isinstance(condition, str) and not render(condition):
                return []
        repeat = next(step['repeat'] for step in branch['sequence'] if 'repeat' in step)
        result = []
        for item in render(repeat['for_each']):
            ctx['repeat'] = {'item': item}
            for step in repeat['sequence']:
                if 'condition' in step:
                    if not render(step['value_template']):
                        break
                elif 'action' in step:
                    result.append(render(step['action']))
        return result

    def test_presence_is_checked_for_each_recipient(self):
        for filename in BLUEPRINTS:
            for anna in ('home', 'not_home', 'unknown', 'unavailable'):
                for ben in ('home', 'work', 'unknown', 'unavailable'):
                    with self.subTest(blueprint=filename, anna=anna, ben=ben):
                        expected = []
                        if anna == 'home':
                            expected.append('notify.mobile_app_anna')
                        if ben == 'home':
                            expected.append('notify.mobile_app_ben')
                        self.assertEqual(self.recipients(filename, {
                            'person.anna': anna, 'person.ben': ben,
                        }), expected)

    def test_unassigned_and_ambiguous_devices_are_skipped(self):
        for filename in BLUEPRINTS:
            for mappings in ([], [{'device': 'anna'}], [
                {'device': 'anna', 'person': 'person.anna'},
                {'device': 'anna', 'person': 'person.ben'},
            ]):
                with self.subTest(blueprint=filename, mappings=mappings):
                    self.assertEqual(self.recipients(filename, {'person.anna': 'home'},
                                                    mappings=mappings, legacy='person.anna'), [])

    def test_one_person_can_receive_on_multiple_devices(self):
        for filename in BLUEPRINTS:
            self.assertEqual(self.recipients(filename, {'person.anna': 'home'}, mappings=[
                {'device': 'anna', 'person': 'person.anna'},
                {'device': 'ben', 'person': 'person.anna'},
            ]), ['notify.mobile_app_anna', 'notify.mobile_app_ben'])

    def test_disabled_filter_and_clearing_include_absent_people(self):
        for filename in BLUEPRINTS:
            for options in ({'enabled': False}, {'trigger': 'window_closed'}):
                with self.subTest(blueprint=filename, options=options):
                    self.assertEqual(self.recipients(filename, {}, **options),
                                     ['notify.mobile_app_anna', 'notify.mobile_app_ben'])

    def test_single_device_legacy_selection_and_explicit_override(self):
        for filename in BLUEPRINTS:
            options = dict(devices=['anna'], legacy='person.anna')
            self.assertEqual(self.recipients(filename, {'person.anna': 'home'},
                                            mappings=[], **options), ['notify.mobile_app_anna'])
            self.assertEqual(self.recipients(filename, {'person.anna': 'home'}, mappings=[
                {'device': 'anna', 'person': 'person.ben'},
            ], **options), [])
