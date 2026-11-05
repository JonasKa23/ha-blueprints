"""Check visibility validation against malformed and supported blueprint inputs."""
import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'blueprint_validator', ROOT / 'skills/ha-blueprint-dev/scripts/validate_blueprint.py'
)
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class VisibilityValidationTests(unittest.TestCase):
    def check(self, visibility, version='2026.11.0'):
        document = {
            'blueprint': {
                'name': 'Visibility fixture',
                'domain': 'automation',
                'source_url': 'https://example.com/blueprint.yaml',
                'homeassistant': {'min_version': version},
                'input': {
                    'enabled': {'default': False, 'selector': {'boolean': {}}},
                    'helper': {'default': [], 'selector': {'entity': {}}},
                    'details': {
                        'visible': visibility,
                        'input': {'position': {'default': 50, 'selector': {'number': {}}}},
                    },
                },
            },
            'actions': [],
        }
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'blueprint.yaml'
            path.write_text(yaml.safe_dump(document))
            with contextlib.redirect_stdout(output):
                result = VALIDATOR.main(path)
        return result, output.getvalue()

    def test_valid_section_visibility_with_multiple_conditions(self):
        result, output = self.check([
            {'field': 'enabled', 'value': True},
            {'field': 'helper', 'operator': 'not_eq', 'value': []},
        ])
        self.assertEqual(result, 0, output)

    def test_unknown_visibility_reference_is_rejected(self):
        result, output = self.check({'field': 'enabeld', 'value': True})
        self.assertEqual(result, 1)
        self.assertIn('unbekannten Input', output)

    def test_visibility_requires_supported_home_assistant_version(self):
        result, output = self.check({'field': 'enabled', 'value': True}, '2026.9.0')
        self.assertEqual(result, 1)
        self.assertIn('min_version >= 2026.11.0', output)

    def test_exists_on_empty_entity_default_warns(self):
        result, output = self.check({'field': 'helper', 'operator': 'exists'})
        self.assertEqual(result, 0)
        self.assertIn('eine leere Liste zählt', output)


if __name__ == '__main__':
    unittest.main()
