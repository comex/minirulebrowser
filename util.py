import subprocess, re, os
def x_check_output(args, **kwargs):
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
    stdout, stderr = p.communicate()
    return stdout
def revs_of_rcs_file(filename):
    env = dict(os.environ.iteritems())
    env['RCS_MEM_LIMIT'] = '99999' # kb
    filename = os.path.abspath(filename)
    log = x_check_output(['rcs', 'rlog', filename], env=env)
    for rev in re.findall('-----\nrevision (\S+)', log):
        text = x_check_output(['rcs', 'co', '-p'+rev, filename], env=env)
        yield rev, text
