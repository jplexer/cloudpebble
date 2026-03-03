import json
import logging
import zipfile
import io

import requests as http_requests
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from ide.models.build import BuildResult
from ide.models.project import Project
from utils.jsonview import json_view, BadRequest

import utils.s3 as s3

logger = logging.getLogger(__name__)

APPSTORE_API_BASE = None


def _get_api_base():
    global APPSTORE_API_BASE
    if APPSTORE_API_BASE is None:
        APPSTORE_API_BASE = getattr(settings, 'APPSTORE_API_BASE', 'https://appstore-api.repebble.com')
    return APPSTORE_API_BASE.rstrip('/')


def _get_firebase_token(request):
    token = request.session.get('firebase_id_token', '')
    if not token:
        raise BadRequest("Not signed in to Firebase. Please sign in and try again.")
    return token


def _api_headers(token):
    return {'Authorization': 'Bearer %s' % token}


@require_POST
@login_required
@json_view
def publish_preflight(request, project_id):
    project = get_object_or_404(Project, pk=project_id, owner=request.user)

    if project.project_type not in ('native', 'alloy'):
        raise BadRequest("Publishing is only supported for native and alloy projects.")

    token = _get_firebase_token(request)
    base = _get_api_base()

    # Check developer status
    try:
        resp = http_requests.get(
            '%s/api/v1/developer/me' % base,
            headers=_api_headers(token),
            timeout=60,
        )
    except http_requests.RequestException as e:
        logger.error("Appstore API /developer/me failed: %s", e)
        raise BadRequest("Could not connect to the app store. Please try again.")

    if resp.status_code == 403:
        # Try to auto-create developer account
        try:
            create_resp = http_requests.post(
                '%s/api/v1/developer/create' % base,
                headers=_api_headers(token),
                json={},
                timeout=60,
            )
        except http_requests.RequestException as e:
            logger.error("Appstore API /developer/create failed: %s", e)
            raise BadRequest("Could not connect to the app store. Please try again.")
        if create_resp.status_code not in (200, 201):
            raise BadRequest("Could not create developer account: %s" % create_resp.text)
        # Retry /me
        try:
            resp = http_requests.get(
                '%s/api/v1/developer/me' % base,
                headers=_api_headers(token),
                timeout=60,
            )
        except http_requests.RequestException as e:
            logger.error("Appstore API /developer/me retry failed: %s", e)
            raise BadRequest("Could not connect to the app store. Please try again.")

    if resp.status_code != 200:
        raise BadRequest("Could not check developer status (HTTP %d)." % resp.status_code)

    me_data = resp.json()
    app_lookup = me_data.get('app_lookup', {}).get('by_app_uuid', {})
    logger.info("Developer /me app_lookup by_app_uuid: %s", app_lookup)

    # Look up this project's UUID in the store (case-insensitive)
    app_uuid = (project.app_uuid or '').lower()
    app_id = None
    is_new_app = True

    for uuid_key, app_info in app_lookup.items():
        if uuid_key.lower() == app_uuid:
            # app_info may be a string (app ID) or a dict with 'id' key
            if isinstance(app_info, dict):
                app_id = app_info.get('id')
            else:
                app_id = str(app_info)
            is_new_app = False
            break

    # Category options for watchapps
    category_options = [
        {'value': 'daily', 'label': 'Daily'},
        {'value': 'tools_and_utilities', 'label': 'Tools & Utilities'},
        {'value': 'notifications', 'label': 'Notifications'},
        {'value': 'remotes', 'label': 'Remotes'},
        {'value': 'health_and_fitness', 'label': 'Health & Fitness'},
        {'value': 'games', 'label': 'Games'},
    ]

    has_successful_build = project.builds.filter(state=BuildResult.STATE_SUCCEEDED).exists()

    return {
        'is_new_app': is_new_app,
        'app_id': app_id,
        'app_uuid': app_uuid,
        'is_watchface': project.app_is_watchface,
        'category_options': category_options,
        'app_name': project.app_long_name or project.app_short_name or project.name,
        'app_version': project.app_version_label or '1.0',
        'github_repo': project.github_repo or '',
        'has_successful_build': has_successful_build,
    }


