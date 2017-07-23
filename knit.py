import argparse, json, copy, datetime, functools, bisect
from collections import defaultdict
import util
from util import warn, warnx, assert_, re


@functools.lru_cache(None)
def revnum_key(a):
    if a is None:
        return (10000,)
    assert isinstance(a, str)
    return tuple(list(map(int, a.split('.'))))

def is_rule_entry(entry):
    return 'no_rules_except' not in entry['data']

INITIAL_BLANKS_RE = re.compile('\s+\n')
def add_normalized_text(entry):
    data = entry['data']
    entry['normalized_text'] = util.normalize_rule_text(data['text'])

WAS_RE = re.compile('\(\*was: (.*?)\*\)\s*$', re.I)
def add_annotation_obj(entry):
    data = entry['data']
    hist = data.get('history') or []
    ans = [util.Annotation(a).copy() for a in hist]
    entry['ans'] = ans
    if (len(ans) == 0 or
        (data['revnum'] is not None and ans[-1].revnum is not None and revnum_key(data['revnum']) > revnum_key(ans[-1].revnum)) or
        (ans[-1].cur_num is not None and ans[-1].cur_num != data['number'])):
        dummy = util.Annotation('#1').copy()
        dummy.revnum = data['revnum']
        timestamp = entry['meta'].get('date')
        if timestamp is not None:
            dummy.date = util.datetime_from_timestamp(timestamp).date()
        dummy.cur_num = data['number']
        ans.append(dummy)
    m = WAS_RE.search(data['text'])
    if m and len(ans) == 1:
        wuz = [int(num) for num in m.group(1).split('/')]
        last = wuz.pop()
        ans[0].prev_num = last
        ans[0].num_changed = True
        for other in wuz:
            dummy = util.Annotation('#2').copy()
            dummy.prev_num = other
            dummy.num_changed = True
            ans.insert(0, dummy)
    ans[-1].cur_num = data['number']
    if data['revnum'] is None:
        data['revnum'] = ans[-1].revnum

def add_guessed_numbers(entry):
    data = entry['data']
    meta = entry['meta']
    history = data['history']
    # propagate cur_num and revnum forward
    cur_num = None
    revnum = None
    for an in entry['ans']:
        if an.is_indeterminate:
            cur_num = None
            revnum = None
            an._guessed_num = None
            an._guessed_revnum = None
            continue
        if an.cur_num is not None:
            cur_num = an.cur_num
        an._guessed_num = cur_num
        if an.revnum is not None:
            revnum = an.revnum
        an._guessed_revnum = revnum
    # propagate prev_num backward
    prev_num = data['number']
    ans = entry['ans']
    for i in range(len(ans)-1, -1, -1):
        an = ans[i]
        if an.is_indeterminate:
            prev_num = None
            continue
        if an._guessed_num is None:
            an._guessed_num = prev_num
        elif (prev_num is not None and an._guessed_num != prev_num
            and not (an._guessed_num == 155 and prev_num == 115)):
            with warnx():
                print('in %s:' % (entry['meta']['path'],))
                print('disagreement about rule number (on [%d]: going backwards: %r; going forwards: %r) for annotation set:' % (i, prev_num, an._guessed_num))
                for j, an2 in enumerate(entry['ans']):
                    print('[%d] %r' % (j, an2))
        if an.num_changed:
            prev_num = an.prev_num


FUDGE_REVNUMS = {
    104: ['0'],
    362: ['0.795'],
    364: ['0.364.-1'],
    376: ['0.793'],
    377: ['0.377.-1'],
    399: ['0', '0.1051',],

    951: ['0.793', '0.410'],
    308: ['0.308.-1'],
    848: ['0.355'],


}

def quality(entry):
    # more history is better
    # newer is better, older is better than no date
    return (len(entry['ans']), entry['meta'].get('date', 0))
def text_match(a, b):
    return a['normalized_text'] == b['normalized_text']


