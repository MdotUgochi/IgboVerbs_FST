"""
Visual Transducer for Igbo Verb Morphology
"""

import streamlit as st
import graphviz
import csv, os, random
from igbo_fst import load_corpus, extract_patterns, IgboFST

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Igbo Visual Transducer",
    page_icon="🔤",
    layout="wide"
)

# ── Load FST (cached) ─────────────────────────────────────────────────────────
@st.cache_resource
def get_fst():
    corpus   = load_corpus('igbo_verbs_final.csv')
    patterns = extract_patterns(corpus)
    fst      = IgboFST(patterns)
    return fst, corpus, patterns

fst, corpus, patterns = get_fst()

# ── State colour map ──────────────────────────────────────────────────────────
STATE_COLORS = {
    'START':        '#E8F4FD',
    'AUX':          '#FFF3CD',
    'PREFIX':       '#D4EDDA',
    'BOUND_PREFIX': '#D1ECF1',
    'ROOT':         '#CCE5FF',
    'EXT_SUFFIX':   '#E2D9F3',
    'IMP_SUFFIX':   '#FCE4EC',
    'INFL_SUFFIX':  '#F8D7DA',
    'REJECT':       '#F5C6CB',
}
ACCEPT_STATES = {'ROOT', 'EXT_SUFFIX', 'IMP_SUFFIX', 'INFL_SUFFIX'}

def build_diagram(active_state='START', trace=None):
    g = graphviz.Digraph(comment='Igbo FST')
    g.attr(rankdir='LR', bgcolor='transparent', fontname='Helvetica')
    g.attr('node', fontname='Helvetica', fontsize='12')

    visited_states = {t['state'] for t in trace} if trace else set()
    visited_states.add('START')

    for state, props in IgboFST.STATES.items():
        is_active  = state == active_state
        is_accept  = props['is_accept']
        is_visited = state in visited_states

        color      = STATE_COLORS.get(state, '#ffffff')
        penwidth   = '3' if is_active else '1'
        style      = 'filled,bold' if is_active else ('filled,dashed' if is_accept else 'filled')
        fontcolor  = '#000000'
        shape      = 'doublecircle' if is_accept else 'circle'

        if is_active:
            color = '#FF6B35'
            fontcolor = '#FFFFFF'
        elif state == 'REJECT':
            color = '#FFCCCC'

        g.node(state, label=state.replace('_','\n'),
               shape=shape, style=style, fillcolor=color,
               fontcolor=fontcolor, penwidth=penwidth,
               width='1.0', height='1.0')

    # Draw transitions
    drawn = set()
    for (from_s, mtype), to_s in IgboFST.TRANSITIONS.items():
        key = (from_s, to_s, mtype)
        if key not in drawn:
            # Check if this edge was traversed
            is_used = False
            if trace:
                for i, step in enumerate(trace):
                    prev = trace[i-1]['state'] if i > 0 else 'START'
                    if step['type'] == mtype and prev == from_s:
                        is_used = True
                        break
            g.edge(from_s, to_s,
                   label=mtype.replace('_','\n'),
                   color='#FF6B35' if is_used else '#888888',
                   penwidth='2.5' if is_used else '1',
                   fontsize='9',
                   fontcolor='#FF6B35' if is_used else '#555555')
            drawn.add(key)

    return g

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🔤 Igbo Visual Transducer")
    st.caption("A pedagogical FST for Igbo verb morphology")
    st.divider()
    mode = st.radio("Mode", [
        "🔬 Analyze",
        "🎯 Predict (Active)",
        "🧩 Build a Word",
        "📊 Corpus Stats"
    ])
    st.divider()
    st.markdown("**Morpheme Types**")
    type_guide = {
        "aux":          "Auxiliary verb (na, ga)",
        "prefix":       "Derivational prefix (i, e, a, ị)",
        "bound_prefix": "Bound participle prefix",
        "root":         "Core verb root",
        "ext_suffix":   "Extensional suffix (meaning modifier)",
        "imp_suffix":   "Imperative suffix",
        "infl_suffix":  "Inflectional suffix (tense/aspect/neg)",
    }
    for t, desc in type_guide.items():
        st.markdown(f"**{t}** — {desc}")

