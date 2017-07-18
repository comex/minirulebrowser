import argparse, json, copy, datetime
from collections import defaultdict
import regex
import util
from util import warn, warnlines

def revnum_gt(a, b):
    assert isinstance(a, str)
    assert isinstance(b, str)
    if a == '???' or b == '???':
        return None
    return float(a) > float(b)

def is_rule_entry(entry):
    return 'no_rules_except' not in entry['data']

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
            if 1:
                warnlines(
                    'in %s:' % (entry['meta']['path'],),
                    'disagreement about rule number (on [%d]: going backwards: %r; going forwards: %r) for annotation set:' % (i, prev_num, an._guessed_num),
                    *('[%d] %r' % (j, an2) for (j, an2) in enumerate(entry['ans']))
                )
        if an.num_changed:
            prev_num = an.prev_num

rule_entries_by_initial_num = defaultdict(list)
unknown_rule_entries = []

def find_renumberings(entries, verbose=True):
    for entry in entries:
        if is_rule_entry(entry):
            initial_num = None
            if entry['data']['number'] == 2483:
                print(entry['ans'])
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
    for entry in entries:
        if is_rule_entry(entry):
            add_annotation_obj(entry)
            add_guessed_numbers(entry)
    find_renumberings(entries)
go(entries)
