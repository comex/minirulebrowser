import argparse, json, copy, datetime
from collections import defaultdict
import regex
import util
from util import warn, warnx

def revnum_gt(a, b):
    assert isinstance(a, str)
    assert isinstance(b, str)
    if a == '???' or b == '???':
        return None
    return float(a) > float(b)

def is_rule_entry(entry):
    return 'no_rules_except' not in entry['data']

def strip_text(entry):
    data = entry['data']
    if data['text'] is not None:
        data['text'] = data['text'].rstrip()

def add_annotation_obj(entry):
    data = entry['data']
    hist = data.get('history') or []
    ans = list(map(copy.copy, map(util.Annotation, hist)))
    entry['ans'] = ans
    if (len(ans) == 0 or
        (data['revnum'] is not None and ans[-1].revnum is not None and revnum_gt(data['revnum'], ans[-1].revnum)) or
        (ans[-1].cur_num is not None and ans[-1].cur_num != data['number'])):
        dummy = copy.copy(util.Annotation(''))
        dummy.revnum = data['revnum']
        timestamp = entry['meta'].get('date')
        if timestamp is not None:
            dummy.date = util.datetime_from_timestamp(timestamp).date()
        dummy.cur_num = data['number']
        ans.append(dummy)
    ans[-1].cur_num = data['number']

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
    for i, an in list(enumerate(entry['ans']))[::-1]:
        if an.is_indeterminate:
            prev_num = None
            continue
        if an._guessed_num is None:
            an._guessed_num = prev_num
        elif prev_num is not None and an._guessed_num != prev_num:
            with warnx():
                print('in %s:' % (entry['meta']['path'],))
                print('disagreement about rule number (on [%d]: going backwards: %r; going forwards: %r) for annotation set:' % (i, prev_num, an._guessed_num))
                for j, an2 in enumerate(entry['ans']):
                    print('[%d] %r' % (j, an2))
        if an.num_changed:
            prev_num = an.prev_num

def normalized_text(entry):
    x = entry.get('normalized_text')
    if x is None:
        #print('normalizing', entry['data']['number'], entry['data']['revnum'])
        x = entry['normalized_text'] = util.normalize_text(entry['data']['text'])
    return x

def identify_same(entries):
    def quality(entry):
        # more history is better
        # newer is better, older is better than no date
        return (len(entry['ans']), entry['meta'].get('date', 0))
    def text_match(a, b):
        if a['data']['text'] == b['data']['text']:
            return True
        return normalized_text(a) == normalized_text(b)
    by_number_and_revnum = defaultdict(lambda: defaultdict(list))
    for entry in entries:
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
        if len(unmatched_nones) == 0:
            break
        if len(unmatched_nones) == 1 and len(by_revnum) == 0:
            # only one text for this rule at all;
            # let's call it 0
            entry['data']['revnum'] = '0'
            entry['variants'] = [entry]
            by_revnum['0'] = [entry]
            break
        with warnx():
            print('Orphan texts for rule %d:' % (entry['data']['number'],),)
            for entry in unmatched_nones:
                print(entry['data']['text'])
                print('meta: %s' % (entry['meta'],))
            print('Here are all the numbered texts I have for that rule:')
            have_any = False
            for existing in (existing for xentries in by_revnum.values() for existing in xentries):
                print(existing['data']['header']),
                print(existing['data']['text']),
                print('meta:', entry['meta'])
                have_any = True
            if not have_any:
                print('(none)')



    for xentries in by_number_and_revnum.values():
        for i, entry in enumerate(xentries):
            best = max(entry['variants'], key=quality)
            if best is not entry:
                best['variants'] = entry['variants']
                del entry['variants']
            xentries[i] = best
    return by_number_and_revnum

def identify_parents(by_number_and_revnum):
    for xentries in by_number_and_revnum.values():
        for entry in xentries:
            pass#by_number_and_revnum((entry['number'], 

def find_renumberings(entries, verbose=True):
    for entry in entries:
        if is_rule_entry(entry):
            initial_num = None
            if entry['ans'][0]._guessed_revnum == '0':
                initial_num = entry['ans'][0]._guessed_num
            if initial_num is not None:
                rule_entries_by_initial_num[initial_num].append(entry)
            else:
                unknown_rule_entries.append(entry)

    if verbose:
        print('a priori got initial nums:')
        nums = set(list(rule_entries_by_initial_num.keys()) +
                   [entry['data']['number'] for entry in entries if 'number' in entry['data']])
        for num in nums:
            print('  rule %d: %d entries' % (num, len(rule_entries_by_initial_num[num])))
        print('  unknown: %d entries' % (len(unknown_rule_entries),))



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
    rule_entries = list(filter(is_rule_entry, entries))
    for entry in rule_entries:
        strip_text(entry)
        add_annotation_obj(entry)
        add_guessed_numbers(entry)
    by_number_and_revnum = identify_same(rule_entries)
    identify_parents(by_number_and_revnum)
go(entries)