# ══════════════════════════════════════════════════════════════════════════════
# MODE 1 — ANALYZE
# ══════════════════════════════════════════════════════════════════════════════
if mode == "🔬 Analyze":
    st.title("Morphological Analysis")
    st.markdown("Enter an Igbo verb form as pipe-separated morphemes, or type the full word.")

    col1, col2 = st.columns([1, 1])

    with col1:
        input_mode = st.radio("Input type", ["Pre-segmented (morphemes)", "Full word (auto-segment)"],
                              horizontal=True)

        if input_mode == "Pre-segmented (morphemes)":
            user_input = st.text_input("Enter morphemes separated by |",
                                       placeholder="e.g.  bia | cha | ra",
                                       key="seg_input")
            if user_input:
                morphemes = [m.strip() for m in user_input.split('|') if m.strip()]
                result = fst.analyze(morphemes)
                segments = morphemes
        else:
            user_input = st.text_input("Enter full word",
                                       placeholder="e.g.  bịachara",
                                       key="word_input")
            if user_input:
                result, segments = fst.analyze_word(user_input.strip())

        if user_input:
            # Result badge
            if result['valid']:
                st.success(f"✅ **VALID** — Final state: {result['final_state']}")
            else:
                st.error(f"❌ **INVALID** — Rejected at: {result['final_state']}")

            # Translation
            st.markdown(f"**Translation:** `{result['translation']}`")

            # Step-by-step trace
            st.markdown("**Step-by-step trace:**")
            for i, step in enumerate(result['trace']):
                icon = "✅" if step['state'] != 'REJECT' else "❌"
                st.markdown(
                    f"{icon} Step {i+1}: `{step['segment']}` → "
                    f"**{step['type'].upper()}** → state: `{step['state']}`"
                )
                if step['reason']:
                    st.caption(f"   ⚠️ {step['reason']}")

    with col2:
        st.markdown("**FST State Diagram**")
        if user_input and result:
            diagram = build_diagram(result['final_state'], result['trace'])
        else:
            diagram = build_diagram('START', [])
        st.graphviz_chart(diagram, use_container_width=True)

        if user_input and result:
            st.markdown("**Legend:** 🟠 = active/traversed state")

