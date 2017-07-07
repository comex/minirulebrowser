import re, os
import util
def normalize(rule_text):
    return re.sub('[^a-z0-9]', '', rule_text.lower())
zefram = open('old_zefram_rules_text.txt').read()
zefram_texts = {}
for text in re.findall(re.compile('\n\n(?:\[orphaned )?text:\n\n(.*?)\n\n(?! )', re.S), zefram):
    zefram_texts[normalize(text)] = text


def handle_text(filename, text):
    for full, header, rest in re.findall('^((Rule [0-9]+[^\n]*\([^\n\)]*)\)[ \t]*\n(.*?)\n\n(?![ 0-9]))', text, re.M | re.S):
        title = None
        if '\n' not in rest:
            print repr(full)
            print repr(rest)
            print path
            die
        if not rest.startswith('\n') and '\n' in rest:
            title, rest = rest.split('\n', 1)
        print rest
        print '###'
for root, dirs, files in os.walk('agora-archives'):
    for filename in files:
        path = os.path.join(root, filename)
        if not os.path.isfile(path): continue
        if 'theses/' in path or 'cfj/' in path or filename == 'discussion':
            continue # some fake rules here
        if filename.endswith(',v'):
            for rev, text in util.revs_of_rcs_file(filename):
                handle_text(filename + ':' + rev, text)
        else:
            with open(path, 'r') as fp:
                text = fp.read()
                handle_text(filename, text)
