import json
import io
import os
import shutil
import tempfile
import zipfile

from django.test import TestCase, override_settings

from ide.utils.alloy_templates import list_alloy_templates, build_template_archive


class TestAlloyTemplates(TestCase):
    def setUp(self):
        self.examples_root = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.examples_root)

    def _write_template(self, relpath, project_type='moddable'):
        template_root = os.path.join(self.examples_root, relpath)
        os.makedirs(os.path.join(template_root, 'src', 'embeddedjs', 'emery'))
        with open(os.path.join(template_root, 'src', 'embeddedjs', 'main.js'), 'w') as handle:
            handle.write('trace("ok");\n')
        with open(os.path.join(template_root, 'src', 'embeddedjs', 'hours.pdc'), 'wb') as handle:
            handle.write(b'PDC')
        with open(os.path.join(template_root, 'src', 'embeddedjs', 'emery', 'dial.png'), 'wb') as handle:
            handle.write(b'\x89PNG\r\n')
        with open(os.path.join(template_root, 'package.json'), 'w') as handle:
            json.dump({'name': relpath, 'pebble': {'projectType': project_type}}, handle)

    @override_settings(MODDABLE_EXAMPLES_ROOT='/tmp/unused')
    def test_list_alloy_templates_returns_empty_when_missing(self):
        self.assertEqual(list_alloy_templates(), [])

    def test_list_alloy_templates_applies_requested_order(self):
        self._write_template('zzzapp')
        self._write_template('hellofetch')
        self._write_template('hellopebble')
        self._write_template('hellowatchface')
        self._write_template('piu/watchfaces/cupertino')
        self._write_template('piu/watchfaces/redmond')
        self._write_template('piu/watchfaces/london')
        self._write_template('piu/apps/words')
        self._write_template('piu/apps/gravity')
        self._write_template('another')
        self._write_template('nonmoddable', project_type='native')

        with override_settings(MODDABLE_EXAMPLES_ROOT=self.examples_root):
            templates = list_alloy_templates()

        ids = [template['id'] for template in templates]
        self.assertEqual(ids[0], 'piu/watchfaces/cupertino')
        self.assertEqual(ids[1:3], ['piu/watchfaces/london', 'piu/watchfaces/redmond'])
        self.assertEqual(ids[3:5], ['piu/apps/gravity', 'piu/apps/words'])
        self.assertGreater(ids.index('hellopebble'), ids.index('piu/apps/words'))
        self.assertGreater(ids.index('hellowatchface'), ids.index('piu/apps/words'))
        self.assertGreater(ids.index('hellofetch'), ids.index('piu/apps/words'))
        self.assertIn('another', ids)
        self.assertIn('zzzapp', ids)
        self.assertNotIn('nonmoddable', ids)

        watchface_labels = [t['label'] for t in templates if t['group'] == 'watchfaces/']
        app_labels = [t['label'] for t in templates if t['group'] == 'apps/']
        self.assertEqual(watchface_labels, ['cupertino', 'london', 'redmond'])
        self.assertEqual(app_labels, ['gravity', 'words'])

    def test_build_template_archive_contains_project_files(self):
        self._write_template('hellopebble')
        with override_settings(MODDABLE_EXAMPLES_ROOT=self.examples_root):
            archive_bytes = build_template_archive('hellopebble')

        with zipfile.ZipFile(io.BytesIO(archive_bytes), 'r') as zf:
            names = set(zf.namelist())

        self.assertIn('package.json', names)
        self.assertIn('src/embeddedjs/main.js', names)
        self.assertIn('src/embeddedjs/hours.pdc', names)
        self.assertIn('src/embeddedjs/emery/dial.png', names)

    def test_build_template_archive_rejects_traversal(self):
        self._write_template('hellopebble')
        with override_settings(MODDABLE_EXAMPLES_ROOT=self.examples_root):
            with self.assertRaises(ValueError):
                build_template_archive('../outside')
