import os, sys, datetime, functools, traceback, atexit
from collections import namedtuple
try:
    import yaml
except:
    print('*** Did you install the dependencies? try %s -m pip install -r requirements.txt' % (sys.executable,))
    raise
try:
    import regex as re
except ImportError:
    print("warning: couldn't import 'regex'; using 're' instead for pypy compat", file=sys.stderr)
    import re

try:
    import pyximport
except ImportError:
    print("warning: couldn't import 'pyximport' (Cython); using pure-Python instead", file=sys.stderr)
    def normalize_rule_text_inner(text):
        return normalize_rule_text_inner_python(text)
else:
    pyximport.install()
    from normalize_rule_text import normalize_rule_text_inner as normalize_rule_text_inner
def normalize_rule_text(text):
    if len(text) > 100000:
        raise Exception('this is definitely not a rule text')
    text = text.rstrip()
    if text.endswith('*)'):
        text = re.sub('\(\*was: .*?\*\)\s*$', '', text, flags=re.I)
    return normalize_rule_text_inner(text)

def normalize_rule_text_inner_python(text):
    return re.sub('[^a-z0-9]', '', text.lower()).encode('utf-8')

def decode(binary):
    return binary.decode('utf-8')

def assert_(cond):
    if not cond:
        raise AssertionError

FATAL_WARNINGS = True
got_any_warnings = False
def warn(x):
    with warnx():
        print(x)
class warnx:
    def __enter__(self):
        print('warning: ', end='')
    def __exit__(self, ty, val, traceback):
        if ty is not None: return False
        global got_any_warnings
        got_any_warnings = True
        return False
@atexit.register
def warn_cleanup():
    if got_any_warnings:
        if FATAL_WARNINGS: raise Exception('got warnings w/ fatal warnings enabled')

def highlight_spaces(text):
    return re.sub('[^ -~\n]+', lambda m: repr(m.group(0))[1:-1], text).replace(' ', '\x1b[7m \x1b[0m')

mboxcl2_regex = re.compile(b'From (?:[^\n]|\n[^\n])+\nContent-Length: ([0-9]+)[ \t]*(?=\n).*?\n\n', re.S)
mboxcl2_vague_regex = re.compile(b'\nFrom [^\n]* [0-9]{1,2} [0-9]{2}:[0-9]{2}:[0-9]{2} [0-9]{4}\n')
mboxcl2_justfrom = re.compile(b'\n*(?:$|From )')
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
    'Jun. or Jul. 1999': '1 June 1999',
    'Mar. or Apr. 2000': '1 March 2000',
    'Apr. or May 1994': '1 April 1994',
    '12 Februray 2016': '12 February 2016', # [sic]
    '16 May 011': '16 May 2011',
    '14 Augut 2012': '14 August 2012',
    '9 Febraury 2013': '9 February 2013',
    '11 Jaunuary 2013': '11 January 2013',
    '27 Apirl 2013': '27 April 2013',
    '24 Janurary 2014': '24 January 2014',
    '26 <ay 2009': '26 May 2009',
    '16 May 2011:': '16 May 2011',
    'July 1993': '1 July 1993',
    'Mar. 19 198': '19 March 1998',
    'Feb. 6 196': '6 February 1996',
    'by Agora March 26 1998': '26 March 1998',
}
@functools.lru_cache(None)
def strptime_ruleset(text):
    text = text.strip()
    text = FIXED.get(text, text)
    text = re.sub('[\.,]', '', text)
    for fmt in ['%d %B %Y', '%b %d %Y', '%b %Y', '%d %b %Y', '%b %d %Y %H:%M:%S %z']:
        try:
            return datetime.datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    raise ValueError('%r could not be parsed as a date' % (text,))

