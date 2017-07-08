import os, sys, tempfile, mailbox, email, datetime, subprocess
import util
import regex # not re
from rcs import RCSFile

my_texts = {}
seen_exactly = set()
fsfr_regex = regex.compile(br'''
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
                    [^\[\]\n]* |
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
''', regex.M | regex.S | regex.X)
def find_stdformat_rules(text, seen_exactly_set):
    for m in fsfr_regex.finditer(text):
        g = m.groupdict()
        full = g['full']
        if full in seen_exactly_set:
            continue
        seen_exactly_set.add(full)
        history = None
        if g['history'] is not None:
            history = list(split_history(g['thehist']))
        data = {
            'number': int(g['number']),
            'revnum': int(g['revnum']) if g['revnum'] else None,
            'title': g['title'] or None,
            'header': g['header'],
            'extra': g['extra'] or None,
            'text': g['text'],
            'annotations': g['annotations'],
            'history': history,
        }
        yield data

def split_history(history):
    for line in regex.split('\n(?!  )', history):
        yield regex.replace('\s+', ' ', line)

def find_oldformat_rules(text, seen_exactly_set):
    for full, header, number, letter, text in regex.findall(b'^((([0-9]{3})([a-z]?)\.\s+)(.*?))\n[ \t]*\n', filetext, regex.M | regex.S):
        if full in seen_exactly_set:
            continue
        seen_exactly_set.add(full)
        title = None
        inumber = int(number)
        if inumber >= 319 and inumber not in (330, 436):
            # have title
            title, text = text.split('\n', 1)
            header += title
            title = title.rstrip(':')
        else:
            text = ' ' * len(header) + text
            header = header.rstrip()
        normalized = normalize(text)
        data = {
            'number': inumber,
            'revnum': None,
            'title': title,
            'header': header,
            'extra': (number + letter) if letter else None,
            'text': text,
            'annotations': None,
            'history': None,
        }
        yield data

def find_rules(path, text, seen_exactly_set):
    if 'theses/' in path or 'cfj/' in path or path.endswith('/discussion'):
        return # some fake rules here
    if 'usenet0/rga' in path:
        yield from find_oldformat_rules(text, seen_exactly_set)
    yield from find_stdformat_rules(text, seen_exactly_set)

def walk_file_nocontainer(metadata, text):
    assert isinstance(text, bytes)
    for data in find_rules(metadata['path'], text, metadata['seen_exactly']): 
        new_metadata = metadata.copy()
        del new_metadata['seen_exactly']
        yield {'meta': metadata, 'data': data}

def walk_file(metadata, text, is_real_path):
    if metadata['path'].endswith(',v'):
        # looks like rcs
        rcs = RCSFile(text)
        for revinfo in rcs.get_revisions():
            new_metadata = {**metadata, 'date': revinfo['date'], 'path': metadata['path'] + ' -r%s' % revinfo['num']}
            text = b'\n'.join(revinfo['text'])
            yield from walk_file(new_metadata, text, is_real_path=False)
        return
    if regex.match(b'From [^\n]+\n[A-Z][^ ]*:', text):
        # looks like mbox
        # but python is dumb and doesn't handle all mbox variants; in fact, none of my mbox files are in the format it expects
        p = subprocess.Popen(['formail'], stdin=subprocess.PIPE, stdout=subprocess.PIPE) # formail(1) from procmail
        text, _ = p.communicate(text)
        is_real_path = False
        fd, path = tempfile.mkstemp(suffix='mbox')
        os.write(fd, text)
        os.close(fd)
        try:
            mbox = mailbox.mbox(path, create=False)
            for message in mbox:
                payload = message.get_payload()
                while isinstance(payload, list):
                    payload = payload[0].get_payload()
                mtext = payload.encode('utf-8')
                received = message['Received']
                if received is None:
                    print(metadata['path'])
                    print(message)
                    die
                mid = message['Message-ID'] or '??message with no Message-ID'
                _, rdate = received.rsplit(';', 1)
                date = email.utils.parsedate_to_datetime(rdate)
                # "If the input date has a timezone of -0000, the datetime will be a naive datetime"
                # ^- WTF
                if date.tzinfo is None:
                    date.tzinfo = datetime.timezone(0)
                new_metadata = {'date': date, 'path': metadata['path'] + ' ' + mid, **metadata}
                yield from walk_file_nocontainer(new_metadata, mtext)
        finally:
            os.unlink(path)

def walk_tree(path):
    seen_exactly_set = set()
    for dirpath, dirnames, filenames in os.walk(path):
        for filename in filenames:
            path = os.path.join(dirpath, filename)
            if os.path.isfile(path): # not, say, a symlink
                metadata = {'path': path, 'seen_exactly': seen_exactly_set}
                with open(path, 'rb') as fp:
                    text = fp.read()
                yield from walk_file(metadata, text, is_real_path=True)

for x in walk_tree(sys.argv[1]):
    #print(x)
    pass
