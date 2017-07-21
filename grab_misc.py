import os, sys, tempfile, mailbox, datetime, subprocess, json, threading, queue
import email, email.parser, email.policy
import multiprocessing
import util
from util import assert_, decode, warn, warnx
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
            # mutability/power marking (must be present)
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
            (?P<extraheader>
                [0-9]{3}[a-z]?\.\ [^\n]*\n
            )
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
                (?:
                    # any number of lines starting like this
                    [a-zA-Z\.\( ][^\n]*(?:\n|$)
                )*
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
    b'1504': lambda text: text.replace(b'\nBobTHJ', b'\n  BobTHJ'),
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
        if g['history'] is not None:
            thehist = decode(g['thehist'])
            thehist = regex.sub('The following section is not a portion of the report:.*', '', thehist, flags=regex.S) # lol, old scam
            history = list(split_history(thehist))
        if expect_history and not history:
            if early_rulenum not in {b'2385', b'2119', b'2001'}:
                with warnx():
                    print(repr(g))
                    print('full: {{{')
                    print(util.highlight_spaces(decode(text)))
                    print('}}}')
                    print('^- no history in this FLR entry')
        text = g['text'] or b''
        inumber = int(g['number'])
        extraheader = g['extraheader'] or b''
        if extraheader:
            _extratitle, text, extraheader = fix_oldformat_header(inumber, text, extraheader.rstrip())

        data = {
            'number': inumber,
            'revnum': decode(g['revnum']) if g['revnum'] else None,
            'title': decode(g['title']) if g['title'] else None,
            'header': decode(g['header']),
            'extra': decode(extraheader) if extraheader else None,
            'text': decode(text),
            'annotations': decode(g['annotations']) or None,
            'history': history,
        }
        yield data

def split_history(history):
    history = history.strip()
    if history:
        for line in regex.split('\n(?!  )', history):
            yield regex.sub('\s+', ' ', line)

def fix_oldformat_header(inumber, text, header):
    header = header.rstrip()
    m = regex.match(b'(\s*(.*?)\.\s*)(.*)$', header)
    header_num, numletter, header_text = m.groups()
    if inumber >= 319 and numletter not in {b'376a', b'330', b'436', b'364a', b'377a'}:
        # 123. Title
        #      Text text text
        # keep whole header
        title = header_text
    else:
        # 123. Text text text
        header = header_num
        title = None
        text = b' ' * len(header_num) + header_text + b'\n' + text
    return title, text, header
fofr_regex = regex.compile(br'''
    (?<=\n|^)
    (?P<full>
        (?P<header>
            (?P<number>[0-9]{3})
            (?P<letter>[a-z]?)
            \.\s*[^\n]*
        )
        \n
        (?P<text>
            (?:
                (?:[ \t][^\n]*|)(?:\n|$) # indented or blank line
            )*
        )
    )
''', regex.M | regex.S | regex.X)
def find_oldformat_rules(filetext, seen_exactly_dict):
    for m in fofr_regex.finditer(filetext):
        g = m.groupdict()
        if g['full'] in seen_exactly_dict:
            continue
        seen_exactly_dict[g['full']] = True
        inumber = int(g['number'])
        title, text, header = fix_oldformat_header(inumber, g['text'], g['header'])
        data = {
            'number': inumber,
            'revnum': None,
            'title': decode(title) if title else None,
            'header': decode(header),
            'extra': decode(g['number'] + g['letter']) if g['letter'] else None,
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

def parse_file(metadata, text):
    new_metadata = metadata.copy()
    del new_metadata['seen_exactly']
    if 'rcslog' in new_metadata:
        del new_metadata['rcslog']
        del new_metadata['rcsauthor']
    assert isinstance(text, bytes)
    #print(metadata['path'])
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
                    with warnx():
                        print('full: {{{')
                        print(util.highlight_spaces(decode(bit)))
                        print('}}}',)
                        print('^-', w)
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
            yield from parse_file(metadata, rest)
        return
    elif b'THE RULES OF INTERNOMIC' in text:
        # this is ... a fake ruleset!
        return

    else: # not a ruleset
        if 'rcslog' in metadata and 'current_flr.txt,v' in metadata['path']:
            print(repr(text))
            raise Exception("this should be a flr but doesn't match")
    for data in find_rules(metadata['path'], text, metadata['seen_exactly']):
        yield {'meta': new_metadata, 'data': data}

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
                date = date.replace(tzinfo=datetime.timezone.utc)
            else:
                date = date.astimezone(datetime.timezone.utc)
            new_metadata = {**metadata, 'date': date.timestamp(), 'path': metadata['path'] + '@message-id:' + mid}
            yield (new_metadata, payload)
        return
    yield (metadata, text)

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

if True:
    queue = queue.Queue(20)
    class WalkThread(threading.Thread):
        def run(self):
            for x in walk_tree(inpath):
                queue.put(x)
            queue.put(None)
    WalkThread().start()
    def queue_read():
        while True:
            x = queue.get()
            if x is None: break
            yield x
    it = queue_read()
else:
    it = walk_tree(inpath)

with open(outpath, 'w') as gp:
    gp.write('[\n')
    first = True
    for x in it:
        for y in parse_file(*x):
            if not first: gp.write(',')
            first = False
            json.dump(y, gp)
            gp.write('\n')
    gp.write(']')
