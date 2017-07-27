import os, sys, tempfile, mailbox, datetime, subprocess, json, functools
from functools import partial
import email, email.parser, email.policy
import util
from util import assert_, decode, warn, warnx
import regex # not re
from rcs import RCSFile

def parsedate_to_datetime(unixdate):
    date = email.utils.parsedate_to_datetime(unixdate)
    # "If the input date has a timezone of -0000, the datetime will be a naive datetime"
    # ^- WTF
    if date.tzinfo is None:
        date = date.replace(tzinfo=datetime.timezone.utc)
    else:
        date = date.astimezone(datetime.timezone.utc)
    return date

my_texts = {}
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
                    [a-zA-Z\.\(\[ ][^\n]*(?:\n|$)
                )*
            )
        )?
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
def find_stdformat_rules(text, expect_history=False):
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
        rtext = g['text'] or b''
        inumber = int(g['number'])
        extraheader = g['extraheader'] or b''
        if extraheader:
            _extratitle, rtext, extraheader = fix_oldformat_header(inumber, rtext, extraheader.rstrip())

        data = {
            'number': inumber,
            'revnum': decode(g['revnum']) if g['revnum'] else None,
            'title': decode(g['title']) if g['title'] else None,
            'header': decode(g['header']),
            'extra': decode(extraheader) if extraheader else None,
            'text': decode(rtext),
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
def find_oldformat_rules(filetext):
    for m in fofr_regex.finditer(filetext):
        g = m.groupdict()
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

def find_rules_mode_for_path(path):
    stdformat = True
    oldformat = False
    expect_history = False
    if 'theses/' in path or 'cfj/' in path or path.endswith('/discussion'):
        stdformat = False
    elif 'usenet0/rga' in path:
        oldformat = True
    elif 'current_flr.txt' in path:
        expect_history=True
    expect_history = 'current_flr.txt' in path
    return stdformat, oldformat, expect_history

def find_rules(mode, bit):
    stdformat, oldformat, expect_history = mode
    if oldformat:
        yield from find_oldformat_rules(bit)
    if stdformat:
        yield from find_stdformat_rules(bit, expect_history=expect_history)


@functools.lru_cache(None)
def find_rules_in_flr_bit(mode, bit):
    found = list(find_rules(mode, bit))
    w = None
    ret = []
    if regex.match(b'\n*Rule [0-9]', bit):
        for data in found:
            ret.append(data)
        if len(found) > 1:
            if b'Rule 2389/0' not in bit:
                w = 'got multiple rules in FLR bit'

            rulenum = None
        elif len(found) == 0:
            if b'Rule 2386/0' not in bit:
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
    return ret
def walk_doc(metadata, text):
    new_metadata = metadata.copy()
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
        ruleset = m.group(0)
        ruleset_bits = regex.split(b'\n------------------------------+|====================+\n', text[lr_start:lr_end])
        have_rulenums = []
        mode = find_rules_mode_for_path(metadata['path'])
        for datas in map(partial(find_rules_in_flr_bit, mode), ruleset_bits):
            for data in datas:
                if data['number'] is not None:
                    have_rulenums.append(data['number'])
                yield {'meta': new_metadata, 'data': data}
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
            yield from walk_doc(metadata, rest)
        return
    elif b'THE RULES OF INTERNOMIC' in text:
        # this is ... a fake ruleset!
        return

    else: # not a ruleset
        if 'rcslog' in metadata and 'current_flr.txt,v' in metadata['path']:
            with warnx():
                print(repr(text))
                print("this should be a flr but doesn't match")
        for data in find_rules(find_rules_mode_for_path(metadata['path']), text):
            yield {'meta': new_metadata, 'data': data}

email_parser = email.parser.BytesParser(policy=email.policy.default)
def walk_email(metadata, mraw):
    if b'LOGICAL RULESET' not in mraw:
        # email parser is slow, and over this period of time we should be fine just looking at published rulesets
        return
    message = email_parser.parsebytes(mraw)
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
    date = parsedate_to_datetime(unixdate)
    new_metadata = {**metadata, 'date': date.timestamp(), 'path': metadata['path'] + '@message-id:' + mid}
    yield from walk_doc(new_metadata, payload)

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
                'rcsauthor': revinfo['author'],
            }
            text = b'\n'.join(revinfo['text'])
            yield from walk_file(new_metadata, text)
        return
    if regex.match(b'From [^\n]+\n[A-Z][^ ]*:', text):
        is_massive = metadata['path'].endswith('agora-official.mbox')
        if is_massive:
            approx_count = text.count(b'\n\nFrom ')
        i = 0
        for mraw in util.iter_mboxcl2ish(text):
            yield from walk_email(metadata, mraw)
            i += 1
            if is_massive:
                if i % 100 == 0:
                    print('%s: %d/~%d messages' % (metadata['path'], i, approx_count))
                    continue
        return
    yield from walk_doc(metadata, text)

def file_paths_in(path):
    it = os.walk(path) if os.path.isdir(path) else [('', [], [path])]
    for dirpath, dirnames, filenames in it:
        for filename in filenames:
            if filename.endswith('.swp'):
                continue
            path = os.path.join(dirpath, filename)
            if os.path.isfile(path): # not, say, a symlink
                yield (path, filename)

YYYYMMDD_REGEX = regex.compile('(?:199|200)[0-9]{5}')
def walk_filepath(x):
    (path, basename) = x
    with open(path, 'rb') as fp:
        text = fp.read()
    meta = {'path': path}
    m = YYYYMMDD_REGEX.search(basename)
    if m:
        meta['date'] = datetime.datetime.strptime(m.group(0), '%Y%m%d').astimezone(datetime.timezone.utc).timestamp()
    if text.startswith(b'Path: nntp') or text.startswith(b'Newsgroups: '):
        datestr = regex.search(b'Date: (.*)', text).group(1)
        date = parsedate_to_datetime(datestr.decode('utf-8'))
        meta['date'] = date.timestamp()
    yield from walk_file(meta, text)

def walk_path(path):
    for ret in map(walk_filepath, file_paths_in(path)):
        yield from ret

if __name__ == '__main__':
    if len(sys.argv) > 1:
        inpath, outpath = sys.argv[1], sys.argv[2]
    else:
        inpath, outpath = 'archives', 'out_misc.json'


    with open(outpath, 'w') as gp:
        gp.write('[\n')
        first = True
        seen_ids = set()
        dummy = []
        for x in walk_path(inpath):
            if id(x['data']) in seen_ids:
                continue
            seen_ids.add(id(x['data']))
            dummy.append(x)

            if not first: gp.write(',')
            first = False
            json.dump(x, gp)
            gp.write('\n')
        gp.write(']')
