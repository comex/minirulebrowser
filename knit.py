import argparse, json, copy
from collections import defaultdict
import regex
import util

def get_initial_num_a_priori(data):
    # if the revision number is 0, the current rule number is the initial one
    if data['revnum'] == '0' and data['number'] is not None:
        return data['number']
    history = data['history']
    if history is not None and len(history) > 0:
        an = util.Annotation(history[0])
        if an.initial_num is not None:
            return an.initial_num

        for annotation_text in history:
            an = util.Annotation(annotation_text)
            if an.renumber is not None:
                old, new = an.renumber
                if old is not None:
                    return old
                else:
                    break
            if an.is_indeterminate:
                break
        else:
            # no renumberings or indeterminate lines in the entire history, so
            # the current rule number is the initial one
            if data['number'] is not None:
                return data['number']


rule_entries_by_initial_num = defaultdict(list)
unknown_rule_entries = []

def is_rule_entry(data):
    return 'no_rules_except' not in data

def find_renumberings(entries, verbose=True):
    for entry in entries:
        data = entry['data']
        if is_rule_entry(data):
            num = get_initial_num_a_priori(data)
            if num is not None:
                rule_entries_by_initial_num[num].append(entry)
            else:
                unknown_rule_entries.append(entry)

    if verbose:
        print('a priori got initial nums:')
        nums = set(list(rule_entries_by_initial_num.keys()) +
                   [entry['data']['number'] for entry in entries if 'number' in entry['data']])
        for num in nums:
            print('  rule %d: %d entries' % (num, len(rule_entries_by_initial_num[num])))


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
