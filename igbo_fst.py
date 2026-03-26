"""
IgboFST - Finite-State Transducer for Igbo Verb Morphology
Based on Koskenniemi (1983) two-level morphology model
Karttunen & Beesley (2003) Lexical Transducer architecture
"""

import csv


# ── 1. Load Corpus ────────────────────────────────────────────────────────────

def load_corpus(filepath):
    corpus = []
    with open(filepath, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            corpus.append({
                'word':     row['word'],
                'morphemes': [m.strip() for m in row['morphemes'].split('|')],
                'types':    [t.strip() for t in row['types'].split('|')],
                'glosses':  row['glosses'],
                'gram_cat': row.get('grammatical_category', ''),
            })
    return corpus


# ── 2. Extract Patterns ───────────────────────────────────────────────────────

def extract_patterns(corpus):
    patterns = {
        'aux': set(), 'prefix': set(), 'bound_prefix': set(),
        'root': set(), 'ext_suffix': set(), 'imp_suffix': set(),
        'infl_suffix': set(), 'sequences': set(),
    }
    # Track which types each morpheme appears as (for ambiguity resolution)
    membership = {}
    for entry in corpus:
        seq_parts = []
        for form, mtype in zip(entry['morphemes'], entry['types']):
            form = form.strip(); mtype = mtype.strip()
            if mtype in patterns and mtype != 'sequences':
                patterns[mtype].add(form)
            if form not in membership:
                membership[form] = {}
            membership[form][mtype] = membership[form].get(mtype, 0) + 1
            seq_parts.append(mtype)
        patterns['sequences'].add('|'.join(seq_parts))
    patterns['_membership'] = membership
    return patterns


# ── 3. FST ────────────────────────────────────────────────────────────────────

class IgboFST:
    """
    Finite-State Transducer for Igbo verb morphology.
    States reflect Emenanjo three-domain morphological analysis:
      Derivational (prefix/bound_prefix)
      Extensional  (ext_suffix)
      Inflectional (aux/infl_suffix/imp_suffix)
    """

    STATES = {
        'START':        {'is_accept': False},
        'AUX':          {'is_accept': False},
        'PREFIX':       {'is_accept': False},
        'BOUND_PREFIX': {'is_accept': False},
        'ROOT':         {'is_accept': True},
        'EXT_SUFFIX':   {'is_accept': True},
        'IMP_SUFFIX':   {'is_accept': True},
        'INFL_SUFFIX':  {'is_accept': True},
        'REJECT':       {'is_accept': False},
    }

    # Valid transitions (current_state, morpheme_type) → next_state
    TRANSITIONS = {
        ('START',        'aux'):          'AUX',
        ('START',        'prefix'):       'PREFIX',
        ('START',        'bound_prefix'): 'BOUND_PREFIX',
        ('START',        'root'):         'ROOT',
        ('AUX',          'prefix'):       'PREFIX',
        ('AUX',          'bound_prefix'): 'BOUND_PREFIX',
        ('AUX',          'root'):         'ROOT',
        ('AUX',          'infl_suffix'):  'INFL_SUFFIX',
        ('PREFIX',       'root'):         'ROOT',
        ('PREFIX',       'imp_suffix'):   'IMP_SUFFIX',
        ('BOUND_PREFIX', 'root'):         'ROOT',
        ('ROOT',         'ext_suffix'):   'EXT_SUFFIX',
        ('ROOT',         'imp_suffix'):   'IMP_SUFFIX',
        ('ROOT',         'infl_suffix'):  'INFL_SUFFIX',
        ('ROOT',         'bound_prefix'): 'BOUND_PREFIX',
        ('EXT_SUFFIX',   'ext_suffix'):   'EXT_SUFFIX',
        ('EXT_SUFFIX',   'infl_suffix'):  'INFL_SUFFIX',
        ('IMP_SUFFIX',   'infl_suffix'):  'INFL_SUFFIX',
        ('INFL_SUFFIX',  'infl_suffix'):  'INFL_SUFFIX',
    }

    REJECTION_REASONS = {
        ('ROOT',        'prefix'):      'A prefix cannot follow a root in Igbo verbs',
        ('ROOT',        'aux'):         'An auxiliary cannot follow a root',
        ('INFL_SUFFIX', 'root'):        'A root cannot follow an inflectional suffix',
        ('INFL_SUFFIX', 'ext_suffix'):  'An extensional suffix cannot follow an inflectional suffix',
        ('START',       'infl_suffix'): 'A word cannot begin with an inflectional suffix',
        ('START',       'ext_suffix'):  'A word cannot begin with an extensional suffix',
        ('EXT_SUFFIX',  'prefix'):      'A prefix cannot follow an extensional suffix',
    }

    def __init__(self, patterns):
        self.patterns = patterns
        self.reset()

    def reset(self):
        self.current_state = 'START'
        self.output_labels = []
        self.trace = []

    def classify(self, segment, prev_state='START'):
        """
        Context-sensitive morpheme classification.
        Resolves ambiguity (e.g. 'ri' as root vs infl_suffix)
        using the current FST state as context — following
        Koskenniemi's parallel constraint model.
        """
        seg = segment.strip()

        # Priority order depends on current state context
        if prev_state in ('START', 'AUX', 'PREFIX', 'BOUND_PREFIX'):
            # Expecting a root or prefix-like element
            priority = ['aux', 'prefix', 'bound_prefix', 'root',
                        'ext_suffix', 'imp_suffix', 'infl_suffix']
        elif prev_state == 'ROOT':
            # Expecting a suffix of some kind
            priority = ['ext_suffix', 'imp_suffix', 'infl_suffix',
                        'bound_prefix', 'aux', 'prefix', 'root']
        elif prev_state in ('EXT_SUFFIX',):
            priority = ['ext_suffix', 'infl_suffix', 'root',
                        'imp_suffix', 'aux', 'prefix', 'bound_prefix']
        else:
            priority = ['infl_suffix', 'ext_suffix', 'imp_suffix',
                        'root', 'bound_prefix', 'prefix', 'aux']

        for mtype in priority:
            if seg in self.patterns.get(mtype, set()):
                # Verify transition is valid before committing
                if (prev_state, mtype) in self.TRANSITIONS:
                    return mtype

        # Fall back: return first set membership regardless of transition
        for mtype in priority:
            if seg in self.patterns.get(mtype, set()):
                return mtype

        # Reduplication detection (Emenanjo Ch.6 BCN / Agbo)
        half = len(seg) // 2
        if len(seg) % 2 == 0 and len(seg) >= 2 and seg[:half] == seg[half:]:
            if seg[:half] in self.patterns['root']:
                return 'root'

        return 'unknown'

    def step(self, segment):
        mtype = self.classify(segment, self.current_state)
        key = (self.current_state, mtype)

        if mtype == 'unknown':
            self.current_state = 'REJECT'
            reason = 'Unrecognised segment — not in any morpheme set'
            label = f'UNKNOWN({segment})'
        elif key in self.TRANSITIONS:
            self.current_state = self.TRANSITIONS[key]
            label = f'{mtype.upper()}({segment})'
            reason = None
        else:
            reason = self.REJECTION_REASONS.get(
                key, f'{mtype} not valid after {self.current_state}'
            )
            self.current_state = 'REJECT'
            label = f'INVALID({segment})'

        self.output_labels.append(label)
        self.trace.append({
            'segment': segment, 'type': mtype,
            'state': self.current_state,
            'label': label, 'reason': reason,
        })
        return self.current_state, label, reason

    def analyze(self, morpheme_list):
        """Analyze a pre-segmented morpheme list."""
        self.reset()
        for seg in morpheme_list:
            self.step(seg)
        return {
            'valid':       self.STATES[self.current_state]['is_accept'],
            'final_state': self.current_state,
            'trace':       self.trace,
            'translation': '  +  '.join(self.output_labels),
        }

    def analyze_word(self, word):
        """Analyze unsegmented word using greedy longest-match."""
        self.reset()
        pos = 0
        segments = []
        all_morphemes = set()
        for mtype, mset in self.patterns.items():
            if mtype not in ('sequences', '_membership'):
                all_morphemes.update(mset)
        while pos < len(word):
            matched = False
            for length in range(len(word) - pos, 0, -1):
                candidate = word[pos:pos + length]
                if candidate in all_morphemes:
                    segments.append(candidate)
                    pos += length
                    matched = True
                    break
            if not matched:
                segments.append(word[pos])
                pos += 1
        return self.analyze(segments), segments

    def validate_corpus(self, corpus):
        """Run FST over entire corpus. Returns accuracy stats."""
        correct = 0
        wrong = []
        for entry in corpus:
            result = self.analyze(entry['morphemes'])
            if result['valid']:
                correct += 1
            else:
                wrong.append({'word': entry['word'], 'result': result})
        total = len(corpus)
        return {
            'total': total, 'correct': correct,
            'accuracy': correct / total * 100,
            'failures': wrong,
        }


# ── 4. Main ───────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import os
    csv_path = 'igbo_verbs_final.csv'
    if not os.path.exists(csv_path):
        print(f'CSV not found at {csv_path}'); exit(1)

    corpus   = load_corpus(csv_path)
    patterns = extract_patterns(corpus)
    fst      = IgboFST(patterns)

    print(f"Corpus: {len(corpus)} entries | {len(patterns['root'])} roots | "
          f"{len(patterns['sequences'])} sequence patterns\n")

    # Corpus validation
    stats = fst.validate_corpus(corpus)
    print(f"Corpus validation: {stats['correct']}/{stats['total']} "
          f"({stats['accuracy']:.1f}% accuracy)\n")
    if stats['failures']:
        print(f"First 5 failures:")
        for f in stats['failures'][:5]:
            print(f"  {f['word']}: {f['result']['translation']}")
        print()

    # Manual test cases
    tests = [
        (['bia'],             'bịa — bare root'),
        (['i', 'bia'],        'ịbịa — infinitive'),
        (['bia', 'ra'],       'bịara — past tense'),
        (['na', 'e', 'ri'],   'na-eri — progressive'),
        (['a', 'bia', 'ghi'], 'abịaghị — negative past'),
        (['bia', 'cha', 'ra'],'bịachara — exhaustive past'),
        (['ri', 'ju', 'ru'],  'rijuru — ate to satisfaction'),
        (['ga', 'e', 'je'],   'ga-eje — future'),
        (['bia', 'a'],        'SHOULD BE INVALID'),
        (['je', 'gide', 're'],'jegidere — kept going'),
    ]

    print("Manual test cases:")
    for morphemes, label in tests:
        r = fst.analyze(morphemes)
        status = '✅ VALID' if r['valid'] else '❌ INVALID'
        print(f"  {status}  {label}")
        print(f"           {r['translation']}")
        if not r['valid']:
            for step in r['trace']:
                if step['reason']:
                    print(f"           Reason: {step['reason']}")
        print()