#NUMBERS_STOPPED_CHANGING_AT = strptime_ruleset('24 October 1994')
FOUNDING_DATE = strptime_ruleset('28 June 1993')
REVNUM_FIXUPS = {
    'e': '3',
}
END_STUFF_RE = re.compile(r'(?:,?\s*(?:sus?bs?tantial|cosmetic|\([^\)]+\)))*$')
_1996_RE = re.compile('(.*), (?:ca\. )?([^,]* 1996)')
OTHER_DATE_RE = re.compile(r'(.*), (?!19[0-9]{2}|20[0-9]{2})(?:ca\. )?(.*?)\.?$')
INITIAL_RE = re.compile(r'ini?t?ial ', re.I)
CREATED_RE = re.compile(r'created|\benacted', re.I)
# XXX handle reenacts! rulekeepor is dead atm
RULE_N_RE = re.compile(r'(.*)Rule ([0-9]+)', re.I)
REVNUM_NOTE_RE = re.compile(r'([A-Za-z]+)\(([^\(\) ]*?)\)')
REVNUM_RE = re.compile(r'[0-9]+(?:\.[0-9]+)?$')
NUMERIC_RE = re.compile(r'[0-9]+$')
AMENDED_BY_PROP_RE = re.compile('(amended|transmuted|mutated|power changed|\?\?\?)?.*by pro[a-z]+ ([0-9][^ ]+)', re.I)
RENUMBERED_RE = re.compile(r'(?:renumbered|number changed)(?: from ([0-9]+)(?:\/[^ ]*)?)? to ([0-9]+)', re.I)
BY_RE = re.compile(r'\bby ([^,\(]*)')
@functools.lru_cache(None)
class Annotation(object):
    __slots__ = ['text', 'date', 'revnum', 'is_create', 'prev_num', 'cur_num', 'num_changed', 'proposal_num', 'is_indeterminate', '_guessed_num', '_guessed_revnum', 'latent', '_sig', '_entry']

    def __init__(self, text):
        if text is None:
            return
        text = text.strip()
        self.text = text
        self.date = None
        self.revnum = None
        self.is_create = False
        self.prev_num = None
        self.cur_num = None
        self.num_changed = False
        self.proposal_num = None
        self.is_indeterminate = text in {'...', '..', '[orphaned text]'} or '??? by' in text
        text = END_STUFF_RE.sub('', text)
        m = _1996_RE.match(text) or OTHER_DATE_RE.match(text)
        if m:
            if m.group(2) not in {'date unknown', 'datu unknown', 'XXXDATEHERE'}:
                try:
                    self.date = strptime_ruleset(m.group(2))
                except ValueError as e:
                    warn('%s, while parsing annotation %r' % (str(e), text))
            text = m.group(1)
        if INITIAL_RE.match(text):
            self.is_create = True
            self.revnum = '0'
            self.date = FOUNDING_DATE # override any existing date
        if CREATED_RE.match(text):
            self.is_create = True
            self.revnum = '0'
        if self.is_create:
            m = RULE_N_RE.match(text)
            if m and ' by' not in m.group(1):
                self.cur_num = int(m.group(2))
        ms = REVNUM_NOTE_RE.findall(text)
        if ms:
            assert self.revnum is None
            kind, revnum = ms[0]
            if kind.lower() not in {'amended', 'transmuted', 'amedned', 'amneded', 'amendd', 'repealed', 'retitled'}:
                warn("revnum attached to something other than 'amended' or 'transmuted' (or 'repealed' or 'retitled' but those are weird): %r in %r" % (kind, text))
            revnum = REVNUM_FIXUPS.get(revnum, revnum)
            if REVNUM_RE.match(revnum):
                self.revnum = revnum
            elif revnum in {'???', ''}:
                # Amended(), Amended(???)
                pass
            else:
                warn("weird revision number %r in %r" % (num, text))
            if len(ms) > 1:
                warn('got multiple revnums? %s <- %s' % (ms, text))
        m = RENUMBERED_RE.match(text)
        if m:
            self.prev_num = int(m.group(1)) if m.group(1) else None
            self.cur_num = int(m.group(2))
            self.num_changed = True
        m = AMENDED_BY_PROP_RE.search(text)
        if m:
            was_atmp = bool(m.group(1))
            self.proposal_num = m.group(2)
            try:
                num = int(self.proposal_num)
            except ValueError:
                pass
            else:
                if num < 1268 and was_atmp:
                    assert_(self.cur_num is None)
                    self.cur_num = num
                    self.num_changed = True
                    if self.revnum is None:
                        self.revnum = '0.%d' % self.cur_num

    def copy(self):
       c = self.__class__(None)
       c.text = self.text
       c.date = self.date
       c.revnum = self.revnum
       c.is_create = self.is_create
       c.prev_num = self.prev_num
       c.cur_num = self.cur_num
       c.num_changed = self.num_changed
       c.proposal_num = self.proposal_num
       c.is_indeterminate = self.is_indeterminate
       return c

    @property
    def sig(self):
        try:
            return self._sig
        except AttributeError:
            self._sig = self._calc_sig()
            return self._sig
    def _calc_sig(self):
        # get a value such that if two sigs are equal, they probably represent
        # the same change (even given corrections) OR are just
        # indistinguishable by text alone (e.g. two retitlings, see knit.py)
        if self.is_create:
            return ('0', 'create')
        if re.search('(?:renumbered|number changed)', self.text, re.I):
            distinguisher = 'renumber'
        elif re.search('(?:retitled|title changed)', self.text, re.I):
            distinguisher = 'retitle'
        elif re.search('(?:transmuted|power changed|from MI=)', self.text, re.I):
            distinguisher = 'repower'
        else:
            # dunno
            distinguisher = None
        if self.proposal_num is not None:
            doer = ('proposal', self.proposal_num)
        else:
            m = BY_RE.search(self.text)
            if m:
                doer = m.group(1).rstrip()
            else:
                # dunno
                doer = None
        if (distinguisher is not None or self.revnum is not None) and doer is not None:
            return (self.revnum, distinguisher, doer)
        else:
            return self.text

    def __repr__(self):
        extra = ''
        if hasattr(self, '_guessed_num'):
            extra += ', _guessed_num=%r' % (self._guessed_num,)
        if hasattr(self, '_guessed_revnum'):
            extra += ', _guessed_revnum=%r' % (self._guessed_revnum,)
        return 'Annotation(date=%s, revnum=%r, prev_num=%s, cur_num=%s, is_create=%s, num_changed=%s, proposal_num=%s, text=%r%s)' % (self.date, self.revnum, self.prev_num, self.cur_num, self.is_create, self.num_changed, self.proposal_num, self.text, extra)

def datetime_from_timestamp(ts):
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc)
def datetime_from_date(date):
    return datetime.datetime.combine(date, datetime.time(tzinfo=datetime.timezone.utc))

Box = namedtuple('Box', ['value'])

def partition(func, iterable):
    yes = []
    no = []
    for item in iterable:
        if func(item):
            yes.append(item)
        else:
            no.append(item)
    return yes, no

def cmp(a, b):
    return (a > b) - (a < b)
