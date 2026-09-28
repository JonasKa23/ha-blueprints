"""Regression checks for the blueprint's selected decisions, without a live HA server.

Run: python -m unittest discover -s tests
Dependencies: pyyaml, jinja2. The harness models only the action types used here.
"""
import ast
import copy
import math
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
            'input_boolean.night': 'off',
        }
        self.position = 60
        self.after_forecast = None
        self.calls = []
        self.forecast = [{'datetime': '2026-09-24T12:00:00+00:00', 'temperature': 22, 'templow': 10}]
        self.env = NativeEnvironment(undefined=StrictUndefined)
        self.env.filters['slugify'] = lambda text: text.replace('.', '_')
        self.env.globals.update(
            states=lambda entity: self.states.get(entity, 'unknown'),
            is_state=lambda entity, state: self.states.get(entity) == state,
            expand=lambda entities: [
                {'entity_id': entity, 'state': self.states[entity]}
                for entity in entities if entity in self.states
            ],
            state_attr=self.attr,
            now=lambda: self.now,
            today_at=lambda value: datetime.combine(self.now.date(), datetime.strptime(value, '%H:%M:%S').time(), timezone.utc),
            timedelta=timedelta,
            as_timestamp=self.timestamp,
            as_datetime=lambda value, default=None: datetime.fromisoformat(value) if value else default,
            as_local=lambda value: value,
            tan=math.tan, cos=math.cos, pi=math.pi,
        )
        self.ctx = {
            key: copy.deepcopy(value.get('default'))
            for section in self.doc['blueprint']['input'].values()
            for key, value in section['input'].items()
        }
        self.ctx.update(
            cover_entity='cover.test', cover='cover.test', window_sensor='binary_sensor.window',
            weather_entity='weather.test', shading_status_helper='input_boolean.shading',
            night_mode_boolean='input_boolean.night',
            evening_enabled=True,
            shading_enabled=True, pause_active=False,
            daily_forecast={}, today_forecast={}, daily_high=None, daily_low=None,
            night_temp_ok=True, evening_temp_ok=True,
        )
        self.branches = {branch['conditions'][0]['id']: branch for branch in self.doc['actions'][1]['choose']}

    def attr(self, entity, name):
        if name == 'current_position':
            return self.position
        if name in ('has_date', 'has_time'):
            return True
        return {'elevation': 30, 'azimuth': 180}.get(name)

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
            rendered = self.env.from_string(value).render(**self.ctx)
            # Home Assistant strips whitespace before converting template results.
            if isinstance(rendered, str):
                try:
                    return ast.literal_eval(rendered.strip())
                except (ValueError, SyntaxError):
                    return rendered.strip()
            return rendered
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
                elif 'wait_for_trigger' in step:
                    # Leave the run suspended; these tests inspect the initial window reaction.
                    return
                elif 'stop' in step:
                    self.fail(step['stop'])
                elif 'action' in step:
                    action = step['action']
                    if action == 'persistent_notification.create':
                        self.calls.append(action)
                        continue
                    entity = self.render(step.get('target', {}).get('entity_id'))
                    if action == 'weather.get_forecasts':
                        self.calls.append(action)
                        self.ctx[step['response_variable']] = {entity: {'forecast': self.forecast}}
                        if self.after_forecast:
                            self.after_forecast()
                    elif action == 'scene.create':
                        self.calls.append(action)
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
        shading = solar[-1]['then'][-1]['choose']
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

    def test_no_solar_forecast_outside_window(self):
        original_attr = self.attr
        self.env.globals['state_attr'] = lambda entity, name: -5 if name == 'elevation' else original_attr(entity, name)
        self.run_steps(self.branches['solar_tick']['sequence'])
        self.assertNotIn('weather.get_forecasts', self.calls)

    def run_trigger(self, trigger_id, **trigger):
        self.ctx.update(trigger_id=trigger_id, trigger=dict(id=trigger_id, **trigger))
        self.run_steps(self.doc['actions'])

    def set_global_permission(self, state):
        entity = 'input_boolean.shading_global'
        previous = self.states.get(entity, 'unknown')
        self.ctx['shading_control_helper'] = entity
        self.states[entity] = state
        for trigger in self.doc['triggers']:
            if trigger.get('trigger') != 'state':
                continue
            if trigger.get('entity_id') != ('input', 'shading_control_helper'):
                continue
            targets = trigger['to'] if isinstance(trigger['to'], list) else [trigger['to']]
            if state in targets and state != previous and self.render(trigger.get('enabled', True)):
                self.run_trigger(trigger['id'], entity_id=entity,
                                 from_state={'state': previous}, to_state={'state': state})

    def test_global_on_immediately_starts_shading(self):
        self.forecast[0]['temperature'] = 28
        self.set_global_permission('on')
        self.assertLess(self.position, 60)
        self.assertEqual(self.states['input_boolean.shading'], 'on')
        self.assertEqual(self.calls.count('weather.get_forecasts'), 1)

    def test_pause_blocks_only_when_all_selected_helpers_are_on(self):
        cases = [([], {}, False),
                 ('input_boolean.pause', {'input_boolean.pause': 'on'}, True),
                 ('input_boolean.pause', {'input_boolean.pause': 'off'}, False),
                 (['input_boolean.pause'], {'input_boolean.pause': 'on'}, True),
                 (['input_boolean.pause', 'input_boolean.pause_other'],
                  {'input_boolean.pause': 'on', 'input_boolean.pause_other': 'on'}, True),
                 (['input_boolean.pause', 'input_boolean.pause_other'],
                  {'input_boolean.pause': 'on', 'input_boolean.pause_other': 'off'}, False)]
        for helpers, states, paused in cases:
            with self.subTest(helpers=helpers, states=states):
                self.position = 60
                self.ctx.update(pause_boolean=helpers, pause_mode='off_pauses')
                self.states.update(states)
                self.ctx['pause_active'] = self.render(self.doc['variables']['pause_active'])
                self.assertEqual(self.ctx['pause_active'], paused)
                self.run_trigger('morning_open')
                self.assertEqual(self.position, 60 if paused else 100)

    def test_pause_ending_catches_up_night_only_after_an_actual_pause(self):
        self.ctx['pause_boolean'] = ['input_boolean.pause', 'input_boolean.pause_other']
        self.states.update({'input_boolean.night': 'on', 'input_boolean.pause': 'off'})
        for other in ('on', 'off'):
            with self.subTest(other=other):
                self.position = 60
                self.states['input_boolean.pause_other'] = other
                self.ctx['pause_active'] = self.render(self.doc['variables']['pause_active'])
                self.run_trigger('pause_ended', entity_id='input_boolean.pause',
                                 from_state={'state': 'on'}, to_state={'state': 'off'})
                self.assertEqual(self.position, 0 if other == 'on' else 60)

    def test_pause_is_rechecked_after_window_wait(self):
        steps = self.branches['window_change']['sequence']
        after_wait = next(i for i, step in enumerate(steps) if 'wait_for_trigger' in step) + 1
        self.ctx.update(pause_boolean=['input_boolean.pause'], wait={'trigger': {}},
                        reclose_scene='scene.reclose_cover_test')
        self.states['input_boolean.night'] = 'on'
        for state in ('on', 'off'):
            with self.subTest(state=state):
                self.position = 35
                self.states['input_boolean.pause'] = state
                self.ctx['pause_active'] = state == 'off'  # Opposite at run start.
                self.run_steps(steps[after_wait:])
                self.assertEqual(self.position, 35 if state == 'on' else 0)

    def test_global_off_clears_status_without_moving_even_when_paused(self):
        self.ctx['pause_active'] = True
        self.states['input_boolean.shading'] = 'on'
        self.set_global_permission('off')
        self.assertEqual(self.position, 60)
        self.assertEqual(self.states['input_boolean.shading'], 'off')
        self.assertEqual(self.calls, [])

    def test_global_off_blocks_start_tracking_and_end(self):
        for active, temperature in [('off', 28), ('on', 28), ('on', 10)]:
            with self.subTest(active=active, temperature=temperature):
                self.ctx['shading_control_helper'] = 'input_boolean.shading_global'
                self.states['input_boolean.shading_global'] = 'off'
                self.states['input_boolean.shading'] = active
                self.forecast[0]['temperature'] = temperature
                self.run_trigger('solar_tick')
                self.assertEqual(self.position, 60)
                self.assertEqual(self.states['input_boolean.shading'], 'off')
                self.assertEqual(self.calls, [])

    def test_missing_global_helper_preserves_shading(self):
        self.forecast[0]['temperature'] = 28
        self.run_trigger('solar_tick')
        self.assertLess(self.position, 60)
        self.assertEqual(self.states['input_boolean.shading'], 'on')

    def test_unavailable_global_helper_blocks_shading(self):
        for state in ('unknown', 'unavailable'):
            with self.subTest(state=state):
                self.states['input_boolean.shading'] = 'on'
                self.set_global_permission(state)
                self.run_trigger('solar_tick')
                self.assertEqual(self.position, 60)
                self.assertEqual(self.states['input_boolean.shading'], 'off')
                self.assertEqual(self.calls, [])

    def test_global_on_does_not_override_local_disable_or_pause(self):
        for settings in ({'shading_enabled': False}, {'pause_active': True}):
            with self.subTest(settings=settings):
                self.ctx.update(shading_enabled=True, pause_active=False)
                self.ctx.update(settings)
                self.states['input_boolean.shading_global'] = 'off'
                self.forecast[0]['temperature'] = 28
                self.set_global_permission('on')
                self.assertEqual(self.position, 60)
                self.assertEqual(self.calls, [])

    def test_global_on_respects_temperature_night_and_window(self):
        cases = [({}, 10),
                 ({'input_boolean.night': 'on'}, 28),
                 ({'binary_sensor.window': 'on'}, 28)]
        for states, temperature in cases:
            with self.subTest(states=states, temperature=temperature):
                self.states.update({'input_boolean.shading_global': 'off',
                                    'input_boolean.night': 'off', 'binary_sensor.window': 'off'})
                self.states.update(states)
                self.forecast[0]['temperature'] = temperature
                self.set_global_permission('on')
                self.assertEqual(self.position, 60)
                self.assertEqual(self.states['input_boolean.shading'], 'off')

    def test_global_off_during_forecast_prevents_shading(self):
        self.forecast[0]['temperature'] = 28
        self.after_forecast = lambda: self.states.update({'input_boolean.shading_global': 'off'})
        self.set_global_permission('on')
        self.assertEqual(self.position, 60)
        self.assertEqual(self.states['input_boolean.shading'], 'off')
        self.assertFalse(any(isinstance(call, tuple) for call in self.calls))

    def test_global_off_keeps_evening_night_and_morning_working(self):
        self.set_global_permission('off')
        self.ctx['evening_position'] = 15
        self.run_trigger('evening_close')
        self.assertEqual(self.position, 15)
        self.states['input_boolean.night'] = 'on'
        self.run_trigger('night_close')
        self.assertEqual(self.position, 0)
        self.run_trigger('morning_open')
        self.assertEqual(self.position, 100)

    def test_global_off_does_not_block_window_ventilation_with_stale_status(self):
        self.set_global_permission('off')
        self.ctx['force_shading'] = True
        self.position = 10
        self.states['input_boolean.shading'] = 'on'
        self.states['binary_sensor.window'] = 'on'
        self.run_trigger('window_change', from_state={'state': 'off'})
        self.assertEqual(self.position, self.ctx['window_open_position'])

    def test_missing_temperature_does_not_start_shading(self):
        self.forecast = []
        self.run_trigger('solar_tick')
        self.assertEqual(self.position, 60)
        self.assertEqual(self.states['input_boolean.shading'], 'off')

    def test_no_weather_entity_cannot_fall_back_to_removed_sensor(self):
        self.ctx.update(weather_entity=[], shading_temp_sensor='sensor.old_daily_high')
        self.states['sensor.old_daily_high'] = '30'
        self.run_trigger('solar_tick')
        self.assertEqual(self.position, 60)
        self.assertEqual(self.states['input_boolean.shading'], 'off')
        self.assertNotIn('weather.get_forecasts', self.calls)

    def test_missing_status_helper_reports_problem_without_moving(self):
        self.ctx['shading_status_helper'] = []
        self.forecast[0]['temperature'] = 28
        self.run_trigger('solar_tick')
        self.assertEqual(self.position, 60)
        self.assertIn('persistent_notification.create', self.calls)

    def test_removed_heating_does_not_reopen_cover_on_cold_day(self):
        self.position = 20
        self.forecast[0]['temperature'] = 10
        self.run_trigger('solar_tick')
        self.assertEqual(self.position, 20)
        self.assertFalse(any(key.startswith('solar_heating_') for key in self.ctx))


if __name__ == '__main__':
    unittest.main()
