import io
import json
import os
import zipfile

EXAMPLES_ROOT = '/opt/pebble-examples'


def _examples_root():
    return EXAMPLES_ROOT


def _template_display_name(path):
    if path.startswith('piu/watchfaces/'):
        return path.split('/')[-1]
    if path.startswith('piu/apps/'):
        return path.split('/')[-1]
    return path


def _template_group(path):
    if path.startswith('piu/watchfaces/'):
        return 'watchfaces/'
    if path.startswith('piu/apps/'):
        return 'apps/'
    return None


def _ordered_paths(paths):
    unique_paths = []
    seen = set()
    for item in paths:
        if item not in seen:
            seen.add(item)
            unique_paths.append(item)

    def _remainder_key(value):
        return value.lower()

    watchfaces = sorted([p for p in unique_paths if p.startswith('piu/watchfaces/')], key=_remainder_key)
    apps = sorted([p for p in unique_paths if p.startswith('piu/apps/')], key=_remainder_key)

    consumed = set(watchfaces + apps)
    remainder = sorted([p for p in unique_paths if p not in consumed], key=_remainder_key)
    return watchfaces + apps + remainder


def _is_moddable_project(project_dir):
    package_json = os.path.join(project_dir, 'package.json')
    src_embeddedjs = os.path.join(project_dir, 'src', 'embeddedjs')
    if not os.path.isfile(package_json) or not os.path.isdir(src_embeddedjs):
        return False

    try:
        with open(package_json, 'r') as handle:
            package_data = json.load(handle)
    except (ValueError, OSError):
        return False

    return package_data.get('pebble', {}).get('projectType') == 'moddable'


def list_alloy_templates():
    root = _examples_root()
    if not os.path.isdir(root):
        return []

    paths = []
    for dirpath, dirnames, _ in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith('.') and d != '.git']
        if _is_moddable_project(dirpath):
            relpath = os.path.relpath(dirpath, root).replace('\\', '/')
            paths.append(relpath)
            dirnames[:] = []

    templates = []
    for path in _ordered_paths(paths):
        templates.append({
            'id': path,
            'path': path,
            'label': _template_display_name(path),
            'group': _template_group(path),
        })
    return templates


def build_template_archive(template_path):
    root = _examples_root()
    target_dir = os.path.normpath(os.path.join(root, template_path))
    if not target_dir.startswith(os.path.normpath(root) + os.sep):
        raise ValueError('Invalid template path')
    if not os.path.isdir(target_dir):
        raise ValueError('Template path does not exist')

    if not _is_moddable_project(target_dir):
        raise ValueError('Template is not a valid JavaScript SDK project')

    bundle = io.BytesIO()
    with zipfile.ZipFile(bundle, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for dirpath, dirnames, filenames in os.walk(target_dir):
            dirnames[:] = [d for d in dirnames if not d.startswith('.') and d != '.git']
            for filename in filenames:
                if filename.startswith('.'):
                    continue
                full_path = os.path.join(dirpath, filename)
                arcname = os.path.relpath(full_path, target_dir)
                archive.write(full_path, arcname=arcname)

    return bundle.getvalue()
