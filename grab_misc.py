import os, sys, tempfile, mailbox, datetime, subprocess, json, quopri
import email, email.parser, email.policy
import multiprocessing
import util
from util import assert_, decode, warn, warnlines
import regex # not re
from rcs import RCSFile

my_texts = {}
seen_exactly = set()
fsfr_regex = regex.compile(br'''
    (?<=\n|^) # start of line
    (?P<full>
        (?P<header>
            Rule\ (?P<number>[0-9]+)
            (?: # revision number?
                /(?P<revnum>[0-9]+)
            )?
            [^\n]*
            # mutability/power marking
            \([^\n\)]*\)
            (?: # committee?
                \ \[[^\]]*\]
            )?
        )
        (?P<newline>[ \t]*(?:\n|$))
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
        # main rule text; in some weird cases, could be missing
        (?:
            (?P<text>
                (?:
                    (?:[ \t][^\n]*|)(?:\n|$) # indented or blank line
                    | \[![^\]]*\]\n # [! ... ] annotations (I used these once)
                )*
            )
            (?&newline)?
        )?
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
                (?&newline)?
            )*
        )
        # there may be history
        (?P<history>
            (?:
                (?&newline)* # fudge for empty rules, as this is unlikely to be a misidentification
                H?istory:(?&newline)
            |
                # common error in the RCS history is to omit History:, starting directly with 'Created by'
                (?=Created\ by)
            )
            (?P<thehist>
                .*?
            )
        )?
        # end on something that is none of:
        # - indented
        # - an old-fashioned numbered rule
        # - an annotation
        # - a blank line
        (?&newline)*
        (?![ 0-9\[\n])
    )
''', regex.S | regex.X)
FIXUPS_FOR_RULENUM = {
    b'478': lambda text: text.replace(b'\nchannel to be a public forum.\n', b'\nchannel to be a public forum.]\n'),
    b'2136': lambda text: text.replace(b'presently actual contestants.\n', b'presently actual contestants.]\n'),
    b'2105': lambda text: text.replace(b'\nPERTH ->', b'\n PERTH ->'),
    b'1449': lambda text: text.replace(b'\nn    ', b'\n    '),
    b'665': lambda text: text.replace(b'on the illegal action would be retracted.]', b'on the illegal action would be retracted.'),
}
def find_stdformat_rules(text, seen_exactly_dict, expect_history=False):
    m = regex.search(b'Rule ([0-9]+)', text)
    early_rulenum = None
    if m:
        early_rulenum = m.group(1)
        action = FIXUPS_FOR_RULENUM.get(early_rulenum)
        if action:
            text = action(text)
    # fix CFJ annotations missing brackets altogether
    text = regex.sub(b'\n(CFJ [0-9]+[^\n]*:.*?)(?=\n\n)', br'\n[\1]', text, flags=regex.S)
    # --
    for m in fsfr_regex.finditer(text):
        #print('yaeh', text[m.end():m.end()+100])
        g = m.groupdict()
        full = g['full']
        if full in seen_exactly_dict:
            continue
        seen_exactly_dict[full] = True
        history = None
        if expect_history and g['history'] is None:
            if early_rulenum not in {b'2385', b'2119', b'2001'}:
                warnlines(
                    repr(g),
                    'full: {{{',
                    util.highlight_spaces(decode(text)),
                    '}}}',
                    '^- no history in this FLR entry',
                )
        if g['history'] is not None:
            thehist = decode(g['thehist'])
            thehist = regex.sub('The following section is not a portion of the report:.*', '', thehist, flags=regex.S) # lol, old scam
            history = list(split_history(thehist))

        data = {
            'number': int(g['number']),
            'revnum': decode(g['revnum']) if g['revnum'] else None,
            'title': decode(g['title']) if g['title'] else None,
            'header': decode(g['header']),
            'extra': decode(g['extra']) if g['extra'] else None,
            'text': decode(g['text'] or b''),
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
        if inumber >= 319 and inumber not in {330, 436}:
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
            'title': decode(title) if title else None,
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
    expect_history = 'current_flr.txt' in path
    yield from find_stdformat_rules(text, seen_exactly_dict, expect_history=expect_history)

def walk_file_nocontainer(metadata, text):
    new_metadata = metadata.copy()
    del new_metadata['seen_exactly']
    if 'rcslog' in new_metadata:
        del new_metadata['rcslog']
        del new_metadata['rcsauthor']
    assert isinstance(text, bytes)
    #print(metadata['path'])
    if b'22 October =' in text:
        print(repr(text))
        die
    m = regex.match(b'(.{,2048}\n)?THE (FULL |SHORT |)LOGICAL RULESET\n\n', text, regex.S)
    if m:
        # this is a ruleset!
        lr_start = m.end()
        n = regex.search(b'\nEND OF THE [^ ]* LOGICAL RULESET', text, pos=lr_start)
        if n:
            lr_end = n.end()
        else:
            lr_end = len(text)
        have_rulenums = []
        ruleset = m.group(0)
        ruleset_bits = regex.split(b'\n------------------------------+|====================+\n', text[lr_start:lr_end])
        for bit in ruleset_bits:
            x = ('rbit', bit)
            rulenum = metadata['seen_exactly'].get(x)
            if rulenum is None:
                found = list(find_rules(metadata['path'], bit, {}))
                w = None
                if regex.match(b'\n*Rule [0-9]', bit):
                    for data in found:
                        rulenum = data['number']
                        yield {'meta': new_metadata, 'data': data}
                    if len(found) > 1:
                        if '@RCS:1.1736' not in metadata['path']:
                            w = 'got multiple rules in FLR bit'

                        rulenum = None
                    elif len(found) == 0:
                        if b'Rule 2386/0' not in text:
                            w = 'got no rules in FLR bit'
                else:
                    if len(found) > 0:
                        w = 'got rule in weird FLR bit'
                    rulenum = False
                if w is not None:
                    warnlines(
                        'full: {{{',
                        util.highlight_spaces(decode(bit)),
                        '}}}',
                        '^- ' + w
                    )
            metadata['seen_exactly'][x] = rulenum
            if rulenum is not False:
                have_rulenums.append(rulenum)
        # explicit repeal annotations in RCS?
        if 'rcslog' in metadata and metadata['rcsauthor'] == 'comex':
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
        rest = text[lr_end:].lstrip()
        if rest:
            yield from walk_file_nocontainer(metadata, rest)
        return
    else: # not a ruleset
        if 'rcslog' in metadata and 'current_flr.txt,v' in metadata['path']:
            print(repr(text))
            raise Exception("this should be a flr but doesn't match")
    for data in find_rules(metadata['path'], text, metadata['seen_exactly']):
        yield {'meta': new_metadata, 'data': data}

utc = datetime.timezone(datetime.timedelta())
def walk_file(metadata, text):
    print('>>>', metadata['path'])
    if metadata['path'].endswith('.swp'):
        return # vim temporary file
    if metadata['path'].endswith(',v'):
        # looks like rcs
        rcs = RCSFile(text)
        for revinfo in rcs.get_revisions():
            new_metadata = {**metadata,
                'date': revinfo['date'].timestamp(),
                'path': metadata['path'] + '@RCS:%s' % decode(revinfo['num']),
                'rcslog': revinfo['log'],
                'rcsauthor': revinfo['author'],
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
                    print('%s: %d/~%d messages' % (metadata['path'], i, approx_count))
                if b'LOGICAL RULESET' not in mraw:
                    # email parser is slow, and over this period of time we should be fine just looking at published rulesets
                    continue
            message = parser.parsebytes(mraw)
            xmessage = message
            while xmessage.is_multipart():
                xmessage = xmessage.get_payload(0)
            payload = xmessage.get_payload(decode=True)
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
            new_metadata = {**metadata, 'date': date.timestamp(), 'path': metadata['path'] + '@message-id:' + mid}
            yield from walk_file_nocontainer(new_metadata, payload)
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
