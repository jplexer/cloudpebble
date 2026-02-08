import urllib
import urllib.parse
import requests

from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_safe
from django.http import Http404

from utils.td_helper import send_td_event
from utils.jsonview import json_view
from utils.filter_dict import filter_dict

__author__ = 'katharine'

PACKAGE_SPEC = {
    'version': True,
    'name': True,
    'description': True,
    'keywords': True,
    'author': True,
    '_id': 'name'
}


@login_required
@require_safe
@json_view
def npm_search(request):
    try:
        query = request.GET['q']
    except KeyError:
        return {'packages': []}
    response = requests.get('https://registry.npmjs.org/-/v1/search', {'text': query, 'size': 20}).json()
    search = []
    for obj in response.get('objects', []):
        pkg = obj.get('package', {})
        author = pkg.get('author', {})
        search.append({
            'name': pkg.get('name', ''),
            'version': pkg.get('version', ''),
            'description': pkg.get('description', ''),
            'keywords': pkg.get('keywords', []),
            'author': author.get('name', '') if isinstance(author, dict) else str(author),
        })
    data = {'packages': [filter_dict(package, PACKAGE_SPEC) for package in search]}
    send_td_event('cloudpebble_package_search', data={
        'data': {
            'query': query
        }
    }, request=request)
    return data


@login_required
@require_safe
@json_view
def npm_info(request):
    query = request.GET['q']

    try:
        raw = requests.get('https://registry.npmjs.org/%s' % urllib.parse.quote(query, safe='@')).json()
    except ValueError:
        raise Http404("Package not found")
    if 'error' in raw:
        raise Http404("Package not found")

    author = raw.get('author', {})
    package = {
        'name': raw.get('name', ''),
        'version': raw.get('dist-tags', {}).get('latest', ''),
        'description': raw.get('description', ''),
        'keywords': raw.get('keywords', []),
        'author': author.get('name', '') if isinstance(author, dict) else str(author),
    }
    data = {
        'package': filter_dict(package, PACKAGE_SPEC)
    }
    send_td_event('cloudpebble_package_get_info', data={
        'data': {
            'query': query
        }
    }, request=request)
    return data
