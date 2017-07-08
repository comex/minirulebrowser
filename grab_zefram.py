import re, json
import util
stuff = open('old_zefram_rules_text.txt').read()
rules = []
show_dups = True
if show_dups:
    seen_rulenums = set()

numbers_stopped_changing_at = util.strptime_ruleset('1 November 1994')
for rulestuff in re.split('\n\n-----+\n\n', stuff)[1:-1]:
    for bit in re.split('\n\n(?![ \]])', rulestuff):
        if bit.startswith('RULE'):
            rulenums = list(map(int, re.match('RULE (.*)$', bit).group(1).split(',')))
            cur_rulenum = rulenums[0] # just guess for now
            for num in rulenums:
                if show_dups:
                    if num in seen_rulenums:
                        print('duplicate:', num)
                    seen_rulenums.add(num)
            rules.append({'rulenums': rulenums, 'versions': []})
        elif bit.startswith('history:'):
            annotation = bit[9:]
            # we have to reverse engineer the actual rule number at the time
            # even though this would have been in Zefram's source material
            cur_revnum = None
            m = re.match('(Initial|Enacted).*Rule ([0-9]+)', annotation)
            if m:
                cur_rulenum = int(m.group(2))
                cur_revnum = '0'
            if annotation.startswith('Created '):
                cur_revnum = '0'
            m = re.match('Renumbered .*to ([0-9]+)', annotation)
            if m:
                cur_rulenum = int(m.group(1))
            m = re.match('(?:Amended|Transmuted).*by Proposal ([0-9]+), (?:ca\. )?(.* 199[34])', annotation)
            if m and util.strptime_ruleset(m.group(2)) < numbers_stopped_changing_at:
                cur_rulenum = int(m.group(1))
            m = re.match('(Amended|Transmuted)\(([^\)]*)\)', annotation)
            if m:
                cur_revnum = m.group(2)
            rules[-1]['versions'].append({'annotation': annotation, 'rulenum': cur_rulenum, 'revnum': cur_revnum, 'texts': []})
        elif bit.startswith('text:'):
            rules[-1]['versions'][-1]['texts'].append(bit[7:])
        elif bit.startswith('[orphaned text:'):
            assert bit.endswith('\n\n]')
            text = bit[17:-3]
            rules[-1]['versions'].append({'annotation': '[orphaned text]', 'rulenum': cur_rulenum, 'revnum': cur_revnum, 'texts': [text]})
        elif bit.startswith('['):
            pass
        else:
            raise Exception('? %r' % (bit,))

# convert to a format similar to that output by grab_misc
out = []
for rule in rules:
    for version in rule['versions']:
        for text in version['texts']:
            data = {
                'number': version['rulenum'],
                'revnum': version['revnum'],
                'title': None,
                'header': None,
                'extra': None,
                'text': text,
                'annotations': None,
                'history': [version['annotation']],
            }
            out.append({'meta': {'path': 'old_zefram_rules_text.txt'}, 'data': data})
with open('rules_zefram.json', 'w') as gp:
    json.dump(out, gp)
