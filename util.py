import regex, os

def normalize(rule_text):
    if len(rule_text) > 100000:
        raise Exception('this is definitely not a rule text')
    return regex.sub(b'[^a-z0-9]*', '', rule_text.lower())

def decode(binary):
    return binary.decode('utf-8', 'replace')

def assert_(cond):
    if not cond:
        raise AssertionError

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
                print('Content-Length was bogus!', repr(text[endpos:endpos+20]), file=sys.stderr)
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