# ══════════════════════════════════════════════════════════════════════════════
# MODE 2 — PREDICT (Active Engagement — Hundhausen et al. 2002, 71% condition)
# ══════════════════════════════════════════════════════════════════════════════
elif mode == "🎯 Predict (Active)":
    st.title("Predict the Next State")
    st.markdown(
        "This mode implements **active engagement** (Hundhausen et al., 2002). "
        "Predict which state the FST will enter before seeing the result."
    )

    if 'predict_word' not in st.session_state:
        st.session_state.predict_word = None
        st.session_state.predict_step = 0
        st.session_state.predict_score = 0
        st.session_state.predict_total = 0
        st.session_state.predict_trace = []
        st.session_state.predict_state = 'START'
        st.session_state.predict_feedback = None

    col1, col2 = st.columns([1, 1])

    with col1:
        if st.button("🎲 Load Random Word"):
            entry = random.choice(corpus)
            st.session_state.predict_word = entry
            st.session_state.predict_step = 0
            st.session_state.predict_trace = []
            st.session_state.predict_state = 'START'
            st.session_state.predict_feedback = None
            fst.reset()

        if st.session_state.predict_word:
            entry = st.session_state.predict_word
            morphemes = entry['morphemes']
            step_idx  = st.session_state.predict_step

            st.markdown(f"**Word:** `{entry['word']}` — *{entry['glosses']}*")
            st.markdown(f"**Morphemes:** {' | '.join(morphemes)}")
            st.divider()

            # Show completed steps
            for i, t in enumerate(st.session_state.predict_trace):
                st.markdown(f"✅ Step {i+1}: `{t['segment']}` → **{t['state']}**")

            if step_idx < len(morphemes):
                current_seg = morphemes[step_idx]
                st.markdown(f"**Current segment:** `{current_seg}`")
                st.markdown(f"**Current state:** `{st.session_state.predict_state}`")

                prediction = st.selectbox(
                    "Predict the next state:",
                    options=list(IgboFST.STATES.keys()),
                    key=f"pred_{step_idx}"
                )

                if st.button("Submit Prediction"):
                    # Run actual FST step
                    fst.current_state = st.session_state.predict_state
                    fst.output_labels = []
                    fst.trace = []
                    new_state, label, reason = fst.step(current_seg)

                    st.session_state.predict_total += 1
                    correct = (prediction == new_state)
                    if correct:
                        st.session_state.predict_score += 1
                        st.session_state.predict_feedback = ('correct', new_state, label)
                    else:
                        st.session_state.predict_feedback = ('wrong', new_state, label, prediction)

                    st.session_state.predict_trace.append({
                        'segment': current_seg, 'state': new_state, 'label': label
                    })
                    st.session_state.predict_state = new_state
                    st.session_state.predict_step += 1
                    st.rerun()

            else:
                final = st.session_state.predict_state
                if IgboFST.STATES[final]['is_accept']:
                    st.success(f"✅ Complete! Final state: **{final}** — VALID word")
                else:
                    st.error(f"❌ Complete! Final state: **{final}** — INVALID word")

            # Feedback
            if st.session_state.predict_feedback:
                fb = st.session_state.predict_feedback
                if fb[0] == 'correct':
                    st.success(f"✅ Correct! → `{fb[1]}` | {fb[2]}")
                else:
                    st.error(f"❌ Wrong. You predicted `{fb[3]}`, actual: `{fb[1]}` | {fb[2]}")

            # Score
            if st.session_state.predict_total > 0:
                pct = st.session_state.predict_score / st.session_state.predict_total * 100
                st.metric("Prediction Accuracy",
                          f"{st.session_state.predict_score}/{st.session_state.predict_total}",
                          f"{pct:.0f}%")

    with col2:
        st.markdown("**FST State Diagram**")
        diagram = build_diagram(
            st.session_state.predict_state,
            st.session_state.predict_trace
        )
        st.graphviz_chart(diagram, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# MODE 3 — BUILD A WORD
# ══════════════════════════════════════════════════════════════════════════════
elif mode == "🧩 Build a Word":
    st.title("Build a Valid Igbo Verb")
    st.markdown("Assemble morpheme tiles to construct a valid verb form.")

    if 'build_morphemes' not in st.session_state:
        st.session_state.build_morphemes = []

    all_morphemes = {}
    for mtype in ['aux', 'prefix', 'bound_prefix', 'root', 'ext_suffix', 'imp_suffix', 'infl_suffix']:
        all_morphemes[mtype] = sorted(patterns.get(mtype, set()))

    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("**Add morphemes:**")
        for mtype, forms in all_morphemes.items():
            if forms:
                selected = st.selectbox(f"Add {mtype}:", ['— skip —'] + forms,
                                        key=f"build_{mtype}")
                if st.button(f"Add {mtype}", key=f"add_{mtype}"):
                    if selected != '— skip —':
                        st.session_state.build_morphemes.append((selected, mtype))
                        st.rerun()

        if st.button("🗑️ Clear"):
            st.session_state.build_morphemes = []
            st.rerun()

        st.divider()
        if st.session_state.build_morphemes:
            morpheme_list = [m for m, _ in st.session_state.build_morphemes]
            result = fst.analyze(morpheme_list)

            assembled = '-'.join(morpheme_list)
            st.markdown(f"**Assembled:** `{assembled}`")
            st.markdown(f"**Translation:** `{result['translation']}`")

            if result['valid']:
                st.success(f"✅ VALID verb form! Final state: {result['final_state']}")
            else:
                st.error(f"❌ INVALID — {result['final_state']}")
                for step in result['trace']:
                    if step['reason']:
                        st.caption(f"⚠️ {step['reason']}")

    with col2:
        st.markdown("**FST State Diagram**")
        if st.session_state.build_morphemes:
            morpheme_list = [m for m, _ in st.session_state.build_morphemes]
            result = fst.analyze(morpheme_list)
            diagram = build_diagram(result['final_state'], result['trace'])
        else:
            diagram = build_diagram('START', [])
        st.graphviz_chart(diagram, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# MODE 4 — CORPUS STATS
# ══════════════════════════════════════════════════════════════════════════════
elif mode == "📊 Corpus Stats":
    st.title("Corpus Statistics")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Entries", len(corpus))
    col2.metric("Unique Roots", len(patterns['root']))
    col3.metric("Sequence Patterns", len(patterns['sequences']))
    col4.metric("Ext. Suffixes", len(patterns['ext_suffix']))

    st.divider()
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Sequence Patterns (by frequency)**")
        from collections import Counter
        seq_counts = Counter(entry['gram_cat'] for entry in corpus)
        for cat, count in seq_counts.most_common(15):
            st.markdown(f"`{cat}` — {count} entries")

    with col2:
        st.markdown("**Morpheme Sets**")
        for mtype in ['aux','prefix','bound_prefix','root','ext_suffix','imp_suffix','infl_suffix']:
            mset = sorted(patterns.get(mtype, set()))
            st.markdown(f"**{mtype}** ({len(mset)}): {', '.join(f'`{m}`' for m in mset)}")

    st.divider()
    st.markdown("**Corpus Sample**")
    sample = random.sample(corpus, min(10, len(corpus)))
    for entry in sample:
        st.markdown(
            f"`{entry['word']}` — {entry['glosses']} | "
            f"`{' | '.join(entry['morphemes'])}` | "
            f"*{' | '.join(entry['types'])}*"
        )
