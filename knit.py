import argparse, json, copy, datetime, functools, bisect, zlib
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
    return 'no_rules_except' not in entry.data

INITIAL_BLANKS_RE = re.compile('\s+\n')
def add_normalized_text(entry):
    data = entry.data
    entry.normalized_text = util.normalize_rule_text(data['text'])

WAS_RE = re.compile('\(\*was: (.*?)\*\)\s*$', re.I)
def add_annotation_objs(entry):
    data = entry.data
    hist = data.get('history') or []
    ans = [util.Annotation(a).copy() for a in hist]
    entry.ans = ans
    if (len(ans) == 0 or
        (data['revnum'] is not None and ans[-1].revnum is not None and revnum_key(data['revnum']) > revnum_key(ans[-1].revnum)) or
        (ans[-1].cur_num is not None and ans[-1].cur_num != data['number'])):
        dummy = util.Annotation('dummyann#1').copy()
        dummy.revnum = data['revnum']
        #timestamp = entry.meta.get('date')
        #if timestamp is not None:
        #    dummy.date = util.datetime_from_timestamp(timestamp).date()
        dummy.cur_num = data['number']
        ans.append(dummy)
    m = WAS_RE.search(data['text'])
    if m and len(ans) == 1:
        wuz = [int(num) for num in m.group(1).split('/')]
        last = wuz.pop()
        ans[0].prev_num = last
        ans[0].num_changed = True
        for other in wuz:
            dummy = util.Annotation('dummyann#2').copy()
            dummy.prev_num = other
            dummy.num_changed = True
            ans.insert(0, dummy)
    ans[-1].cur_num = data['number']
    if data['revnum'] is None:
        data['revnum'] = ans[-1].revnum
    for an in ans:
        an._entry = entry

def add_guessed_numbers(entry):
    data = entry.data
    meta = entry.meta
    history = data['history']
    # propagate cur_num and revnum forward
    cur_num = None
    revnum = None
    for an in entry.ans:
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
    ans = entry.ans
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
                print('in %s:' % (entry.meta['path'],))
                print('disagreement about rule number (on [%d]: going backwards: %r; going forwards: %r) for annotation set:' % (i, prev_num, an._guessed_num))
                for j, an2 in enumerate(entry.ans):
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
    return (len(entry.ans), entry.meta.get('date', 0))
def text_match(a, b):
    return a['normalized_text'] == b['normalized_text']


def identify_same(entries):
    def add_with_revnum(entry):
        number = entry.data['number']
        revnum = entry.data['revnum']
        existings = by_number_and_revnum[number][revnum]
        for existing in existings:
            # lol, performance
            if text_match(existing, entry):
                existing.variants.append(entry)
                break
        else:
            entry.variants = [entry]
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
                    existing.variants.append(entry)
                    break
            else:
                unmatched_nones.append(entry)
        still_unmatched_nones = []
        for entry in unmatched_nones:
            fudge_revnum = None
            number = entry.data['number']
            path = entry.meta['path']
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
                    entry.data['revnum'] = fudge_revnum
                    add_with_revnum(entry)
                continue
        with warnx():
            print('Orphan texts for rule %d:' % (entry.data['number'],),)
            for entry in still_unmatched_nones:
                print(entry.data['text'])
                print('variants:%d meta:%s' % (len(entry.variants), entry.meta,))
                print('last annotation:%s' % (entry.ans[-1],))
                print('==')
            print('Here are all the numbered texts I have for that rule:')
            have_any = False
            for revnum, xentries in sorted(by_revnum.items(), key=lambda tup: revnum_key(tup[0])):
                if revnum is None:
                    continue
                print('--')
                for existing in xentries:
                    print('revnum: %s  header: %s' % (existing.data['revnum'], existing.data['header']))
                    print(existing.data['text']),
                    print('variants:%d meta:%s' % (len(existing.variants), existing.meta,))
                    have_any = True
            if not have_any:
                print('(none)')



    for by_revnum in by_number_and_revnum.values():
        for revnum, xentries in by_revnum.items():
            if revnum is None:
                continue
            for i, entry in enumerate(xentries):
                best = max(entry.variants, key=quality)
                if best is not entry:
                    best.variants = entry.variants
                    del entry.variants
                xentries[i] = best
    return [existing for xentries in by_revnum.values() for existing in xentries]


