# -*- coding: utf-8 -*-
"""用 GitHub REST API 提交单个文件（当 github.com:443 被阻断、api.github.com 仍通时的备用推送通道）。

用法：python _api_push.py <本地文件> <仓库内路径> [commit message]
注意：本脚本仅在 git push 无法连通时使用；正常情况下优先 git push。
"""
import base64
import json
import os
import subprocess
import sys
import urllib.request

REPO = 'edgetutor-cn/READING'
BRANCH = 'master'


def token():
    url = subprocess.run(['git', 'remote', 'get-url', 'origin'], capture_output=True, text=True).stdout.strip()
    # https://<token>@github.com/owner/repo.git
    if '@github.com' in url:
        return url.split('://', 1)[1].split('@', 1)[0].split(':', 1)[-1]
    return os.environ['GH_TOKEN']


def api(method, path, payload=None, tk=None):
    req = urllib.request.Request(
        'https://api.github.com' + path, method=method,
        headers={'Authorization': 'Bearer ' + tk, 'Accept': 'application/vnd.github+json',
                 'User-Agent': 'edge-deploy'})
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        req.add_header('Content-Type', 'application/json')
    with urllib.request.urlopen(req, data, timeout=60) as r:
        return json.loads(r.read().decode())


def main():
    local, remote_path = sys.argv[1], sys.argv[2]
    msg = sys.argv[3] if len(sys.argv) > 3 else 'update ' + remote_path
    tk = token()
    cur = api('GET', f'/repos/{REPO}/contents/{remote_path}?ref={BRANCH}', tk=tk)
    content = open(local, 'rb').read()
    res = api('PUT', f'/repos/{REPO}/contents/{remote_path}', {
        'message': msg,
        'content': base64.b64encode(content).decode(),
        'sha': cur['sha'],
        'branch': BRANCH,
    }, tk=tk)
    print('已提交:', res['commit']['sha'][:10], res['commit']['message'].splitlines()[0])


if __name__ == '__main__':
    main()
