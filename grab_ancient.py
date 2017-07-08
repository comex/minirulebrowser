import os, sys
import util
import regex # not re

my_texts = {}
seen_exactly = set()
fsfr_regex = regex.compile(r'''
    ^ # start of line
    (?P<full>
        (?P<header>
            Rule\ (?P<number>[0-9]+)
            (?: # revision number?
                /(?P<revnum>[0-9]+)
            )?
            [^\n]*
            # mutability/power marking
            \([^\n\)]*\)
        )
        (?P<newline>[ \t]*\n)
        (?:
            # title line
            (?P<title>\S[^\n]*?)
            (?&newline)
        )?
        (?&newline)
        (?:
            # old fashioned rule number?
            (?P<extra>
                [0-9]+\.\ .*?
            )
            (?&newline)
            (?&newline)
        )?
        # main rule text
        (?P<text>.*?)
        (?&newline)
        (?&newline)
        # there may be some []-delimited annotations
        (?P<annotations>
            (?:
                \[
                # allow nested []s, lol recursive regex
                (?P<nested>
                    [^\[\]]* |
                    \[(?&nested)\]
                )*
                # ending ] should be followed by \n\n, perhaps with excess whitespace
                \]
                (?&newline)
                (?&newline)
            )*
        )
        # there may be history
        (?P<history>
            History:
            (?&newline)
            (?P<thehist>
                (?&newline)
                .*?
                (?&newline)
                (?&newline)
            )
        )?
        # end on something that is not indented, nor an old-fashioned numbered rule
        (?![ 0-9])
    )
''', regex.M | regex.S)
def find_stdformat_rules(text, seen_exactly_set):
    for m in fsfr_regex.finditer(text):
        g = m.groupdict()
        if full in seen_exactly:
            continue
        seen_exactly.add(full)
        history = None
        if g['history'] is not None:
            history = list(split_history(g['thehist']))
        data = {
            'number': int(g['number']),
            'revnum': int(g['revnum') if g['revnum'] else None,
            'title': g['title'] or None,
            'extra': g['extra'] or None,
            'text': text,
            'annotations': g['annotations'],
            'history': history,
        }


def split_history(history):
    for line in regex.split('\n(?!  )', history):
        yield regex.replace('\s+', ' ', line)
def handle_filetext(path, filetext):
    for full, header, number, text in re.findall('^((Rule ([0-9]+)[^\n]*\([^\n\)]*)\)[ \t]*\n(.*?)\n\n(?![ 0-9]))', filetext, re.M | re.S):
        if full in seen_exactly:
            continue
        seen_exactly.add(full)
        number = int(number)
        title = None
        if not text.startswith('\n') and '\n' in text:
            title, text = text.split('\n', 1)
        extra = None
        m = re.match('\n([0-9]+\. [^\n]*)\n\n(.*)$', text, re.S)
        if m:
            extra, text = m.groups()
        normalized = normalize(text)
        data = {
            'number': number,
            'header': header,
            'title': title,
            'extra': extra,
            'text': text,
        }
        my_texts.setdefault(normalized, []).append(data)
    # alternate old format
    if 'usenet0/rga' in path:
        for header, number, letter, text in re.findall('^(([0-9]{3})([a-z]?)\.\s+)(.*?)\n\s*\n', filetext, re.M | re.S):
            title = None
            number = int(number)
            if number >= 319 and number not in (330, 436):
                # have title
                title, text = text.split('\n', 1)
                header += title
                title = title.rstrip(':')
            else:
                text = ' ' * len(header) + text
                header = header.rstrip()
            normalized = normalize(text)
            data = {
                'number': number,
                'header': header,
                'title': title,
                'extra': letter or None,
                'text': text,
            }
            my_texts.setdefault(normalized, []).append(data)
rootpath = sys.argv[1] if len(sys.argv) > 1 else 'zeframs-archives'
for root, dirs, files in os.walk(rootpath):
    for filename in files:
        path = os.path.join(root, filename)
        #print path
        if not os.path.isfile(path): continue
        if 'theses/' in path or 'cfj/' in path or filename == 'discussion':
            continue # some fake rules here
        if filename.endswith(',v'):
            print 'doing rcs file %s...' % path
            for rev, text in util.revs_of_rcs_file(path):
                handle_filetext(path + ':' + rev, text)
            print '...done.'
        else:
            #print path
            with open(path, 'r') as fp:
                text = fp.read()
                handle_filetext(path, text)
with open('temp.txt', 'w') as fp:
    for datas in my_texts.itervalues():
        for data in datas:
            fp.write('<<%s>>\n\n' % data['text'])
        
#sys.exit(0)
for norm in zefram_texts:
    if norm not in my_texts:
        print 'missing:'
        print zefram_texts[norm]
        print '--'