class Entry:
    def __init__(self, stuff):
        self.data = stuff['data']
        self.meta = stuff['meta']
    def __str__(self):
        return ('entry %#x - %s/%s - normalized_text crc=%x\n%s\npath: %s' % (id(self), self.data['number'], self.data['revnum'], self.text_crc(), self.data['text'].rstrip(), self.meta['path']))
    def text_crc(self):
        return zlib.crc32(self.normalized_text) & 0xffffffff
    def date(self):
        ts = self.meta.get('date')
        if ts is None:
            return None
        else:
            return util.datetime_from_timestamp(ts)
class Rule:
    def __init__(self):
        self.anchors = []
        self.entries = []
        self.numbers = set()
    def __repr__(self):
        return 'Rule(numbers=%s, anchors=%s, #entries=%s)' % (self.numbers, self.anchors, len(self.entries))
    def definitely_created_after(self, after_date):
        dates = [an.date for entry in self.entries for an in entry.ans if an.is_create and an.date is not None]
        if len(dates) == 0:
            return False
        # be conservative in cae of conflict
        date = min(dates)
        return date > after_date


ANCHOR_OVERRIDES = {
    (2220, 5658): (2220, 5958),
    (2388, 7328): (2388, 7320),
    # was Rule 1477 created by Rule 1601 or Proposal 1601?
    # I can't find a primary source, but later FLRs say proposal
    (1477, datetime.date(1995, 6, 19)): (1477, 1601),
    # Rule 111 was renumbered to 1076 and then back to 111, at least
    # supposedly - see '1076.' in
    # archives/agora_vanyel0/agora/logs/discussion/1997.09.27
    # there's nothing in rulesets to link them, so this otherwise
    # would treat them as two separate rules
    (111, datetime.date(1994, 11, 1)): (111, datetime.date(1993, 6, 28)),
}

def split_into_rules_with_number_timeline(rule_entries):
    by_num_and_numbered_date = defaultdict(lambda: defaultdict(list))
    for entry in rule_entries:
        entry.anchors = []
        for an in entry.ans:
            if (an.is_create or an.num_changed) and an.date is not None and an._guessed_num is not None:
                anchor = (an._guessed_num, an.proposal_num or an.date)
                anchor = ANCHOR_OVERRIDES.get(anchor, anchor)
                by_num_and_numbered_date[an._guessed_num][an.date].append((entry, anchor))
                entry.anchors.append(anchor)
    timeline_by_num = defaultdict(list)
    for number, by_numbered_date in by_num_and_numbered_date.items():
        timeline_by_num[number] = sorted(by_numbered_date.keys())
    for entry in rule_entries:
        already_anchored = False
        prev_gn = None
        for an in entry.ans:
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
                    entry.anchors.append((number, None))
                    already_anchored = True
                    continue
                i = bisect.bisect_right(timeline, an.date)
                if i == 0 and number not in {1741}:
                    with warnx():
                        print('Annotation comes before all anchors for rule %d: %s' % (number, an))
                        print('from %s' % entry.meta['path'])
                        print('earliest is at %s: %s' % (timeline[0], by_num_and_numbered_date[number][timeline[0]]))
                        for an in entry.ans: print(an)
                    continue
                if i == len(timeline):
                    i -= 1 # assume the rule stayed the same?
                date = timeline[i]
                oentry, anchor = by_num_and_numbered_date[an._guessed_num][date][-1]
                entry.anchors.append(anchor)
                already_anchored = True
    def print_timeline(num):
        print('timeline for %s:' % (num,))
        for date in timeline_by_num[num]:
            print('- %s' % (date,))
            for entry in by_num_and_numbered_date[num][date][0]:
                print(entry)
                for an in entry.ans:
                    print(an)
    #print_timeline(1051); die
    anchor_to_rule = {}
    all_rules = set()
    rule_id = 0
    # unify multiple anchors in the same entry
    for entry in rule_entries:
        first_info = None
        for i, anchor in enumerate(entry.anchors):
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
        if entry.anchors:
            rule = anchor_to_rule[entry.anchors[0]]
            rule.entries.append(entry)
            for an in entry.ans:
                if an._guessed_num is not None:
                    rule.numbers.add(an._guessed_num)
            assert_(entry.data['number'] in rule.numbers)
        else:
            unowned_entries.append(entry)
    return all_rules, unowned_entries

