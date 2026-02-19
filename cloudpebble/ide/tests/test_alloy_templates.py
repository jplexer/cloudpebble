import json
import io
import os
import shutil
import tempfile
import zipfile
import mock

from django.test import TestCase

from ide.utils.alloy_templates import list_alloy_templates, build_template_archive


class TestAlloyTemplates(TestCase):
    def setUp(self):
        self.examples_root = tempfile.mkdtemp()
        self.tutorial_root = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.examples_root)
        shutil.rmtree(self.tutorial_root)

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

    def _write_tutorial_part(self, part):
        self._write_template(os.path.join('tutorial', part))
        src = os.path.join(self.examples_root, 'tutorial', part)
        dst = os.path.join(self.tutorial_root, part)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copytree(src, dst)

    def test_list_alloy_templates_returns_empty_when_missing(self):
        with mock.patch('ide.utils.alloy_templates._examples_root', return_value='/tmp/unused'), \
             mock.patch('ide.utils.alloy_templates._watchface_tutorial_root', return_value='/tmp/unused'):
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
        for part in ['part1', 'part2', 'part3', 'part4', 'part5']:
            self._write_tutorial_part(part)

        with mock.patch('ide.utils.alloy_templates._examples_root', return_value=self.examples_root), \
             mock.patch('ide.utils.alloy_templates._watchface_tutorial_root', return_value=self.tutorial_root):
            templates = list_alloy_templates()

        ids = [template['id'] for template in templates]
        self.assertEqual(
            ids[:5],
            [
                'watchface-tutorial/part1',
                'watchface-tutorial/part2',
                'watchface-tutorial/part3',
                'watchface-tutorial/part4',
                'watchface-tutorial/part5',
            ]
        )
        self.assertEqual(ids[5], 'piu/watchfaces/cupertino')
        self.assertEqual(ids[6:8], ['piu/watchfaces/london', 'piu/watchfaces/redmond'])
        self.assertEqual(ids[8:10], ['piu/apps/gravity', 'piu/apps/words'])
        self.assertGreater(ids.index('hellopebble'), ids.index('piu/apps/words'))
        self.assertGreater(ids.index('hellowatchface'), ids.index('piu/apps/words'))
        self.assertGreater(ids.index('hellofetch'), ids.index('piu/apps/words'))
        self.assertIn('another', ids)
        self.assertIn('zzzapp', ids)
        self.assertNotIn('nonmoddable', ids)
        labels = {t['id']: t['label'] for t in templates}
        self.assertEqual(labels['watchface-tutorial/part1'], 'Your First Watchface')
        self.assertEqual(labels['watchface-tutorial/part2'], 'Customizing Your Watchface')
        self.assertEqual(labels['watchface-tutorial/part3'], 'Adding Battery and Bluetooth')
        self.assertEqual(labels['watchface-tutorial/part4'], 'Adding Weather')
        self.assertEqual(labels['watchface-tutorial/part5'], 'Adding User Settings')
        groups = {t['id']: t['group'] for t in templates}
        self.assertEqual(groups['watchface-tutorial/part1'], 'watchface-tutorial/')
        dirs = {t['id']: t['dir'] for t in templates}
        self.assertEqual(dirs['watchface-tutorial/part1'], 'watchface-tutorial/')

        watchface_labels = [t['label'] for t in templates if t['group'] == 'watchfaces/']
        app_labels = [t['label'] for t in templates if t['group'] == 'apps/']
        self.assertEqual(watchface_labels, ['cupertino', 'london', 'redmond'])
        self.assertEqual(app_labels, ['gravity', 'words'])

    def test_build_template_archive_contains_project_files(self):
        self._write_template('hellopebble')
        with mock.patch('ide.utils.alloy_templates._examples_root', return_value=self.examples_root), \
             mock.patch('ide.utils.alloy_templates._watchface_tutorial_root', return_value=self.tutorial_root):
            archive_bytes = build_template_archive('hellopebble')

        with zipfile.ZipFile(io.BytesIO(archive_bytes), 'r') as zf:
            names = set(zf.namelist())

        self.assertIn('package.json', names)
        self.assertIn('src/embeddedjs/main.js', names)
        self.assertIn('src/embeddedjs/hours.pdc', names)
        self.assertIn('src/embeddedjs/emery/dial.png', names)

    def test_build_template_archive_rejects_traversal(self):
        self._write_template('hellopebble')
        with mock.patch('ide.utils.alloy_templates._examples_root', return_value=self.examples_root), \
             mock.patch('ide.utils.alloy_templates._watchface_tutorial_root', return_value=self.tutorial_root):
            with self.assertRaises(ValueError):
                build_template_archive('../outside')

    def test_build_template_archive_supports_watchface_tutorial_path(self):
        self._write_tutorial_part('part1')
        with mock.patch('ide.utils.alloy_templates._examples_root', return_value=self.examples_root), \
             mock.patch('ide.utils.alloy_templates._watchface_tutorial_root', return_value=self.tutorial_root):
            archive_bytes = build_template_archive('watchface-tutorial/part1')

        with zipfile.ZipFile(io.BytesIO(archive_bytes), 'r') as zf:
            names = set(zf.namelist())
        self.assertIn('package.json', names)
        self.assertIn('src/embeddedjs/main.js', names)
