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