def do_stragglers(rules, unowned_entries):
    rules_by_text = defaultdict(set)
    rules_by_number = defaultdict(set)
    for rule in rules:
        for entry in rule.entries:
            rules_by_text[entry.normalized_text].add(rule)
        for number in rule.numbers:
            rules_by_number[number].add(rule)
    unowned_by_number_and_text = defaultdict(lambda: defaultdict(set))
    for entry in unowned_entries:
        unowned_by_number_and_text[entry.data['number']][entry.normalized_text].add(entry)
    had_fails = False
    for number, by_text in unowned_by_number_and_text.items():
        nrules = rules_by_number[number]
        if len(nrules) == 0 or number in {1741}:
            # no history for this rule at all; just assume they're all one rule
            # rule 1741: the unanchored entry is a different rule from the anchored one
            new_rule = Rule()
            new_rule.numbers.add(number)
            for entries in by_text.values():
                new_rule.entries.extend(entries)
            rules.add(new_rule)
            continue
        for normalized_text, entries in by_text.items():
            trules = nrules
            if len(trules) > 1:
                trules = trules.intersection(rules_by_text[normalized_text])
            for entry in entries:
                drules = trules
                edate = entry.meta.get('date')
                if edate is not None and number not in {430}:
                    # rule 430: zefram_rules_text says "ca. Sep. 13 1993",
                    # but it was published on Sep. 8
                    edate = util.datetime_from_timestamp(edate).date()
                    drules = [rule for rule in trules if not rule.definitely_created_after(edate)]
                drules = list(drules)
                if len(drules) == 1:
                    rule = next(iter(drules))
                    rule.entries.append(entry)
                else:
                    print('could not match entry (and copies) to rule:')
                    print(next(iter(entries)))
                    print('date:', entry.date())
                    for i, rule in enumerate(drules):
                        print('***** candidate %d/%d:' % (i+1, len(drules)))
                        print(rule)
                        for oentry in rule.entries:
                            print('--')
                            print(oentry)
                    if not drules:
                        print('***** no candidates! (%d by number alone, but enacted too late)' % (len(nrules),))
                    print('====')
                    had_fails = True
                    break
    if had_fails:
        warn('could not match some entries')


