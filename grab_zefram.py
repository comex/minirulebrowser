import json
import regex
import util
stuff = open('old_zefram_rules_text.txt').read()
rules = []
show_dups = True
if show_dups:
    seen_rulenums = set()

numbers_stopped_changing_at = util.strptime_ruleset('1 November 1994')
for rulestuff in regex.split('\n\n-----+\n\n', stuff)[1:-1]:
    for bit in regex.split('\n\n(?![ \]])', rulestuff):
        if bit.startswith('RULE'):
            rulenums = list(map(int, regex.match('RULE (.*)$', bit).group(1).split(',')))
            cur_rulenum = rulenums[0] # just guess for now
            for num in rulenums:
                if show_dups:
                    if num in seen_rulenums:
                        print('duplicate:', num)
                    seen_rulenums.add(num)
            rules.append({'rulenums': rulenums, 'versions': []})
        elif bit.startswith('history:'):
            annotation_text = bit[9:]
            # we have to reverse engineer the actual rule number at the time
            # even though this would have been in Zefram's source material
            annotation = util.Annotation(annotation_text)
            cur_revnum = annotation.revnum
            if annotation.cur_num is not None:
                cur_rulenum = annotation.cur_num
            rules[-1]['versions'].append({'annotation': annotation_text, 'rulenum': cur_rulenum, 'revnum': cur_revnum, 'texts': []})
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
for j, rule in enumerate(rules):
    for i, version in enumerate(rule['versions']):
        for text in version['texts']:
            data = {
                'number': version['rulenum'],
                'revnum': version['revnum'],
                'title': None,
                'header': None,
                'extra': None,
                'text': text,
                'annotations': None,
                'history': [xversion['annotation'] for xversion in rule['versions'][:i+1]],
                'zefram_anchor': j,
            }
            out.append({'meta': {'path': 'old_zefram_rules_text.txt'}, 'data': data})
with open('out_zefram.json', 'w') as gp:
    json.dump(out, gp)