@require_POST
@login_required
@json_view
def publish_submit(request, project_id):
    project = get_object_or_404(Project, pk=project_id, owner=request.user)

    if project.project_type not in ('native', 'alloy'):
        raise BadRequest("Publishing is only supported for native and alloy projects.")

    token = _get_firebase_token(request)
    base = _get_api_base()

    # Get form data
    is_new_app = request.POST.get('is_new_app') == 'true'
    app_id = request.POST.get('app_id', '')
    name = request.POST.get('name', '')
    description = request.POST.get('description', '')
    source = request.POST.get('source', '')
    category = request.POST.get('category', '')
    release_notes = request.POST.get('release_notes', '')
    version = request.POST.get('version', project.app_version_label or '1.0')

    # Get latest successful build
    try:
        build = project.builds.filter(state=BuildResult.STATE_SUCCEEDED).order_by('-started')[0]
    except (IndexError, BuildResult.DoesNotExist):
        raise BadRequest("No successful build found. Please build your project first.")

    # Read PBW from storage
    pbw_data = _read_pbw(build, project)

    # Normalize UUID in PBW (lowercase the UUID in appinfo.json inside the zip)
    app_uuid = (project.app_uuid or '').lower()
    pbw_data = _normalize_pbw_uuid(pbw_data, app_uuid)

    # Build multipart form data (list-of-tuples to allow duplicate field names)
    files = [('pbwFile', ('app.pbw', pbw_data, 'application/octet-stream'))]

    # Collect screenshot files (keys like screenshot_{platform}_{index} from frontend)
    # Remap to screenshots_{platform} — pebble-tool uses this field name for BOTH
    # static screenshots and GIFs (the API distinguishes by content type).
    for key in request.FILES:
        if key.startswith('screenshot_'):
            f = request.FILES[key]
            # Parse platform from screenshot_{platform}_{index}
            parts = key.split('_', 2)  # ['screenshot', platform, index]
            if len(parts) >= 2:
                platform = parts[1]
            else:
                platform = 'unknown'
            # Determine correct MIME type from filename extension
            is_gif = (f.content_type == 'image/gif' or
                      f.name.lower().endswith('.gif'))
            content_type = 'image/gif' if is_gif else 'image/png'
            field_name = 'screenshots_%s' % platform
            logger.info("Attaching file: field=%s name=%s content_type=%s size=%d",
                        field_name, f.name, content_type, f.size)
            files.append((field_name, (f.name, f.read(), content_type)))

    if is_new_app:
        # Validation for new apps
        if not name:
            raise BadRequest("App name is required for new apps.")
        if not description:
            raise BadRequest("Description is required for new apps.")
        if not project.app_is_watchface and not category:
            raise BadRequest("Category is required for new watchapps.")

        data = {
            'name': name,
            'description': description,
            'version': version,
            'expectedUuid': app_uuid,
            'type': 'watchface' if project.app_is_watchface else 'watchapp',
            'visible': 'true',
            'isPublished': 'true',
            'source': source or '',
            'releaseNotes': release_notes or '',
        }
        if category and not project.app_is_watchface:
            data['category'] = category

        # Handle icons
        if 'icon_small' in request.FILES:
            f = request.FILES['icon_small']
            files.append(('iconSmall', (f.name, f.read(), f.content_type)))
        if 'icon_large' in request.FILES:
            f = request.FILES['icon_large']
            files.append(('iconLarge', (f.name, f.read(), f.content_type)))

        # If no icons and it's a watchapp, send iconPrompt for AI generation
        if not project.app_is_watchface and 'icon_small' not in request.FILES:
            data['iconPrompt'] = '%s: %s' % (name, description)

        url = '%s/api/dashboard/apps' % base
    else:
        # Existing app update
        if not app_id:
            raise BadRequest("App ID is required for updates.")
        data = {
            'version': version,
            'releaseNotes': release_notes or '',
            'isPublished': 'true',
            'replaceScreenshots': 'false',
        }

        url = '%s/api/dashboard/apps/%s/releases' % (base, app_id)

    # Forward to appstore API
    screenshot_count = len(files) - 1  # subtract pbwFile
    logger.info("Publishing to %s with %d screenshot files, data keys: %s, all files: %s",
                url, screenshot_count, list(data.keys()),
                [(name, fname, ct) for name, (fname, _, ct) in files])
    try:
        resp = http_requests.post(
            url,
            data=data,
            files=files,
            headers=_api_headers(token),
            timeout=300,
        )
    except http_requests.RequestException as e:
        logger.error("Appstore API request failed: %s", e)
        raise BadRequest("Could not connect to the app store. Please try again.")

    logger.info("Appstore API response: status=%d body=%s", resp.status_code, resp.text[:1000])
    if resp.status_code in (200, 201):
        result = resp.json()
        logger.info("Publish success: %s", result)

        # Forward screenshot results if present (releases endpoint reports failures)
        screenshot_results = result.get('screenshotResults', {})
        screenshot_warnings = []
        for fail in screenshot_results.get('failed', []):
            screenshot_warnings.append('%s: %s' % (fail.get('platform', '?'), fail.get('error', 'unknown')))
        if screenshot_warnings:
            logger.warning("Screenshot upload failures: %s", screenshot_warnings)

        ret = {
            'published': True,
            'app_id': result.get('id') or app_id,
        }
        if screenshot_warnings:
            ret['screenshot_warnings'] = screenshot_warnings
        return ret
    else:
        error_text = resp.text
        logger.warning("Appstore API error: status=%d body=%s", resp.status_code, error_text[:500])
        try:
            error_json = resp.json()
            error_text = error_json.get('message', error_json.get('error', resp.text))
        except (ValueError, KeyError):
            pass
        raise BadRequest("App store returned an error: %s" % error_text)


def _read_pbw(build, project):
    """Read PBW binary data from storage."""
    if settings.AWS_ENABLED:
        return s3.read_file('builds', build.pbw)
    else:
        with open(build.pbw, 'rb') as f:
            return f.read()


def _normalize_pbw_uuid(pbw_data, target_uuid):
    """Ensure the UUID inside the PBW's appinfo.json is lowercase.

    The appstore API matches by UUID, so it needs to be consistent.
    Based on pebble-tool's _create_uuid_normalized_pbw logic.
    """
    if not target_uuid:
        return pbw_data

    try:
        with zipfile.ZipFile(io.BytesIO(pbw_data), 'r') as original:
            if 'appinfo.json' not in original.namelist():
                return pbw_data

            appinfo_raw = original.read('appinfo.json')
            appinfo = json.loads(appinfo_raw)
            current_uuid = appinfo.get('uuid', '')

            if current_uuid.lower() == target_uuid and current_uuid == target_uuid:
                return pbw_data

            # Rewrite with normalized UUID
            appinfo['uuid'] = target_uuid
            new_appinfo = json.dumps(appinfo, indent=2).encode('utf-8')

            output = io.BytesIO()
            with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as new_zip:
                for item in original.namelist():
                    if item == 'appinfo.json':
                        new_zip.writestr(item, new_appinfo)
                    else:
                        new_zip.writestr(item, original.read(item))
            return output.getvalue()
    except (zipfile.BadZipFile, json.JSONDecodeError, KeyError) as e:
        logger.warning("Could not normalize PBW UUID: %s", e)
        return pbw_data