def create_rule_timeline(rule):
    # any duplicate annotations? e.g. two retitlings on the same day by the same mechanism.  or indeterminate stuff
    some_number = min(rule.numbers)
    duplicate_sigs = {'dummyann#1', 'dummyann#2'}
    for entry in rule.entries:
        seen_sigs = set()
        for an in entry.ans:
            if an.is_indeterminate or an.sig in seen_sigs:
                duplicate_sigs.add(an.sig)
            seen_sigs.add(an.sig)
    # create a lattice/DAG of all annotations from all entries, ordered by order within an entry
    # 'latent' = lattice entry
    latents_by_sig = {}
    all_latents = set()
    class Latent:
        __slots__ = ['prevs', 'nexts', 'sig', 'ans', 'sccid', 'stackidx']
        def __init__(self, sig):
            self.prevs = set()
            self.nexts = set()
            self.sig = sig
            self.ans = []
            self.sccid = None
            self.stackidx = None
            all_latents.add(self)
        def __repr__(self):
            return 'Latent(%r)' % (self.sig,)
        def print_sig_and_texts(self):
            seen = set()
            print('sig:', self.sig)
            print('texts:')
            for an in self.ans:
                if an.text in seen: continue
                seen.add(an.text)
                print('->', an.text)
                print(' path:', an._entry.meta['path'])
        def delete(self):
            for prev in self.prevs: prev.nexts.remove(self)
            for next in self.nexts: next.prevs.remove(self)
            all_latents.remove(self)

    def build_latents():
        for entry in rule.entries:
            for an in entry.ans:
                sig = an.sig
                if sig in duplicate_sigs:
                    an.latent = Latent(None)
                elif sig in latents_by_sig:
                    an.latent = latents_by_sig[sig]
                else:
                    an.latent = latents_by_sig[sig] = Latent(sig)
                an.latent.ans.append(an)
            for i, an in enumerate(entry.ans):
                if i > 0:
                    an.latent.prevs.add(entry.ans[i-1].latent)
                if i + 1 < len(entry.ans):
                    an.latent.nexts.add(entry.ans[i+1].latent)
    def detect_renumberings:
    def handle_revnum_clashes():
        latents_by_revnum = defaultdict(list)
        for latent in latents_by_sig.values():
            revnum = latent.ans[0].revnum
            if revnum is not None:
                latents_by_revnum[revnum].append(latent)
        for revnum, latents in latents_by_revnum.items():
            kill = None
            if len(latents) <= 1:
                continue
            if some_number == 1567 and revnum == '2':
                # 'null-amended' entry later removed
                continue
            elif some_number == 207 and revnum == '24':
                # (24) was renumbered to (25)
                kill = {'Amended(24) via Rule 2430 "Cleanup Time," 24 May 2017'}
            elif some_number == 833 and revnum == '6':
                kill = {('6', '???')}
            if kill is not None:
                goods, bads = util.partition(lambda latent: latent.sig not in kill, latents)
                assert_(len(goods) == 1)
                for latent in bads:
                    goods[0].ans.extend(latent.ans)
                    latent.remove()

            if len(latents) <= 1:
                continue
            with warnx():
                print('Duplicate revnums for rule %s:' % (rule.numbers,))
                for latent in latents:
                    print('--')
                    latent.print_sig_and_texts()
                print('***')

    def break_cycles_and_group_sccs():
        # break cycles - turns out doesn't actually happen, but I had to write this code to figure that out, so may as well keep it
        stack = []
        for latent in all_latents:
            latent.prevs = list(latent.prevs)
            latent.nexts = list(latent.nexts)
        sccalias = list(range(len(all_latents)))
        for j, latent0 in enumerate(all_latents):
            sccid = j
            stack = [(latent0, 0)]
            latent0.stackidx = 0
            latent0.sccid = sccid
            while stack:
                latent, nexti = stack[-1]
                if nexti == len(latent.nexts):
                    latent.stackidx = None
                    stack.pop()
                    continue
                next = latent.nexts[nexti]
                stack[-1] = latent, nexti + 1
                if next.sccid is not None:
                    if next.sccid != sccid:
                        if next.sccid < sccid:
                            sccalias[sccid] = next.sccid
                            sccid = next.sccid
                        elif next.sccid > sccid:
                            sccalias[next.sccid] = sccid
                    if next.stackidx is not None:
                        # got a cycle
                        warn('Got cycle in annotation ordering: %r' % (stack[next.stackidx:],))
                        # arbitrarily choose the last link to break since it's easier - TODO if there are real cycles, do it better
                        latent.nexts.remove(next)
                        next.prevs.remove(latent)
                        stack[-1] = latent, nexti
                else:
                    next.sccid = sccid
                    next.stackidx = len(stack)
                    stack.append((next, 0))

        sccdict = defaultdict(list)
        for latent in all_latents:
            sccid = latent.sccid
            lst = []
            # lol this is dumb
            while True:
                sccid2 = sccalias[sccid]
                if sccid2 == sccid: break
                assert_(sccid2 < sccid)
                lst.append(sccid)
                sccid = sccid2
            for sccid in lst:
                sccalias[sccid] = sccid2
            sccdict[sccid2].append(latent)
        sccs = filter(len, sccdict.values())
        return sccs
    build_latents()
    handle_revnum_clashes()
    sccs = break_cycles_and_group_sccs()
    


ap = argparse.ArgumentParser()
ap.add_argument('inputs', nargs='*', default=['out_zefram.json', 'out_misc.json', 'out_git.json'])
args = ap.parse_args()


entries = []
for inputpath in args.inputs:
    with open(inputpath) as fp:
        entries += json.load(fp)
def go(entries):
    entries = list(map(Entry, entries))
    rule_entries = []
    no_rules_except_entries = []
    for entry in entries:
        if is_rule_entry(entry):
            rule_entries.append(entry)
        else:
            assert_('no_rules_except' in entry.data)
            date = entry.date()
            if date is not None:
                no_rules_except_entries.append((date, entry))
    for entry in rule_entries:
        add_normalized_text(entry)
        add_annotation_objs(entry)
        add_guessed_numbers(entry)
    rules, unowned_entries = split_into_rules_with_number_timeline(rule_entries)
    do_stragglers(rules, unowned_entries)
    for rule in rules:
        create_rule_timeline(rule)
go(entries)
