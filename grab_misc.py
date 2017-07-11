import os, sys, tempfile, mailbox, datetime, subprocess, json
import email, email.parser, email.policy
import util
from util import assert_, decode
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
                .*?
            )
            (?&newline)
            (?&newline)
        )?
        # end on something that is not indented, nor an old-fashioned numbered rule
        (?![ 0-9])
    )
''', regex.M | regex.S | regex.X)
def find_stdformat_rules(text, seen_exactly_dict):
    for m in fsfr_regex.finditer(text):
        #print('yaeh', text[m.end():m.end()+100])
        g = m.groupdict()
        full = g['full']
        if full in seen_exactly_dict:
            continue
        seen_exactly_dict[full] = True
        history = None
        if g['history'] is not None:
            history = list(split_history(decode(g['thehist'])))
        data = {
            'number': int(g['number']),
            'revnum': decode(g['revnum']) if g['revnum'] else None,
            'title': decode(g['title']) if g['title'] else None,
            'header': decode(g['header']),
            'extra': decode(g['extra']) if g['extra'] else None,
            'text': decode(g['text']),
            'annotations': decode(g['annotations']) or None,
            'history': history,
        }
        yield data

def split_history(history):
    for line in regex.split('\n(?!  )', history):
        yield regex.sub('\s+', ' ', line)

def find_oldformat_rules(filetext, seen_exactly_dict):
    for full, header, number, letter, text in regex.findall(b'^((([0-9]{3})([a-z]?)\.\s+)(.*?))\n[ \t]*\n', filetext, regex.M | regex.S):
        if full in seen_exactly_dict:
            continue
        seen_exactly_dict[full] = True
        title = None
        inumber = int(number)
        if inumber >= 319 and inumber not in (330, 436):
            # have title
            title, text = text.split(b'\n', 1)
            header += title
            title = title.rstrip(b':')
        else:
            text = b' ' * len(header) + text
            header = header.rstrip()
        data = {
            'number': inumber,
            'revnum': None,
            'title': decode(title),
            'header': decode(header),
            'extra': decode(number + letter) if letter else None,
            'text': decode(text),
            'annotations': None,
            'history': None,
        }
        yield data

def find_rules(path, text, seen_exactly_dict):
    if 'theses/' in path or 'cfj/' in path or path.endswith('/discussion'):
        return # some fake rules here
    if 'usenet0/rga' in path:
        yield from find_oldformat_rules(text, seen_exactly_dict)
    yield from find_stdformat_rules(text, seen_exactly_dict)

def walk_file_nocontainer(metadata, text):
    new_metadata = metadata.copy()
    del new_metadata['seen_exactly']
    if 'rcslog' in new_metadata:
        del new_metadata['rcslog']
        del new_metadata['rcsrev']
    assert isinstance(text, bytes)
    #print(metadata['path'])
    m = regex.match(b'\s*THE (FULL |SHORT |)LOGICAL RULESET\n\n.*?(END OF THE [^ ]* LOGICAL RULESET\s*|\s*$)', text, regex.S)
    if m:
        # this is a ruleset!
        have_rulenums = []
        ruleset = m.group(0)
        ruleset_bits = regex.split(b'\n------------------------------+\n', text)
        for bit in ruleset_bits:
            x = ('rbit', bit)
            rulenum = metadata['seen_exactly'].get(x)
            if rulenum is None:
                it = iter(find_rules(metadata['path'], bit, {}))
                if bit.startswith(b'\nRule'):
                    data = next(it)
                    rulenum = data['number']
                    yield {'meta': new_metadata, 'data': data}
                else:
                    rulenum = False
                # shouldn't have any others
                try:
                    data = next(it)
                except StopIteration:
                    pass
                else:
                    raise Exception('got extra rule %r in bit %r' % (data, bit))
            metadata['seen_exactly'][x] = rulenum
            if rulenum is not False:
                have_rulenums.append(rulenum)
        # explicit repeal annotations in RCS?
        if 'rcslog' in metadata:
            revnum = int(metadata['rcsrev'].split(b'.')[-1])
            if revnum > 801 and revnum != 969:
                # split by semicolon, but not semicolons in parens
                logs = regex.findall(br';\s*((?:\([^\)]*\)|[^;\(]+)*)', metadata['rcslog'])
                for log in logs:
                    log = log.strip()
                    if log in {b'formatting', b'update xrefs', b'lots of formatting fixes'}:
                        continue # old stuff I put in
                    n = regex.match(b'Rule ([0-9]+) (?:\([^\)]*\) )?repealed', log)
                    if not n:
                        raise Exception('unknown RCS annotation %r' % log)
                    number = int(n.group(1))
                    yield {'meta': new_metadata, 'data': {
                        'number': number,
                        'revnum': None,
                        'title': None,
                        'header': None,
                        'extra': None,
                        'text': None,
                        'annotations': None,
                        'history': [decode(log)],
                    }}
        # repeals?
        yield {'meta': new_metadata, 'data': {'no_rules_except': have_rulenums}}

        # handle any remaining data
        if m.end() < len(text):
            yield from walk_file_nocontainer(metadata, text[m.end():])
        return
    else: # not a ruleset
        if 'rcslog' in metadata and 'current_flr.txt,v' in metadata['path']:
            print(repr(text))
            raise Exception('bad flr?')
    for data in find_rules(metadata['path'], text, metadata['seen_exactly']):
        yield {'meta': new_metadata, 'data': data}

utc = datetime.timezone(datetime.timedelta())
def walk_file(metadata, text):
    print('>>>', metadata['path'])
    if metadata['path'].endswith(',v'):
        # looks like rcs
        rcs = RCSFile(text)
        for revinfo in rcs.get_revisions():
            new_metadata = {**metadata,
                'date': revinfo['date'].timestamp(),
                'path': metadata['path'] + '@RCS:%s' % decode(revinfo['num']),
                'rcslog': revinfo['log'],
                'rcsrev': revinfo['num'],
            }
            text = b'\n'.join(revinfo['text'])
            yield from walk_file(new_metadata, text)
        return
    if regex.match(b'From [^\n]+\n[A-Z][^ ]*:', text):
        is_massive = metadata['path'].endswith('agora-official.mbox')
        parser = email.parser.BytesParser(policy=email.policy.default)
        if is_massive:
            approx_count = text.count(b'\n\nFrom ')
        i = 0
        for mraw in util.iter_mboxcl2ish(text):
            i += 1
            if is_massive:
                if i % 100 == 0:
                    print('%d/~%d messages' % (i, approx_count))
                if b'LOGICAL RULESET' not in mraw:
                    # email parser is slow, and over this period of time we should be fine just looking at published rulesets
                    continue
            message = parser.parsebytes(mraw)
            payload = message.get_payload()
            while isinstance(payload, list):
                payload = payload[0].get_payload()
            mtext = payload.encode('utf-8')
            unixfrom = message.get_unixfrom()
            #print(mraw)
            #print(unixfrom)
            unixdate = unixfrom.split(' ', 2)[2].strip()
            assert_(unixdate)
            mid = message['Message-ID'] or '??message with no Message-ID'
            date = email.utils.parsedate_to_datetime(unixdate)
            # "If the input date has a timezone of -0000, the datetime will be a naive datetime"
            # ^- WTF
            if date.tzinfo is None:
                date = date.replace(tzinfo=utc)
            else:
                date = date.astimezone(utc)
            new_metadata = {'date': date.timestamp(), 'path': metadata['path'] + ' ' + mid, **metadata}
            yield from walk_file_nocontainer(new_metadata, mtext)
        return
    yield from walk_file_nocontainer(metadata, text)

def walk_tree(path):
    seen_exactly_dict = {}
    it = os.walk(path) if os.path.isdir(path) else [('', [], [path])]
    for dirpath, dirnames, filenames in it:
        for filename in filenames:
            path = os.path.join(dirpath, filename)
            if os.path.isfile(path): # not, say, a symlink
                metadata = {'path': path, 'seen_exactly': seen_exactly_dict}
                with open(path, 'rb') as fp:
                    text = fp.read()
                yield from walk_file(metadata, text)

if len(sys.argv) > 1:
    inpath, outpath = sys.argv[1], sys.argv[2]
else:
    inpath, outpath = 'archives', 'out_misc.json'
with open(outpath, 'w') as gp:
    gp.write('[\n')
    first = True
    for x in walk_tree(inpath):
        if not first: gp.write(',')
        first = False
        json.dump(x, gp)
        gp.write('\n')
    gp.write(']')
