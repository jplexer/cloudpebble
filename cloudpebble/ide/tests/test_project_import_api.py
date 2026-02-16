import json
from io import BytesIO
from zipfile import ZipFile

import mock
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test.client import Client
from django.test import TestCase

from ide.models import Project


def _make_zip_bytes():
    buf = BytesIO()
    with ZipFile(buf, 'w') as zf:
        zf.writestr('appinfo.json', '{"sdkVersion":"3"}')
        zf.writestr('src/main.c', 'int main(void){return 0;}')
        zf.writestr('wscript', 'def options(ctx): pass')
    return buf.getvalue()


class _FakeTask(object):
    task_id = 'task-123'


class TestProjectImportApi(TestCase):
    def setUp(self):
        self.client = Client()
        self.client.post('/accounts/register', {
            'username': 'test',
            'email': 'test@test.test',
            'password1': 'test',
            'password2': 'test',
        })
        self.assertTrue(self.client.login(username='test', password='test'))

    @mock.patch('ide.api.project.do_import_archive')
    def test_import_zip_uses_selected_sdk(self, import_archive):
        import_archive.delay.return_value = _FakeTask()
        response = self.client.post('/ide/import/zip', {
            'name': 'zip-sdk-4977',
            'sdk': '4.9.77',
            'archive': SimpleUploadedFile('project.zip', _make_zip_bytes(), content_type='application/zip'),
        })
        payload = json.loads(response.content)
        self.assertTrue(payload['success'])
        project = Project.objects.get(id=payload['project_id'])
        self.assertEqual(project.sdk_version, '4.9.77')

    @mock.patch('ide.api.project.do_import_archive')
    def test_import_zip_defaults_to_4977(self, import_archive):
        import_archive.delay.return_value = _FakeTask()
        response = self.client.post('/ide/import/zip', {
            'name': 'zip-sdk-default',
            'archive': SimpleUploadedFile('project.zip', _make_zip_bytes(), content_type='application/zip'),
        })
        payload = json.loads(response.content)
        self.assertTrue(payload['success'])
        project = Project.objects.get(id=payload['project_id'])
        self.assertEqual(project.sdk_version, '4.9.77')

    @mock.patch('ide.api.project.do_import_archive')
    def test_import_zip_rejects_invalid_sdk(self, import_archive):
        response = self.client.post('/ide/import/zip', {
            'name': 'zip-sdk-invalid',
            'sdk': 'invalid-sdk',
            'archive': SimpleUploadedFile('project.zip', _make_zip_bytes(), content_type='application/zip'),
        })
        payload = json.loads(response.content)
        self.assertFalse(payload['success'])
        self.assertEqual(response.status_code, 400)
        import_archive.delay.assert_not_called()
        self.assertFalse(Project.objects.filter(name='zip-sdk-invalid').exists())

    @mock.patch('ide.api.project.do_import_github')
    def test_import_github_uses_selected_sdk(self, import_github):
        import_github.delay.return_value = _FakeTask()
        response = self.client.post('/ide/import/github', {
            'name': 'github-sdk-4121',
            'repo': 'github.com/example/repo',
            'branch': 'master',
            'sdk': '4.9.121-1-moddable',
            'add_remote': 'false',
        })
        payload = json.loads(response.content)
        self.assertTrue(payload['success'])
        project = Project.objects.get(id=payload['project_id'])
        self.assertEqual(project.sdk_version, '4.9.121-1-moddable')

    @mock.patch('ide.api.project.do_import_github')
    def test_import_github_defaults_to_4977(self, import_github):
        import_github.delay.return_value = _FakeTask()
        response = self.client.post('/ide/import/github', {
            'name': 'github-sdk-default',
            'repo': 'github.com/example/repo',
            'branch': 'master',
            'add_remote': 'false',
        })
        payload = json.loads(response.content)
        self.assertTrue(payload['success'])
        project = Project.objects.get(id=payload['project_id'])
        self.assertEqual(project.sdk_version, '4.9.77')

    @mock.patch('ide.api.project.do_import_github')
    def test_import_github_rejects_invalid_sdk(self, import_github):
        response = self.client.post('/ide/import/github', {
            'name': 'github-sdk-invalid',
            'repo': 'github.com/example/repo',
            'branch': 'master',
            'sdk': 'invalid-sdk',
            'add_remote': 'false',
        })
        payload = json.loads(response.content)
        self.assertFalse(payload['success'])
        self.assertEqual(response.status_code, 400)
        import_github.delay.assert_not_called()
        self.assertFalse(Project.objects.filter(name='github-sdk-invalid').exists())
