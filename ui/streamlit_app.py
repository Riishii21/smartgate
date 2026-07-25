"""Operations console for the request triage workflow.

Written for a service-desk handler rather than an engineer: the case card is the
unit of work, plain language is used throughout, and every automated decision is
shown together with the reason behind it.
"""
import json
import pathlib
import sys
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import config
from services import report, store
from workflow.graph import process

ROOT = pathlib.Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "data" / "sample_requests"

TYPE_LABEL = {
    "billing_dispute": "Billing dispute",
    "general_enquiry": "General enquiry",
    "service_request": "Service request",
    "complaint": "Complaint",
}
TYPE_BLURB = {
    "billing_dispute": "The customer is contesting a charge on their account.",
    "general_enquiry": "The customer wants information. Nothing needs changing on the account.",
    "service_request": "The customer is asking us to do something to their account.",
    "complaint": "The customer is unhappy with how we have handled something.",
}
URGENCY_STYLE = {
    "low":      ("#616B7A", "#F0F1F3"),
    "medium":   ("#1A5FA5", "#E8F0F8"),
    "high":     ("#B8791C", "#FBF2E3"),
    "critical": ("#A32235", "#FAEAEC"),
}
TYPE_FG, TYPE_BG = "#1E2360", "#EAECF5"

st.set_page_config(page_title="SmartGate — card servicing", page_icon="📋", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

:root {
  --navy:#1E2360; --navy-deep:#151A47; --navy-bg:#EAECF5;
  --orange:#EE7623; --orange-bg:#FDF0E6;
  --ink:#14181F; --slate:#5A6270; --mute:#858C9B;
  --rule:#DFE2EC; --paper:#FBFBFC; --card:#FFFFFF;
  --teal:#0F6B4F; --teal-bg:#E7F2ED;
  --amber:#B8791C; --amber-bg:#FBF2E3;
  --crimson:#A32235; --crimson-bg:#FAEAEC;
  --violet:#453A9E; --violet-bg:#ECEAF8;
}

html, body, [class*="css"] { font-family:'Inter',system-ui,sans-serif; }
.block-container { padding-top:2rem; max-width:1220px; }

h1, h2, h3 { font-family:'Archivo',sans-serif !important; letter-spacing:-0.02em !important; }

/* masthead */
.masthead { background:var(--navy); border-bottom:3px solid var(--orange); padding:20px 24px 18px 24px;
            margin:0 0 4px 0; border-radius:6px 6px 0 0; }
.masthead-row { display:flex; align-items:baseline; justify-content:space-between; }
.masthead h1 { font-size:30px !important; font-weight:700 !important; margin:0 !important;
                color:#FFFFFF !important; }
.masthead-tag { font-family:'IBM Plex Mono',monospace; font-size:11px; letter-spacing:0.09em;
                text-transform:uppercase; color:var(--orange); }
.masthead-sub { font-size:13.5px; color:#B9BFDA; margin-top:9px; }

/* case file */
.filehead { display:flex; justify-content:space-between; align-items:flex-start;
            padding:2px 0 14px 0; border-bottom:1px solid var(--rule); margin-bottom:16px; }
.fileref { font-family:'IBM Plex Mono',monospace; font-size:11.5px; color:var(--mute);
           text-align:right; line-height:1.7; }
.tag { display:inline-block; padding:3px 11px; border-radius:3px; font-size:11.5px;
       font-weight:600; letter-spacing:0.03em; margin-right:7px;
       font-family:'IBM Plex Mono',monospace; text-transform:uppercase; }

/* status stripe */
.stripe { border-left:3px solid; padding:15px 20px; margin:4px 0 22px 0; background:var(--card); }
.stripe-held { border-color:var(--crimson); background:var(--crimson-bg); }
.stripe-auto { border-color:var(--teal); background:var(--teal-bg); }
.stripe-h { font-family:'Archivo',sans-serif; font-weight:700; font-size:15.5px; margin-bottom:3px; }
.stripe-b { font-size:13.5px; color:var(--slate); }
.stripe-reasons { margin-top:9px; padding-top:9px; border-top:1px solid rgba(0,0,0,.07); }
.stripe-reason { font-size:13px; padding:2px 0; }

/* chain of custody */
.chain { position:relative; padding-left:30px; margin-top:4px; }
.chain::before { content:''; position:absolute; left:9px; top:8px; bottom:14px; width:1px;
                 background:var(--rule); }
.link { position:relative; padding-bottom:16px; }
.link::before { content:''; position:absolute; left:-25px; top:5px; width:9px; height:9px;
                border-radius:50%; background:var(--orange); box-shadow:0 0 0 3px var(--paper); }
.link-name { font-weight:600; font-size:14px; color:var(--ink); }
.link-detail { font-size:12.5px; color:var(--slate); margin-top:3px; line-height:1.5; }

/* eyebrow */
.eyebrow { font-family:'IBM Plex Mono',monospace; font-size:10.5px; letter-spacing:0.11em;
           text-transform:uppercase; color:var(--navy); margin:26px 0 11px 0;
           padding-bottom:5px; border-bottom:1px solid var(--rule); }

/* data rows */
.row { padding:9px 0; border-bottom:1px solid var(--rule); }
.row-k { font-family:'IBM Plex Mono',monospace; font-size:10.5px; letter-spacing:0.07em;
         text-transform:uppercase; color:var(--mute); }
.row-v { font-size:14px; color:var(--ink); margin-top:2px; }

.tabnote { font-size:13.5px; color:var(--slate); line-height:1.55; margin:4px 0 20px 0;
          padding-bottom:14px; border-bottom:1px solid var(--rule); max-width:760px; }
.note { font-size:12.5px; color:var(--slate); line-height:1.55; }
.sb-h { font-family:'Archivo',sans-serif; font-weight:600; font-size:12px; letter-spacing:0.05em;
        text-transform:uppercase; color:var(--navy); margin-bottom:9px; }
.sb-t { font-size:13px; color:var(--slate); line-height:1.6; }

section[data-testid="stSidebar"] { background:var(--navy-bg); border-right:1px solid var(--rule); }
.stTabs [aria-selected="true"] { color:var(--navy) !important; }
.stTabs [data-baseweb="tab-highlight"] { background:var(--orange) !important; }
button[kind="primary"] { background:var(--orange) !important; border-color:var(--orange) !important; }
button[kind="primary"]:hover { background:#D96716 !important; border-color:#D96716 !important; }
.sb-brand { font-family:'Archivo',sans-serif; font-weight:700; font-size:17px; color:var(--navy); }
.stTabs [data-baseweb="tab"] { font-family:'Archivo',sans-serif; font-weight:600; font-size:13.5px; }
div[data-testid="stMetricValue"] { font-family:'Archivo',sans-serif; font-weight:700; }
div[data-testid="stMetricLabel"] { font-family:'IBM Plex Mono',monospace; font-size:10.5px !important;
                                    letter-spacing:0.07em; text-transform:uppercase; }
</style>
""", unsafe_allow_html=True)


def parse_sample(path: pathlib.Path):
    text = path.read_text(encoding="utf-8").strip()
    subject = ""
    if text.lower().startswith("subject:"):
        first, _, rest = text.partition("\n")
        subject = first.split(":", 1)[1].strip()
        text = rest.strip()
    return subject, text


def pill(text: str, fg: str, bg: str) -> str:
    return f'<span class="tag" style="background:{bg}; color:{fg}">{text}</span>'


def urgency_pill(urgency: str) -> str:
    fg, bg = URGENCY_STYLE.get(str(urgency).lower(), URGENCY_STYLE["low"])
    return pill(f"{str(urgency)} priority", fg, bg)


def waiting_text(iso: str) -> str:
    """How long a case has been sitting, in the way a handler would say it."""
    if not iso:
        return "—"
    try:
        elapsed = datetime.now(timezone.utc) - datetime.fromisoformat(iso)
        mins = elapsed.total_seconds() / 60
        if mins < 1:
            return "just now"
        if mins < 60:
            return f"{int(mins)} min ago"
        if mins < 48 * 60:
            return f"{mins / 60:.0f} hr ago"
        return f"{mins / 1440:.0f} days ago"
    except ValueError:
        return "—"


def sla_text(iso: str) -> str:
    if not iso:
        return "Not set"
    try:
        remaining = datetime.fromisoformat(iso) - datetime.now(timezone.utc)
        hours = remaining.total_seconds() / 3600
        if hours <= 0:
            return "Overdue"
        if hours < 1:
            return f"{int(hours * 60)} minutes"
        if hours < 48:
            return f"{hours:.0f} hours"
        return f"{hours / 24:.0f} days"
    except ValueError:
        return "Not set"


def render_steps(actions) -> None:
    links = []
    for action in actions:
        step = action["step"] if isinstance(action, dict) else action.step
        detail = action["detail"] if isinstance(action, dict) else action.detail
        links.append(f'<div class="link"><div class="link-name">{step}</div>'
                     f'<div class="link-detail">{detail}</div></div>')
    st.markdown(f'<div class="chain">{"".join(links)}</div>', unsafe_allow_html=True)


def render_case(state: dict) -> None:
    cls = state["classification"]
    held = state.get("hold_for_human")

    st.markdown(
        f'<div class="filehead"><div>'
        f'{pill(TYPE_LABEL.get(cls.request_type.value, ""), TYPE_FG, TYPE_BG)}'
        f'{urgency_pill(cls.urgency.value)}'
        f'<div style="margin-top:9px; font-size:14px; color:var(--slate)">'
        f'{TYPE_BLURB.get(cls.request_type.value, "")}</div></div>'
        f'<div class="fileref">{state["case_id"]}<br>'
        f'{state["received_at"][:16].replace("T", " ")}<br>'
        f'via {state.get("channel", "email")}</div></div>',
        unsafe_allow_html=True)

    if held:
        reasons = "".join(f'<div class="stripe-reason">— {r}</div>'
                          for r in state.get("hold_reasons", []))
        st.markdown(
            f'<div class="stripe stripe-held"><div class="stripe-h">Waiting for a person</div>'
            f'<div class="stripe-b">Nothing has been sent to the customer. This case is queued '
            f'for {state["routed_to"]}.</div>'
            f'<div class="stripe-reasons">{reasons}</div></div>', unsafe_allow_html=True)
    else:
        st.markdown(
            f'<div class="stripe stripe-auto"><div class="stripe-h">Handled automatically</div>'
            f'<div class="stripe-b">Passed every check and was actioned without a person. '
            f'Sent to {state["routed_to"]}.</div></div>', unsafe_allow_html=True)

    left, right = st.columns([3, 2], gap="large")

    with left:
        st.markdown('<div class="eyebrow">Chain of actions</div>', unsafe_allow_html=True)
        render_steps(state["actions"])

        st.markdown('<div class="eyebrow">Draft reply</div>', unsafe_allow_html=True)
        st.caption("Edit before sending if needed." if held
                   else "This reply was cleared for sending automatically.")
        st.text_area("Draft", value=state.get("draft_response", ""), height=185,
                     key=f"draft_{state['case_id']}", label_visibility="collapsed")

    with right:
        st.markdown('<div class="eyebrow">Case record</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="row"><div class="row-k">Assigned to</div>'
                    f'<div class="row-v">{state["routed_to"]}</div></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="row"><div class="row-k">Response due in</div>'
                    f'<div class="row-v">{sla_text(state.get("sla_due_at", ""))}</div></div>',
                    unsafe_allow_html=True)
        sure = ("acted on" if cls.confidence >= config.CONFIDENCE_THRESHOLD
                else "below the bar — a person checks")
        st.markdown(f'<div class="row"><div class="row-k">Classification certainty</div>'
                    f'<div class="row-v">{cls.confidence:.0%} — {sure}</div></div>',
                    unsafe_allow_html=True)

        vulns = [v.value.replace("_", " ") for v in cls.vulnerability_signals if v.value != "none"]
        if vulns:
            st.write("")
            st.error(f"**Customer may need extra support** — {', '.join(vulns)} mentioned. Assigned to "
                     "a trained handler, and automatic replies are switched off for this case.")

        note = state.get("notification")
        if note:
            st.write("")
            label = ("Supervisor alerted" if note["channel"] == "alert"
                     else "Added to the team's queue")
            with st.expander(f"{label} — {note['to']}", expanded=note["channel"] == "alert"):
                st.caption(note["subject"])
                st.code(note["body"], language=None)
                st.caption("Simulated. In deployment this is the payload handed to email, "
                           "Slack, or the ticketing system.")

        if state.get("pii_found"):
            st.write("")
            st.info("**Personal details protected** — " + ", ".join(state["pii_found"]).lower()
                    + " were replaced before the message was sent to the AI, then restored afterwards.")

        if cls.entities:
            st.markdown('<div class="eyebrow">Extracted from the message</div>', unsafe_allow_html=True)
            for k, v in cls.entities.items():
                st.markdown(f'<div class="row"><div class="row-k">{k.replace("_", " ")}</div>'
                            f'<div class="row-v">{v}</div></div>', unsafe_allow_html=True)

        with st.expander("Full decision history"):
            for event in state.get("audit", []):
                st.markdown(f'**{event["node"]}** · {event["ts"][11:19]}  \n{event["decision"]}  \n'
                            f'<span class="meta">{event.get("detail", "")}</span>', unsafe_allow_html=True)
                st.divider()


with st.sidebar:
    st.markdown('<div class="sb-brand">SmartGate</div>', unsafe_allow_html=True)
    st.caption("Card servicing · customer messages")
    st.divider()
    st.markdown('<div class="sb-h">How this works</div>', unsafe_allow_html=True)
    st.markdown('<div class="sb-t">'
                "Every incoming message is read, sorted "
                "into one of four types, and put through the right process for that type.<br><br>"
                "Straightforward cases are handled end to end. Anything sensitive stops and waits for "
                "a person.</div>", unsafe_allow_html=True)
    st.divider()
    st.markdown('<div class="sb-h">Always reviewed by a person</div>', unsafe_allow_html=True)
    st.markdown('<div class="sb-t">'
                "— complaints<br>"
                "— anyone mentioning bereavement, hardship or illness<br>"
                "— anything urgent<br>"
                "— anything the system isn't sure about</div>", unsafe_allow_html=True)
    st.divider()
    st.caption(f"Model: {config.active_model()}")
    if config.LLM_PROVIDER == "nvidia" and not config.NVIDIA_API_KEY:
        st.error("No NVIDIA key set — every case will be held.")
    elif config.LLM_PROVIDER == "groq" and not config.GROQ_API_KEY:
        st.error("No Groq key set — every case will be held.")


st.markdown(
    '<div class="masthead"><div class="masthead-row">'
    '<h1>SmartGate</h1>'
    '<span class="masthead-tag">Card servicing &nbsp;·&nbsp; customer messages</span>'
    '</div><div class="masthead-sub">Every message that comes in is read, sorted, and either dealt '
    'with straight away or passed to the right person — with the reason attached.</div></div>',
    unsafe_allow_html=True)

tab_process, tab_queue, tab_overview = st.tabs(
    ["  Handle a message  ", "  Needs your approval  ", "  How the desk is doing  "])

with tab_process:
    st.markdown('<div class="tabnote"><b>In use, messages arrive on their own</b> — from the shared '
                'mailbox, a web form, or an API call — and are handled without anyone opening them '
                'first. Nobody reads an inbox. This page is for putting a single message through by '
                'hand: to see how the desk reasons, or to deal with something that came in by an '
                'unusual route.<br><br>To watch a batch arrive the way it would in practice, use '
                '<i>Run all the examples at once</i> at the bottom of this page.</div>',
                unsafe_allow_html=True)
    sample_files = sorted(SAMPLES.glob("*.txt"))
    nice = {p.name: p.name[3:].replace("_", " ").replace(".txt", "").title() for p in sample_files}

    col_l, col_r = st.columns([2, 1], gap="large")
    choice = col_l.selectbox("Try one of the example messages",
                             ["I'll paste my own message"] + [nice[p.name] for p in sample_files])
    uploaded = col_r.file_uploader("Or open a saved message", type=["txt"])

    subject_default, text_default = "", ""
    if uploaded is not None:
        raw = uploaded.read().decode("utf-8").strip()
        if raw.lower().startswith("subject:"):
            first, _, rest = raw.partition("\n")
            subject_default, text_default = first.split(":", 1)[1].strip(), rest.strip()
        else:
            text_default = raw
    elif choice != "I'll paste my own message":
        path = next(p for p in sample_files if nice[p.name] == choice)
        subject_default, text_default = parse_sample(path)

    c1, c2 = st.columns([3, 1])
    subject = c1.text_input("What the subject line said", value=subject_default)
    channel = c2.selectbox("How it reached us", ["email", "web form", "shared inbox"])
    body = st.text_area("What the customer wrote", value=text_default, height=175,
                        placeholder="Paste what the customer wrote…")

    if st.button("Handle this message", type="primary", disabled=not body.strip()):
        with st.spinner("Reading the message and working out what it needs…"):
            st.session_state["last_case"] = process(body, subject=subject, channel=channel)

    if "last_case" in st.session_state:
        st.divider()
        render_case(st.session_state["last_case"])

    st.divider()
    with st.expander("Run all the examples at once"):
        st.caption("Handles all six example messages one after another, so you can see a full day's work.")
        if st.button("Simulate an inbox arriving"):
            bar = st.progress(0.0, text="Starting…")
            for i, path in enumerate(sample_files, 1):
                subj, txt = parse_sample(path)
                bar.progress(i / len(sample_files), text=f"Processing {nice[path.name]}…")
                process(txt, subject=subj, channel="email")
            bar.empty()
            st.success(f"Processed {len(sample_files)} messages. Open the Queue tab to see them.")

with tab_queue:
    st.markdown('<div class="tabnote"><b>This is the only list a handler works from.</b> Everything '
                'here was stopped deliberately — nothing has gone to these customers. Read why it '
                'stopped, adjust the reply, and send it. Everything not on this list was already '
                'dealt with.</div>', unsafe_allow_html=True)
    try:
        store.init_db()
        cases = store.all_cases()
    except Exception as exc:
        cases = []
        st.error(f"Could not read the case store: {exc}")

    if not cases:
        st.info("Nothing here yet. Process a request on the first tab and it will appear.")
    else:
        df = pd.DataFrame(cases)
        waiting = int(df["hold_for_human"].sum())

        c1, c2, c3 = st.columns(3)
        held_rows = df[df["hold_for_human"] == 1]
        oldest = waiting_text(held_rows["received_at"].min()) if len(held_rows) else "—"
        c1.metric("Cases", len(df))
        c2.metric("Waiting for a person", waiting)
        c3.metric("Longest wait", oldest)

        st.divider()
        f1, f2 = st.columns([1, 2])
        only_held = f1.checkbox("Only show ones still waiting")
        type_filter = f2.multiselect(
            "Show only these kinds",
            sorted({TYPE_LABEL.get(t, t) for t in df["request_type"].dropna().unique()}))

        view = df.copy()
        if only_held:
            view = view[view["hold_for_human"] == 1]
        if type_filter:
            wanted = [k for k, v in TYPE_LABEL.items() if v in type_filter]
            view = view[view["request_type"].isin(wanted)]

        # Oldest first: a handler works a queue from the top of the wait, not the newest arrival.
        view = view.sort_values("received_at")
        st.dataframe(pd.DataFrame({
            "Arrived": view["received_at"].str[11:16],
            "Waiting": view["received_at"].map(waiting_text),
            "Subject": view["subject"],
            "Type": view["request_type"].map(lambda t: TYPE_LABEL.get(t, t)),
            "Urgency": view["urgency"].str.title(),
            "Reply due": view["sla_due_at"].map(sla_text),
            "Goes to": view["routed_to"],
            "Case": view["case_id"],
        }), use_container_width=True, hide_index=True)
        st.caption("Oldest first. 'Reply due' counts down to the response target for that type — "
                   "one hour for complaints, eight hours for service requests.")

        d1, d2 = st.columns([1, 3])
        with d1:
            if st.button("Prepare review pack"):
                rows = view.to_dict("records")
                st.session_state["queue_pdf"] = report.build_review_pdf(
                    rows, {r["case_id"]: store.audit_for(r["case_id"]) for r in rows},
                    title="Case review — cases awaiting approval" if only_held else "Case review")
        with d2:
            if "queue_pdf" in st.session_state:
                st.download_button(
                    "Download review pack (PDF)", st.session_state["queue_pdf"],
                    file_name=f"case-review-{datetime.now().strftime('%Y%m%d-%H%M')}.pdf",
                    mime="application/pdf", type="primary")
        st.caption("A printable record of these cases — what each customer wrote, how the desk "
                   "classified it, what it did, what it drafted, and why anything stopped. "
                   "For quality review and audit sampling.")

        st.divider()
        if len(view):
            selected = st.selectbox("Open one to work on it", view["case_id"].tolist())
            row = df[df["case_id"] == selected].iloc[0]

            st.markdown(
                f'<div class="filehead"><div>'
                f'{pill(TYPE_LABEL.get(row["request_type"], ""), TYPE_FG, TYPE_BG)}'
                f'{urgency_pill(row["urgency"])}</div>'
                f'<div class="fileref">{row["case_id"]}<br>'
                f'arrived {str(row["received_at"])[:16].replace("T", " ")}<br>'
                f'waiting {waiting_text(row["received_at"])}</div></div>',
                unsafe_allow_html=True)

            if row["hold_for_human"]:
                reasons = "".join(f'<div class="stripe-reason">— {r}</div>'
                                  for r in json.loads(row["hold_reasons"] or "[]"))
                st.markdown(f'<div class="stripe stripe-held">'
                            f'<div class="stripe-h">Waiting for you</div>'
                            f'<div class="stripe-reasons">{reasons}</div></div>',
                            unsafe_allow_html=True)

            st.markdown('<div class="eyebrow">Chain of actions</div>', unsafe_allow_html=True)
            render_steps(json.loads(row["actions"] or "[]"))

            st.markdown('<div class="eyebrow">Draft reply</div>', unsafe_allow_html=True)
            st.text_area("Reply", value=row["draft_response"], height=175,
                         key=f"q_{selected}", label_visibility="collapsed")

            if row["hold_for_human"]:
                if st.button("Approve and send", type="primary"):
                    store.approve_case(selected)
                    st.success("Approved. The reply is marked as sent and your approval is recorded.")
                    st.rerun()
            else:
                st.caption("This case was handled automatically. No approval needed.")

            st.download_button(
                "Download this case as a PDF",
                report.build_review_pdf([row.to_dict()], {selected: store.audit_for(selected)},
                                        title=f"Case review — {selected}"),
                file_name=f"{selected}.pdf", mime="application/pdf")

            with st.expander("Full decision history"):
                for event in store.audit_for(selected):
                    st.markdown(f'**{event["node"]}** · {event["ts"][11:19]}  \n{event["decision"]}  \n'
                                f'<span class="meta">{event.get("detail", "")}</span>',
                                unsafe_allow_html=True)
                    st.divider()

with tab_overview:
    st.markdown('<div class="tabnote">How much is coming in, how much the desk cleared on its own, '
                'and which teams are carrying the load.</div>', unsafe_allow_html=True)
    try:
        store.init_db()
        cases = store.all_cases()
    except Exception:
        cases = []

    if not cases:
        st.info("Nothing here yet. Process some requests and the numbers will appear.")
    else:
        df = pd.DataFrame(cases)
        held, total = int(df["hold_for_human"].sum()), len(df)

        m1, m2, m3 = st.columns(3)
        m1.metric("Messages processed", total)
        m2.metric("Cleared without a person", f"{(total - held) / total:.0%}")
        m3.metric("Sent to a person", held)

        st.caption("Cases reach a person by design, not by failure — complaints and customers in "
                   "difficult circumstances are always reviewed by a trained handler.")

        st.divider()
        left, right = st.columns(2, gap="large")
        with left:
            st.markdown("**What is coming in**")
            st.bar_chart(df["request_type"].map(lambda t: TYPE_LABEL.get(t, t)).value_counts(),
                         color="#1E2360", horizontal=True)
        with right:
            st.markdown("**Where cases ended up**")
            st.bar_chart(df["status"].str.replace("_", " ").str.capitalize().value_counts(),
                         color="#EE7623", horizontal=True)

        st.divider()
        e1, e2 = st.columns([1, 3])
        with e1:
            if st.button("Prepare full report"):
                st.session_state["all_pdf"] = report.build_review_pdf(
                    cases, {c["case_id"]: store.audit_for(c["case_id"]) for c in cases},
                    title="Case review — every message handled")
        with e2:
            if "all_pdf" in st.session_state:
                st.download_button(
                    "Download full report (PDF)", st.session_state["all_pdf"],
                    file_name=f"front-desk-report-{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf", type="primary")
        st.caption("Every message the desk has handled, with the reply it produced and the reasoning "
                   "behind each decision.")

        st.divider()
        st.markdown("**Workload by team**")
        workload = df.groupby("routed_to").agg(
            Cases=("case_id", "count"),
            Waiting=("hold_for_human", "sum"),
        ).sort_values("Cases", ascending=False)
        workload.index.name = "Team"
        st.dataframe(workload, use_container_width=True)