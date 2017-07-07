import re, os, sys
import util
def normalize(rule_text):
    if len(rule_text)> 1000000:
        print rule_text
        die
    return re.sub('[^a-z0-9]*', '', rule_text.lower())
zefram = open('old_zefram_rules_text.txt').read()
zefram_texts = {}
for text in re.findall(re.compile('\n\n(?:\[orphaned )?text:\n\n(.*?)\n\n(?! )', re.S), zefram):
    zefram_texts[normalize(text)] = text

my_texts = {}
seen_exactly = set()
def handle_text(filename, text):
    for full, header, rest in re.findall('^((Rule [0-9]+[^\n]*\([^\n\)]*)\)[ \t]*\n(.*?)\n\n(?![ 0-9]))', text, re.M | re.S):
        if full in seen_exactly:
            continue
        seen_exactly.add(full)
        title = None
        if not rest.startswith('\n') and '\n' in rest:
            title, rest = rest.split('\n', 1)
        extra = None
        m = re.match('\n([0-9]+\. [^\n]*)\n\n(.*)$', rest, re.S)
        if m:
            extra, rest = m.groups()
        normalized = normalize(rest)
        data = {
            'header': header,
            'title': title,
            'extra': extra,
            'rest': rest,
        }
        my_texts.setdefault(normalized, []).append(data)
#handle_text('a', open('/Users/comex/agora_vanyel0/agora/logs/official/1998.10.20').read())
#sys.exit(0)
for root, dirs, files in os.walk('zeframs-archives'):
    for filename in files:
        path = os.path.join(root, filename)
        #print path
        if not os.path.isfile(path): continue
        if 'theses/' in path or 'cfj/' in path or filename == 'discussion':
            continue # some fake rules here
        if filename.endswith(',v'):
            print 'doing rcs file %s...' % path
            for rev, text in util.revs_of_rcs_file(path):
                handle_text(path + ':' + rev, text)
            print '...done.'
        else:
            print path
            with open(path, 'r') as fp:
                text = fp.read()
                handle_text(path, text)
for norm in zefram_texts:
    if norm not in my_texts:
        print 'missing:'
        print zefram_texts[norm]
        print '--'