def identify_same(entries):
    def add_with_revnum(entry):
        number = entry['data']['number']
        revnum = entry['data']['revnum']
        existings = by_number_and_revnum[number][revnum]
        for existing in existings:
            # lol, performance
            if text_match(existing, entry):
                existing['variants'].append(entry)
                break
        else:
            entry['variants'] = [entry]
            existings.append(entry)
    by_number_and_revnum = defaultdict(lambda: defaultdict(list))
    for entry in entries:
        add_with_revnum(entry)
    # deal with revnum=None entries
    for number, by_revnum in by_number_and_revnum.items():
        nones = by_revnum[None]
        del by_revnum[None]
        unmatched_nones = []
        for entry in nones:
            for existing in (existing for xentries in by_revnum.values() for existing in xentries):
                if text_match(existing, entry):
                    existing['variants'].append(entry)
                    break
            else:
                unmatched_nones.append(entry)
        still_unmatched_nones = []
        for entry in unmatched_nones:
            fudge_revnum = None
            number = entry['data']['number']
            path = entry['meta']['path']
            still_unmatched_nones.append(entry)
        if not still_unmatched_nones:
            continue
        fudge_revnums = None
        if len(still_unmatched_nones) == 1 and len(by_revnum) == 0:
            fudge_revnums = ['0']
        elif number in FUDGE_REVNUMS:
            fudge_revnums = FUDGE_REVNUMS[number]
        if fudge_revnums is not None:
            if len(fudge_revnums) != len(still_unmatched_nones):
                print('...bad fudge_revnums length!')
            else:
                for fudge_revnum, entry in zip(fudge_revnums, still_unmatched_nones):
                    entry['data']['revnum'] = fudge_revnum
                    add_with_revnum(entry)
                continue
        with warnx():
            print('Orphan texts for rule %d:' % (entry['data']['number'],),)
            for entry in still_unmatched_nones:
                print(entry['data']['text'])
                print('variants:%d meta:%s' % (len(entry['variants']), entry['meta'],))
                print('last annotation:%s' % (entry['ans'][-1],))
                print('==')
            print('Here are all the numbered texts I have for that rule:')
            have_any = False
            for revnum, xentries in sorted(by_revnum.items(), key=lambda tup: revnum_key(tup[0])):
                if revnum is None:
                    continue
                print('--')
                for existing in xentries:
                    print('revnum: %s  header: %s' % (existing['data']['revnum'], existing['data']['header']))
                    print(existing['data']['text']),
                    print('variants:%d meta:%s' % (len(existing['variants']), existing['meta'],))
                    have_any = True
            if not have_any:
                print('(none)')



    for by_revnum in by_number_and_revnum.values():
        for revnum, xentries in by_revnum.items():
            if revnum is None:
                continue
            for i, entry in enumerate(xentries):
                best = max(entry['variants'], key=quality)
                if best is not entry:
                    best['variants'] = entry['variants']
                    del entry['variants']
                xentries[i] = best
    return [existing for xentries in by_revnum.values() for existing in xentries]


class Entry:
    def __init__(self, stuff):
        self.data = stuff['data']
        self.meta = stuff['meta']
class Rule:
    def __init__(self):
        self.anchors = []
        self.entries = []
        self.numbers = set()
    def __repr__(self):
        return 'Rule(numbers=%s, anchors=%s, #entries=%s)' % (self.numbers, self.anchors, len(self.entries))

