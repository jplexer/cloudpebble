import base64
import hashlib

__author__ = 'katharine'


def git_sha(content):
    if isinstance(content, str):
        content = content.encode('utf-8')
    return hashlib.sha1(('blob %d\x00' % len(content)).encode('utf-8') + content).hexdigest()


def git_blob(repo, sha):
    return base64.b64decode(repo.get_git_blob(sha).content)
