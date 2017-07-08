import subprocess, regex, os
from multiprocessing import Pool
def x_check_output(args, **kwargs):
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
    stdout, stderr = p.communicate()
    return stdout
def revs_of_rcs_file(path):
    path = os.path.abspath(path)
    log = x_check_output(['rcs', 'rlog', path], env=rcsenv)
    split = regex.split('\n(?:----------------------------|=============================================================================)\n', log)
    assert split[-1].strip() == ''
    split = split[1:-1]
    todo = []
    for revinfo in split:
        m = regex.match('revision ([^\n]*)\ndate: ([^;]*)[^\n]*\n(.*)', revinfo, regex.S)
        if not m:
            raise Exception("can't parse output from rcs: %r" % revinfo)
        rev, date, revlog = m.groups()
        todo.append({'rev': rev, 'date': date, 'revlog': revlog, 'path': path})
    return Pool().map(revs_of_rcs_file_do_one, todo)

rcsenv = dict(os.environ.iteritems())
rcsenv['RCS_MEM_LIMIT'] = '99999' # kb

def revs_of_rcs_file_do_one(info):
    text = x_check_output(['rcs', 'co', '-p'+info['rev'], info['path']], env=rcsenv)
    info['text'] = text
    del info['path']
    print '#', info['rev']
    return info

def normalize(rule_text):
    if len(rule_text)> 1000000:
        print rule_text
        die
    return re.sub('[^a-z0-9]*', '', rule_text.lower())

for info in revs_of_rcs_file('/Users/comex/agora/current_flr.txt,v'): print info