def make_rules_with_timeline(rule_entries):
    by_num_and_numbered_date = defaultdict(lambda: defaultdict(list))
    for entry in rule_entries:
        entry['anchors'] = []
        for an in entry['ans']:
            if (an.is_create or an.num_changed) and an.date is not None and an._guessed_num is not None:
                by_num_and_numbered_date[an._guessed_num][an.date].append(entry)
                entry['anchors'].append((an._guessed_num, an.date))
    timeline_by_num = defaultdict(list)
    for number, by_numbered_date in by_num_and_numbered_date.items():
        timeline_by_num[number] = sorted(by_numbered_date.keys())
    for entry in rule_entries:
        already_anchored = False
        prev_gn = None
        for an in entry['ans']:
            if an.num_changed or an.is_indeterminate or an._guessed_num != prev_gn:
                already_anchored = False
            prev_gn = an._guessed_num
            if (an.is_create or an.num_changed) and an.date is not None:
                already_anchored = True
            if already_anchored:
                continue
            if an._guessed_num is not None and an.date is not None:
                number = an._guessed_num
                timeline = timeline_by_num[number]
                if len(timeline) == 0:
                    # eh, assume there weren't multiple copies of this rule
                    entry['anchors'].append((number, None))
                    already_anchored = True
                    continue
                i = bisect.bisect_right(timeline, an.date)
                if i == 0 and number not in {1741}:
                    with warnx():
                        print('Annotation comes before all anchors for rule %d: %s' % (number, an))
                        print('from %s' % entry['meta']['path'])
                        print('earliest is at %s: %s' % (timeline[0], by_num_and_numbered_date[number][timeline[0]]))
                        for an in entry['ans']: print(an)
                    continue
                if i == len(timeline):
                    i -= 1 # assume the rule stayed the same?
                date = timeline[i]
                entry['anchors'].append((an._guessed_num, date))
                already_anchored = True
    anchor_to_rule = {}
    all_rules = set()
    rule_id = 0
    # unify multiple anchors in the same entry
    for entry in rule_entries:
        first_info = None
        for i, anchor in enumerate(entry['anchors']):
            rule = anchor_to_rule.get(anchor)
            if rule is None:
                rule = Rule()
                rule.anchors.append(anchor)
                all_rules.add(rule)
                anchor_to_rule[anchor] = rule
            if i == 0:
                first_rule = rule
            else:
                if rule is not first_rule:
                    for anchor in rule.anchors:
                        anchor_to_rule[anchor] = first_rule
                    all_rules.remove(rule)
                    first_rule.anchors.extend(rule.anchors)
    unowned_entries = []
    for entry in rule_entries:
        if entry['anchors']:
            rule = anchor_to_rule[entry['anchors'][0]]
            rule.entries.append(entry)
            for an in entry['ans']:
                if an._guessed_num is not None:
                    rule.numbers.add(an._guessed_num)
        else:
            unowned_entries.append(entry)
    return all_rules, unowned_entries

def do_easy_stragglers(rules, unowned_entries):
    rules_by_text = defaultdict(set)
    rules_by_number = defaultdict(set)
    for rule in rules:
        for entry in rule.entries:
            rules_by_text[entry['normalized_text']].add(rule)
        for number in rule.numbers:
            rules_by_number[number].add(rule)
    for entry in unowned_entries:
        xrules = (rules_by_text[entry['normalized_text']].intersection(
                  rules_by_number[entry['data']['number']]))
        if len(xrules) == 1:
            rule = next(iter(xrules))
        elif len(xrules) > 1:
            print('entry:')
            print(entry)
            print('candidates:')
            for rule in xrules:
                print(rule)
                for oentry in rule.entries:
                    print('--')
                    print(oentry)
            print('====')



ap = argparse.ArgumentParser()
ap.add_argument('inputs', nargs='*', default=['out_zefram.json', 'out_misc.json', 'out_git.json'])
args = ap.parse_args()

entries = []
for inputpath in args.inputs:
    with open(inputpath) as fp:
        entries += json.load(fp)
def go(entries):
    for i, entry in enumerate(entries):
        entry['id'] = i
    rule_entries = list(map(Entry, filter(is_rule_entry, entries)))
    for entry in rule_entries:
        add_normalized_text(entry)
        add_annotation_obj(entry)
        add_guessed_numbers(entry)
    rules, unowned_entries = make_rules_with_timeline(rule_entries)
    do_easy_stragglers(rules, unowned_entries)
    #rule_entries = identify_same(rule_entries)
go(entries)
