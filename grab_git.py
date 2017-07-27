import os, sys, argparse, json
import util
import git
import regex
import yaml

import logging
logging.basicConfig(level=logging.INFO)

# based on the tutorial
class MyProgressPrinter(git.RemoteProgress):
    def update(self, op_code, cur_count, max_count=None, message=''):
        if max_count:
            pct = str(cur_count / max_count * 100)
        else:
            pct = '??'
        line = 'fetch: ' + pct + '%'
        if message:
            line += ' ' + message
        print(line)

ap = argparse.ArgumentParser()
ap.add_argument('--fetch', action='store_true', help='fetch from GitHub')
ap.add_argument('git_path', nargs='?', default='ruleset.git', help='path to Git repo')
ap.add_argument('out_path', nargs='?', default='out_git.json', help='write to this JSON file')
args = ap.parse_args()

if not args.fetch and not os.path.exists(args.git_path):
    print("ERROR: %r doesn't exist and --fetch not specified.  run grab_git.py --fetch to download it or grab it yourself (git clone --bare https://whatever ruleset.git)" % (args.git_path,))
    sys.exit(1)

try:
    repo = git.Repo(args.git_path)
except git.exc.NoSuchPathError:
    repo = git.Repo.init(args.git_path, bare=True)
if args.fetch:
    if repo.active_branch.name != 'master':
        print("ERROR: active branch is not 'master' but %r" % (repo.active_branch,))
        sys.exit(1)
    try:
        remote = repo.remote('origin')
    except ValueError:
        remote = repo.create_remote('origin', url='https://github.com/AgoraNomic/ruleset.git')
    assert remote.exists()
    remote.fetch('refs/heads/master:refs/heads/master', progress=MyProgressPrinter())
    print('fetch done')

seen_exactly = set()
out = []
def handle_commit(commit):
    message = commit.message
    commit_hexsha = commit.hexsha
    rules = commit.tree['rules']
    date_unix = commit.authored_date
    def handle_blob(blob):
        path = blob.path
        name = path.rsplit('/', 1)[1]
        if name in {'index', 'meta', 'keywords'}:
            return
        blob_hexsha = blob.hexsha
        if blob_hexsha in seen_exactly:
            #print('skip', hexsha)
            return
        seen_exactly.add(blob_hexsha)
        raw = blob.data_stream.read()
        if raw == b'':
            return
        try:
            y = yaml.load(raw)
            if y is None:
                raise Exception('huh?')
            header = 'Rule %s/%s (Power=%s)' % (y['id'], y['rev'], y['power'])
            assert isinstance(y['history'], list)
            # ignore 'annotations' and 'cfjs' for now because the repo's scripts do
            history = list(map(str, y['history']))
            # fix up broken history entries (that don't take wrapping into account)
            # --
            i = 0
            while i < len(history):
                if history[i].startswith('  '):
                    history[i-1] = history[i-1].rstrip() + ' ' + history[i].lstrip()
                    del history[i]
                    continue
                i += 1
            # --
            data = {
                'number': int(y['id']),
                'revnum': str(y['rev']),
                'title': str(y['name']),
                'header': header,
                'extra': None,
                'text': str(y['text']),
                'annotations': None,
                'history': history,
            }
            meta = {
                'date': date_unix,
                'path': 'ruleset.git@%s:%s' % (commit_hexsha, path),
            }
            out.append({'meta': meta, 'data': data})

        except:
            print('note: exception occurred processing path %s in commit %s,' % (path, commit_hexsha,))
            print('content %r' % (raw,))
            raise



    def handle_tree_or_blob(tb):
        if tb.type == 'blob':
            handle_blob(tb)
        else:
            assert tb.type == 'tree'
            # recurse into this subdirectory
            for sub in tb:
                handle_tree_or_blob(sub)
    handle_tree_or_blob(rules)

commits = list(repo.iter_commits())[::-1]
count = 0
for commit in commits:
    handle_commit(commit)
    count += 1
print('processed %s commits' % (count,))
with open(args.out_path, 'w') as gp:
    json.dump(out, gp)
print('-> %s' % (args.out_path,))
