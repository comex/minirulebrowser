import argparse, json, functools, copy
import regex
import util

class Annotation(object):
    def __repr__(self):
        return repr(self.__dict__)
    def copy(self):
        return copy.copy(self)
    pass

FOUNDING_DATE = util.strptime_ruleset('28 June 1993')
BOGUS = {
    '',
    '[Proposal 1500 attempted to Amend this Rule, but failed by Rule', '1339/2.]',
    '[Note: An earlier Rule with Number 833 was amended 8 times; thus', 'the amendment number.]',
}
REPLACEMENTS = {
    'Rule 2210 repealed itself.': 'Rule 2210 repealed by Rule 2210',
    'Amended by Proposal 754, Dec. 1, 1993': 'Amended by Proposal 754, Dec. 1 1993',
    'Mutated from MI=Unanimity to Rule 1057, MI=3 by Proposal 1057, Sep. 20 1994':
        'Mutated from MI=Unanimity to MI=3 and renumbered to 1057 by Proposal 1057, Sep. 20 1994',
    'Amended to Rule 1067 by Proposal 1067, Oct. 4 1994':
        'Amended by Proposal 1067, Oct. 4 1994',
}

@functools.lru_cache(None)
def parse_annotations(text):
    fulltext = text
    an = Annotation()
    an.revnum = None
    an.date = None
    an.power = None
    text = text.strip()
    if text in BOGUS:
        return [] # ?
    text = REPLACEMENTS.get(text, text)
    if text in {'...', '..', '[orphaned text]'}:
        an.type = '...'
        return [an]
    if text == 'Rule 2210 repealed itself.':
        an.type = 'repeal'
        an.num = 2210
        return [an]
    text = regex.sub(', (?:sus?bs?tantial|cosmetic)(?:,? \(unattributed\))?$', '', text)
    m = regex.match('(.*), (?:ca\. )?(.*?)\.?$', text)
    if m:
        if m.group(2) not in {'date unknown', 'datu unknown', 'XXXDATEHERE'}:
            an.date = util.strptime_ruleset(m.group(2))
        text = m.group(1)
    m = regex.match('ini?t?ial (immutable |mutable )?Rule ([0-9]+)$', text, regex.I)
    if m:
        an.type = 'create'
        an.revnum = '0'
        an.num = int(m.group(2))
        an.date = FOUNDING_DATE
        return [an]
    text = text.replace('byProposal', 'by Proposal')
    m = regex.match('(.*?) (?:by|via) (.*)', text)
    if m:
        an.by = m.group(2)
        text = m.group(1)
    mods = text.split(' and ')
    del text
    out = []
    for mod in mods:
        an2 = an.copy()
        out.append(an2)
        if mod == '???':
            an2.type = '...'
            continue
        m = regex.match('(?:created|enacted)(?: as(?: mutable| immutable| (?:mi|power)=([^ ]*))? Rule(?: ([0-9]+))?)?$', mod, regex.I)
        if m:
            an2.type = 'create'
            an2.revnum = '0'
            an2.num = int(m.group(2)) if m.group(2) else None
            an2.power = m.group(1) or None
            continue
        m = regex.match('(retitled|title changed)$', mod, regex.I)
        if m:
            an2.type = 'retitle'
            continue
        m = regex.match('(?:a?mended|amedned|mutated|null-amended)(?:\(([^\)]*)\))?(?: substantially| cosmetically| twice)?$', mod, regex.I)
        if m:
            an2.type = 'amend'
            an2.revnum = m.group(1)
            continue
        m = regex.match('(?:mutated|transmuted|power changed)(?: from (?:MI=)?([^ ]*))? to (?:MI=)?([^ ]*)$', mod, regex.I)
        if m:
            an2.type = 'repower'
            an2.old_power = m.group(1)
            an2.power = m.group(2)
            continue
        m = regex.match('(?:renumbered|number changed)(?: from ([0-9]+)(?:\/[^ ]*)?)? to ([0-9]+)(?:\/[^ ]*)?$', mod, regex.I)
        if m:
            an2.type = 'renumber'
            an2.old_num = int(m.group(1)) if m.group(1) else None
            an2.num = int(m.group(2))
            continue
        m = regex.match('infected(?:,? but not amended,?\s*)?$', mod, regex.I)
        if m:
            an2.type = 'infect'
            continue
        m = regex.match('assigned to (.*)$', mod, regex.I)
        if m:
            an2.type = 'assign'
            an2.committee = m.group(1)
            continue
        m = regex.match('(?:rule (?P<ruleno>[0-9]+) (?:\([^\)]*\) )?)?repealed(?: as (?:mutable|immutable|(?:power|mi)=(?P<power>[^ ]*)) rule(?: (?P<ruleno>[0-9]+))?)?$', mod, regex.I)
        if m:
            an2.type = 'repeal'
            an2.power = m.group('power') or None
            an2.num = int(m.group('ruleno')) if m.group('ruleno') else None
            continue

        raise Exception('annotation: unknown format: %r / %r' % (fulltext, mod))
    return out

def find_renumberings(entries):
    for entry in entries:
        data = entry['data']
        history = data.get('history')
        if history:
            for hist in history:
                print(hist)
                print(parse_annotations(hist))





def handle_entry(entry):
    meta = entry['meta']
    data = entry['data']
    if 'no_rules_except' in data:
        return
    for hist in (data['history'] or []):
        print(hist)

ap = argparse.ArgumentParser()
ap.add_argument('inputs', nargs='*', default=['out_zefram.json', 'out_misc.json', 'out_git.json'])
args = ap.parse_args()

entries = []
for inputpath in args.inputs:
    with open(inputpath) as fp:
        entries += json.load(fp)
find_renumberings(entries)
