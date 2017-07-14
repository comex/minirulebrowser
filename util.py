import regex, os, sys, datetime, functools

def normalize(rule_text):
    if len(rule_text) > 100000:
        raise Exception('this is definitely not a rule text')
    return regex.sub(b'[^a-z0-9]*', '', rule_text.lower())

def decode(binary):
    return binary.decode('utf-8')

def assert_(cond):
    if not cond:
        raise AssertionError

FATAL_WARNINGS = True
def warn(x):
    warnlines(x)
def warnlines(*xs):
    full = 'warning: ' + '\n'.join(map(str, xs))
    print(full, file=sys.stderr)
    if FATAL_WARNINGS: raise Exception

def highlight_spaces(text):
    return regex.sub('[^ -~\n]+', lambda m: repr(m.group(0))[1:-1], text).replace(' ', '\x1b[7m \x1b[0m')

mboxcl2_regex = regex.compile(b'From (?:[^\n]|\n[^\n])+\nContent-Length: ([0-9]+)[ \t]*(?=\n).*?\n\n', regex.S)
mboxcl2_vague_regex = regex.compile(b'\nFrom [^\n]* [0-9]{1,2} [0-9]{2}:[0-9]{2}:[0-9]{2} [0-9]{4}\n')
mboxcl2_justfrom = regex.compile(b'\n*(?:$|From )')
def iter_mboxcl2ish(text):
    # why the fuck is there no easy way to parse mboxcl2,
    # i.e. taking into account Content-Length
    # formail (part of procmail) can do it but for some bizarre reason it will
    # *either* treat the input as a single message and add '>' escaping
    # (default), or split messages and not add escaping (-s), but not both.
    # you can pass -s argv to make it invoke a command for each message, but
    # that's sloow
    pos = 0
    while pos != len(text):
        if text[pos:pos+1] == b'\n':
            pos += 1
            continue
        m = mboxcl2_regex.match(text, pos)
        if text[pos:pos+5] != b'From ':
            print(repr(text[pos:pos+1000]))
            raise Exception('wat')
        if m is not None:
            content_length = int(m.group(1))
            hdrend = m.end()
            endpos = m.end() + content_length
            if not mboxcl2_justfrom.match(text, endpos):
                # this could be because it has quoted Froms,
                # but agora_vanyel0/agora/proto/10 has one message that's just /completely/ wrong
                # print('Content-Length was bogus!', repr(text[endpos:endpos+20]), file=sys.stderr)
                # anyway, fall back on search
                m = None
        if m is None:
            # ack, no content-length
            # but still...
            n = mboxcl2_vague_regex.search(text, pos + 1)
            if n is not None:
                endpos = n.start()
            else:
                endpos = len(text)
            hdrend = pos # xxx

        #print('pos=', pos, 'gotcl=', m is not None, 'hdrend=', hdrend, 'endpos=', endpos, '@hdrend=', repr(text[hdrend:hdrend+10]))
        msgtext = text[pos:endpos]
        yield msgtext
        pos = endpos
        last_hdrend = hdrend

FIXED = {
    'Jan. or Feb. 1994': '1 January 1994',
    'Apr. or May 1994': '1 April 1994',
    '12 Februray 2016': '12 February 2016', # [sic]
}
@functools.lru_cache(None)
def strptime_ruleset(text):
    text = text.strip()
    text = FIXED.get(text, text)
    for fmt in ['%d %B %Y', '%b. %d %Y', '%b. %Y', '%b %d %Y', '%d %b %Y', '%b. %d %Y %H:%M:%S %z', '%b %d. %Y']:
        try:
            return datetime.datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    raise ValueError('%r could not be parsed as a date' % (text,))

NUMBERS_STOPPED_CHANGING_AT = strptime_ruleset('1 November 1994')
FOUNDING_DATE = strptime_ruleset('28 June 1993')
@functools.lru_cache(None)
class Annotation(object):
    def __init__(self, text):
        text = text.strip()
        self.text = text
        self.date = None
        self.revnum = None
        self.renumber = None
        self.is_create = False
        self.initial_num = None
        self.is_indeterminate = text in {'...', '..', '[orphaned text]'} or '??? by' in text
        text = regex.sub(', (?:(?:sus?bs?tantial|cosmetic).*)?(?:,? \(unattributed\))?$', '', text)
        m = regex.match('(.*), (?:ca\. )?(.*?)\.?$', text)
        if m:
            if m.group(2) not in {'date unknown', 'datu unknown', 'XXXDATEHERE'}:
                try:
                    self.date = strptime_ruleset(m.group(2))
                except ValueError as e:
                    warn('%s, while parsing annotation %r' % (str(e), text))
            text = m.group(1)
        if regex.match('ini?t?ial ', text, regex.I):
            self.is_create = True
            self.revnum = '0'
            self.date = FOUNDING_DATE # override any existing date
        if regex.match('created|enacted', text, regex.I):
            self.is_create = True
            self.revnum = '0'
        if self.is_create:
            m = regex.match('(.*)Rule ([0-9]+)', text, regex.I)
            if m and ' by' not in m.group(1):
                self.initial_num = int(m.group(2))
        ms = regex.findall('([A-Za-z]+)\((.*?)\)', text)
        if ms:
            assert self.revnum is None
            kind, num = ms[0]
            if kind.lower() not in {'amended', 'transmuted', 'amedned'}:
                warn("revnum attached to something other than 'amended' or 'transmuted': %r in %r" % (kind, text))
            self.revnum = num
            if len(ms) > 1:
                warn('got multiple revnums? %s <- %s' % (ms, text))
        m = regex.match('(?:renumbered|number changed)(?: from ([0-9]+)(?:\/[^ ]*)?)? to ([0-9]+)(?:\/[^ ]*)?$', text, regex.I)
        if m:
            old_num = int(m.group(1)) if m.group(1) else None
            new_num = int(m.group(2))
            self.renumber = (old_num, new_num)
        m = regex.search('(?:amended|transmuted).*by Proposal ([0-9]+), (?:ca\. )?(.* 199[34])', text, regex.I)
        if m and self.date < NUMBERS_STOPPED_CHANGING_AT:
            assert self.renumber is None
            self.renumber = (None, int(m.group(1)))

    def __repr__(self):
        return 'Annotation(date=%s, revnum=%r, renumber=%s, initial_num=%s, text=%r)' % (self.date, self.revnum, self.renumber, self.initial_num, self.text)

