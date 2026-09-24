"""Regression checks for the blueprint's selected decisions, without a live HA server.

Run: python -m unittest discover -s tests
Dependencies: pyyaml, jinja2. The harness models only the action types used here.
"""
import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

import yaml
from jinja2 import StrictUndefined
from jinja2.nativetypes import NativeEnvironment


class Loader(yaml.SafeLoader):
    pass


Loader.add_constructor('!input', lambda loader, node: ('input', loader.construct_scalar(node)))
BLUEPRINT = Path(__file__).resolve().parents[1] / 'automations/cover_automation.yaml'


class StopSequence(Exception):
    pass


class CoverLogicTests(unittest.TestCase):
    def setUp(self):
        self.doc = yaml.load(BLUEPRINT.read_text(), Loader=Loader)
        self.now = datetime(2026, 9, 24, 18, tzinfo=timezone.utc)
        self.states = {
            'binary_sensor.window': 'off',
            'input_boolean.shading': 'off',
            'input_boolean.heating': 'off',
            'input_boolean.night': 'off',
        }
        self.position = 60
        self.calls = []
        self.forecast = [{'datetime': '2026-09-24T12:00:00+00:00', 'temperature': 22, 'templow': 10}]
        self.env = NativeEnvironment(undefined=StrictUndefined)
        self.env.filters['slugify'] = lambda text: text.replace('.', '_')
        self.env.globals.update(
            states=lambda entity: self.states.get(entity, 'unknown'),
            is_state=lambda entity, state: self.states.get(entity) == state,
            state_attr=self.attr,
            now=lambda: self.now,
            today_at=lambda value: datetime.combine(self.now.date(), datetime.strptime(value, '%H:%M:%S').time(), timezone.utc),
            timedelta=timedelta,
            as_timestamp=self.timestamp,
            as_datetime=lambda value, default=None: datetime.fromisoformat(value) if value else default,
            as_local=lambda value: value,
        )
        self.ctx = {
            key: copy.deepcopy(value.get('default'))
            for section in self.doc['blueprint']['input'].values()
            for key, value in section['input'].items()
        }
        self.ctx.update(
            cover_entity='cover.test', cover='cover.test', window_sensor='binary_sensor.window',
            weather_entity='weather.test', shading_status_helper='input_boolean.shading',
            solar_heating_status_helper='input_boolean.heating', night_mode_boolean='input_boolean.night',
            evening_enabled=True,
            shading_enabled=True, solar_heating_enabled=True, pause_active=False,
            daily_forecast={}, today_forecast={}, daily_high=None, daily_low=None,
        )
        self.branches = {branch['conditions'][0]['id']: branch for branch in self.doc['actions'][1]['choose']}

    def attr(self, entity, name):
        if name == 'current_position':
            return self.position
        if name in ('has_date', 'has_time'):
            return True
        return {'elevation': 30, 'azimuth': 180, 'wind_speed': 0}.get(name)

    def timestamp(self, value, default=0):
        if isinstance(value, datetime):
            return value.timestamp()
        try:
            return datetime.fromisoformat(value).replace(tzinfo=timezone.utc).timestamp()
        except (ValueError, TypeError):
            return default

    def render(self, value):
        if isinstance(value, tuple):
            return self.ctx[value[1]]
        if isinstance(value, str) and ('{{' in value or '{%' in value):
            return self.env.from_string(value).render(**self.ctx)
        return value

    def conditions(self, items):
        for item in items:
            if isinstance(item, str):
                if not self.render(item):
                    return False
            elif item.get('condition') == 'trigger':
                if self.ctx.get('trigger_id') != item['id']:
                    return False
            else:
                self.fail(f'Unsupported condition: {item}')
        return True

    def run_steps(self, steps):
        try:
            for step in steps:
                if 'variables' in step:
                    for key, value in step['variables'].items():
                        self.ctx[key] = self.render(value)
                elif 'condition' in step:
                    if not self.render(step['condition']):
                        raise StopSequence
                elif 'if' in step:
                    self.run_steps(step.get('then' if self.conditions(step['if']) else 'else', []))
                elif 'choose' in step:
                    for branch in step['choose']:
                        if self.conditions(branch['conditions']):
                            self.run_steps(branch['sequence'])
                            break
                    else:
                        self.run_steps(step.get('default', []))
                elif 'sequence' in step:
                    self.run_steps(step['sequence'])
                elif 'stop' in step:
                    self.fail(step['stop'])
                elif 'action' in step:
                    action = step['action']
                    if action == 'persistent_notification.create':
                        self.calls.append(action)
                        continue
                    entity = self.render(step['target']['entity_id'])
                    if action == 'weather.get_forecasts':
                        self.calls.append(action)
                        self.ctx[step['response_variable']] = {entity: {'forecast': self.forecast}}
                    elif action == 'input_datetime.set_datetime':
                        stamp = self.render(step['data']['timestamp'])
                        self.states[entity] = datetime.fromtimestamp(float(stamp), timezone.utc).isoformat()
                    elif action.startswith('input_boolean.'):
                        self.states[entity] = 'on' if action.endswith('turn_on') else 'off'
                    elif action == 'cover.set_cover_position':
                        self.position = self.render(step['data']['position'])
                        self.calls.append((action, self.position))
                    else:
                        self.fail(f'Unsupported action: {action}')
                else:
                    self.fail(f'Unsupported step: {step}')
        except StopSequence:
            pass

    def test_active_shading_tracks_hysteresis_band(self):
        solar = self.branches['solar_tick']['sequence']
        shading = solar[-2]['then'][-1]['choose']
        self.ctx.update(sun_in_window=True, temp_available=True, outdoor_temp=22)
        self.states['input_boolean.shading'] = 'on'
        self.assertTrue(self.render(shading[0]['conditions'][0]))
        self.states['input_boolean.shading'] = 'off'
        self.assertFalse(self.render(shading[0]['conditions'][0]))
        self.states['input_boolean.shading'] = 'on'
        self.ctx['outdoor_temp'] = 21
        self.assertFalse(self.render(shading[0]['conditions'][0]))
        self.ctx.update(weather_bad_stable=False)
        self.assertTrue(self.render(shading[1]['conditions'][1]))

    def test_heating_uses_daily_high_and_one_forecast(self):
        self.ctx['shading_enabled'] = False
        self.position = 20
        self.run_steps(self.branches['solar_tick']['sequence'])
        self.assertEqual(self.position, 20)  # Daily high 22 is too warm for heating.
        self.assertEqual(self.calls.count('weather.get_forecasts'), 1)
        self.forecast[0]['temperature'] = 10
        self.run_steps(self.branches['solar_tick']['sequence'])
        self.assertEqual(self.position, 100)

    def test_heating_never_lowers_cover(self):
        self.ctx.update(shading_enabled=False, solar_heating_position=10)
        self.forecast[0]['temperature'] = 10
        self.position = 20
        self.run_steps(self.branches['solar_tick']['sequence'])
        self.assertEqual(self.position, 20)

    def test_evening_requires_no_status_helper(self):
        self.ctx['evening_position'] = 25
        self.run_steps(self.branches['evening_close']['sequence'])
        self.assertEqual(self.position, 25)
        self.assertNotIn('evening_until_helper', self.ctx)
        self.assertNotIn('evening_end_time', self.ctx)

    def test_evening_skips_open_window(self):
        self.states['binary_sensor.window'] = 'on'
        self.run_steps(self.branches['evening_close']['sequence'])
        self.assertEqual(self.position, 60)
        self.assertEqual(len(self.doc['actions']), 2)

    def test_evening_never_raises_cover(self):
        self.ctx['evening_position'] = 25
        self.position = 10
        self.run_steps(self.branches['evening_close']['sequence'])
        self.assertEqual(self.position, 10)

    def test_evening_respects_night_mode(self):
        self.ctx['evening_position'] = 25
        self.states['input_boolean.night'] = 'on'
        self.position = 60
        self.run_steps(self.branches['evening_close']['sequence'])
        self.assertEqual(self.position, 60)

    def test_night_and_morning_replace_evening_position(self):
        self.ctx['evening_position'] = 25
        self.run_steps(self.branches['evening_close']['sequence'])
        self.assertEqual(self.position, 25)
        self.states['input_boolean.night'] = 'on'
        self.run_steps(self.branches['night_close']['sequence'])
        self.assertEqual(self.position, 0)
        self.run_steps(self.branches['morning_open']['sequence'])
        self.assertEqual(self.position, 100)

    def test_missing_shading_helper_does_not_block_heating(self):
        self.ctx['shading_status_helper'] = []
        self.forecast[0]['temperature'] = 10
        self.position = 20
        self.run_steps(self.branches['solar_tick']['sequence'])
        self.assertEqual(self.position, 100)
        self.assertIn('persistent_notification.create', self.calls)

    def test_no_solar_forecast_outside_window(self):
        original_attr = self.attr
        self.env.globals['state_attr'] = lambda entity, name: -5 if name == 'elevation' else original_attr(entity, name)
        self.run_steps(self.branches['solar_tick']['sequence'])
        self.assertNotIn('weather.get_forecasts', self.calls)

    def test_missing_high_never_starts_heating(self):
        self.ctx['shading_enabled'] = False
        self.forecast = []
        self.position = 20
        self.run_steps(self.branches['solar_tick']['sequence'])
        self.assertEqual(self.position, 20)


if __name__ == '__main__':
    unittest.main()
