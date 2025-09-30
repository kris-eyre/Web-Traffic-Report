# app.py — Unify Engagement: Web Activity + Master Merge (Streamlit)
# ---------------------------------------------------------------------
# Corrected to match intent: detailed rows from all sources, with blanks for unknown contacts,
# derived columns per row, rep fragment filter, unassigned without duplicates.
# Modified to upload Master Account List instead of reading from disk.

import hashlib
from typing import List

import streamlit as st
import pandas as pd

st.set_page_config(page_title="Unify Engagement — Web Activity + Master Merge", page_icon="🧩", layout="wide")
st.title("Unify Engagement — Web Activity Merge (Known + Unknown + Intent) with Master Rep Mapping")

# -----------------------------
# Sidebar: mappings & settings
# -----------------------------
with st.sidebar:
    st.header("Web-Activity Column Mapping")
    st.caption("These apply to the three uploaded activity files.")
    col_account = st.text_input("Account Name column (activity)", value="Account Name")
    col_details = st.text_input("Details column (activity)", value="Details")
    col_first = st.text_input("First Name column (known only)", value="First Name")
    col_last = st.text_input("Last Name column (known only)", value="Last Name")
    col_title = st.text_input("Title column (known only)", value="Title")

    st.header("Master Account List Settings")
    master_account_col = st.text_input("Account Name column (master)", value="Account Name")
    master_rep_col = st.text_input("Current Team - Primary column (master)", value="Current Team - Primary")
    master_ind_col = st.text_input("Industry column (master, for email theming)", value="Industry (SF)")

    st.subheader("Rep Filter (for Rep Accounts output)")
    rep_frags = st.text_input(
        "Rep fragments (comma-separated)",
        value="",
        help="Filters the Rep Accounts output to accounts whose Current Team - Primary contains any fragment (case-insensitive). Leave blank to include all assigned accounts.",
    )

    st.subheader("De-duplication & Normalization")
    normalize_names = st.checkbox("Normalize Account Name (trim, collapse spaces, casefold)", value=True)

st.write("Upload the four files: Known Activity, Unknown Activity, Intent, and Master Account List.")

# -----------------------------
# Uploads
# -----------------------------
col1, col2, col3, col4 = st.columns(4)
with col1:
    f_known = st.file_uploader("Known Activity (CSV/XLSX)", type=["csv", "xlsx"], key="known")
with col2:
    f_unknown = st.file_uploader("Unknown Activity (CSV/XLSX)", type=["csv", "xlsx"], key="unknown")
with col3:
    f_intent = st.file_uploader("Intent (CSV/XLSX)", type=["csv", "xlsx"], key="intent")
with col4:
    f_master = st.file_uploader("Master Account List (XLSX)", type=["xlsx"], key="master")

# -----------------------------
# Utilities
# -----------------------------
def safe_str(x) -> str:
    try:
        return "" if pd.isna(x) else str(x).strip()
    except Exception:
        return "" if x is None else str(x).strip()

def read_any(file) -> pd.DataFrame:
    if file is None:
        return pd.DataFrame()
    name = file.name.lower()
    if name.endswith(".csv"):
        df = pd.read_csv(file)
    else:
        df = pd.read_excel(file)
    # Attach origin filename
    df["Origin File"] = file.name
    return df

def norm_account(x: str) -> str:
    s = safe_str(x)
    if normalize_names:
        s = " ".join(s.split()).casefold()
    return s

def product_from_details(details: str) -> str:
    d = safe_str(details).lower()
    eam_triggers = [
        "eam", "asset management", "hxgn eam", "hxgn-eam", "enterprise-asset-management",
        "maintenance", "equipment management", "preventative maintenance", "asset data"
    ]
    if any(t in d for t in eam_triggers):
        return "HxGN EAM/APM"
    if ("asset performance" in d) or ("apm" in d):
        return "HxGN APM"
    if any(t in d for t in ["quality", "etq", "qms", "compliance"]):
        return "ETQ"
    if any(t in d for t in ["project-management", "controls", "ecosys"]):
        return "Ecosys"
    if "measuring-machines" in d:
        return "Scanner"
    if "cadworx" in d:
        return "CADWorx"
    if "caesar" in d:
        return "CAESAR II"
    if any(t in d for t in ["productivity-and-efficiency", "digital transformation"]):
        return "J5/AKMS"
    if "acceleratorkms" in d:
        return "AKMS"
    return "N/A"

def norm_industry(text: str) -> str:
    s = safe_str(text).lower()
    if any(k in s for k in ["aerospace", "defense"]): return "aerospace"
    if any(k in s for k in ["automotive", "vehicle", "mobility"]): return "automotive"
    if any(k in s for k in ["oil", "gas", "o&g", "energy", "upstream", "midstream", "downstream", "refining"]): return "energy"
    if any(k in s for k in ["life science", "pharma", "biotech", "medical"]): return "lifesciences"
    if any(k in s for k in ["food", "beverage", "f&b"]): return "foodbev"
    if any(k in s for k in ["chem", "petrochem"]): return "chemicals"
    if any(k in s for k in ["utilities", "power", "generation", "transmission", "distribution"]): return "utilities"
    if any(k in s for k in ["mining", "metals"]): return "mining"
    if any(k in s for k in ["electronics", "semiconductor", "high-tech", "hi tech", "hitech"]): return "hitech"
    if any(k in s for k in ["discrete", "machinery", "heavy", "industrial"]): return "discrete"
    if s: return "other"
    return "discrete"  # default

def role_category(title: str) -> str:
    t = safe_str(title).lower()
    if any(k in t for k in ["chief ", "cxo", "ceo", "cfo", "coo", "cio", "cto", "ciso", "president"]):
        return "exec"
    if any(k in t for k in ["svp", "evp"]): return "exec"
    if "vice president" in t or "vp" in t: return "vp"
    if "director" in t: return "director"
    if any(k in t for k in ["quality", "compliance", "qms", "regulatory"]): return "quality"
    if any(k in t for k in ["maintenance", "reliability", "asset", "condition monitoring"]): return "maintenance"
    if any(k in t for k in ["project controls", "project manager", "program manager", "pmo"]): return "projects"
    if any(k in t for k in ["operations", "manufacturing", "plant manager", "production"]): return "operations"
    if any(k in t for k in ["engineering", "design", "cad", "piping"]): return "engineering"
    if any(k in t for k in ["ehs", "hse", "safety"]): return "safety"
    if any(k in t for k in ["it ", "ot ", "information technology", "industrial it", "systems", "data"]): return "it"
    if any(k in t for k in ["manager", "lead", "head"]): return "manager"
    return "ic"

def deterministic_pick(key: str, n: int) -> int:
    if n <= 0: return 0
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return int(h[:8], 16) % n

SUBJECT_THEMES = {
    "maintenance": {
        "discrete": [
            "Cut unplanned downtime on the line with {product}",
            "Stabilize asset uptime in discrete manufacturing with {product}",
            "Fewer surprises on critical equipment — {product}"
        ],
        "aerospace": [
            "Improve fleet & ground asset uptime — {product}",
            "Maintenance leaders in A&D: reduce reactive work with {product}",
            "A&D uptime without extra headcount — {product}"
        ],
        "default": [
            "Improve asset reliability with {product}",
            "Cut unplanned downtime — {product}",
            "Predictable performance from critical assets — {product}"
        ]
    },
    "quality": {
        "default": [
            "Faster quality cycles & cleaner audits — {product}",
            "Reduce compliance friction with {product}",
            "Make quality predictable with {product}"
        ]
    },
    "projects": {
        "default": [
            "Project controls that hold the line — {product}",
            "Stop late surprises in cost & schedule — {product}",
            "Forecast accuracy that sticks — {product}"
        ]
    },
    "operations": {
        "default": [
            "Make operations predictable with {product}",
            "Control variability across shifts — {product}",
            "Fewer bottlenecks, clearer flow — {product}"
        ]
    },
    "engineering": {
        "default": [
            "Deliver designs faster with {product}",
            "Reduce rework & surprises — {product}",
            "Cleaner models, cleaner handoffs — {product}"
        ]
    },
    "safety": {
        "default": [
            "Lower incident risk without slowing the line — {product}",
            "Simplify compliance and improve safety — {product}",
            "Fewer near-misses with better visibility — {product}"
        ]
    },
    "it": {
        "default": [
            "Less tool sprawl, clearer outcomes — {product}",
            "Integrations without the drag — {product}",
            "Operate with a simpler stack — {product}"
        ]
    },
    "vp": {
        "default": [
            "Improve predictability without adding complexity — {product}",
            "Visibility you can act on — {product}",
            "Hold the line on margin with {product}"
        ]
    },
    "exec": {
        "default": [
            "Improve margin predictability with {product}",
            "Operational confidence across sites — {product}",
            "Clarity on reliability, quality & cost — {product}"
        ]
    },
    "director": {
        "default": [
            "Boost cross-team visibility — {product}",
            "Make execution repeatable with {product}",
            "Fewer fires, more follow-through — {product}"
        ]
    },
    "manager": {
        "default": [
            "Hit targets with less churn — {product}",
            "Keep teams moving in the same direction — {product}",
            "Less busywork, more progress — {product}"
        ]
    },
    "ic": {
        "default": [
            "Remove busywork and move faster — {product}",
            "Make work easier with {product}",
            "Clarity to execute — {product}"
        ]
    }
}

ROLE_P1 = {
    "maintenance": ["You’re asked to keep uptime high with constrained headcount.", "Manual PMs miss early failure signals."],
    "quality": ["Audits and deviations slow teams down.", "Teams chase documents across silos."],
    "projects": ["Forecast accuracy slips as change orders stack up.", "Cost control is fragile without a clear source of truth."],
    "operations": ["Throughput swings with schedule volatility.", "Firefighting replaces flow when visibility is late."],
    "engineering": ["Late clashes force expensive changes.", "Design cycles stretch when models aren’t aligned."],
    "safety": ["Incidents rise when reporting is fragmented.", "Compliance pulls time from proactive safety work."],
    "it": ["Integrations inflate cost while ops still lack clear signal.", "Maintaining brittle connections slows initiatives."],
    "vp": ["Hard to improve predictability without adding complexity.", "Targets compete without clear visibility."],
    "exec": ["Board-level targets require repeatable execution.", "Confidence erodes when risk is invisible until late."],
    "director": ["Cross-team consistency is hard without bureaucracy.", "Leaders end up firefighting instead of driving change."],
    "manager": ["Coordinating under pressure leads to churn and misses.", "Getting consistent execution is hard."],
    "ic": ["Disconnected tools slow delivery.", "Workarounds pile up when process isn’t clear."]
}
ROLE_P2 = {
    "maintenance": ["Left unresolved, it drives firefighting and lost production.", "The cost shows up as overtime and missed targets."],
    "quality": ["Unresolved, it prolongs investigations and risks customer trust.", "It becomes margin drag through scrap and rework."],
    "projects": ["Unresolved, it erodes margin and forces late cuts.", "It leads to unpredictable forecasts."],
    "operations": ["Unresolved, it causes schedule misses and unstable output.", "It keeps teams reactive."],
    "engineering": ["Unresolved, it creates rework and missed launch milestones.", "It adds expensive late fixes."],
    "safety": ["Unresolved, it elevates risk and drags productivity.", "It exposes the business to incidents."],
    "it": ["Unresolved, it inflates TCO and stalls initiatives.", "Unresolved, it creates shadow IT."],
    "vp": ["Unresolved, it clouds forecasting and compresses margins.", "It makes planning fragile."],
    "exec": ["Unresolved, it undermines predictability and confidence.", "It leaves strategy vulnerable."],
    "director": ["Unresolved, it blocks visibility and creates fires.", "It derails roadmaps."],
    "manager": ["Unresolved, it causes churn and KPI misses.", "It makes it hard to coach."],
    "ic": ["Unresolved, it adds busywork and slows delivery.", "It keeps the signal buried in noise."]
}

PRODUCT_P3 = {
    "HxGN EAM/APM": ["Move to predictable uptime: connected asset data, prioritized work.", "Earlier signals, planned interventions, extended asset life."],
    "HxGN APM": ["Spot risks earlier and act before failures.", "Reliability gains from early detection."],
    "ETQ": ["Faster closings, automated evidence, and cleaner audits.", "Quality that flows without delays."],
    "Ecosys": ["Project controls that hold the line.", "See slippage sooner and act with confidence."],
    "Scanner": ["Quicker inspections and faster issue detection.", "Close the loop faster between measurement and correction."],
    "CADWorx": ["Fewer clashes and faster design cycles.", "Intelligent models reduce rework."],
    "CAESAR II": ["Trusted stress analysis for safer designs.", "Decisions backed by industry-standard analysis."],
    "J5/AKMS": ["Standardize shift handover and logs.", "Create operational clarity across teams."],
    "AKMS": ["Codify best practices and reduce error.", "Make procedures easy to follow and auditable."],
    "N/A": ["Clearer execution and measurable outcomes.", "Predictability without adding complexity."]
}
PRODUCT_P3_VERB = {
    "HxGN EAM/APM": ["move from reactive to reliable", "plan work before it breaks"],
    "HxGN APM": ["act before failures", "prioritize by risk"],
    "ETQ": ["cut audit drag", "shorten quality cycles"],
    "Ecosys": ["hold the line on cost", "forecast with confidence"],
    "Scanner": ["speed up inspection", "catch issues earlier"],
    "CADWorx": ["deliver designs faster", "reduce rework"],
    "CAESAR II": ["de-risk piping decisions", "accelerate approvals"],
    "J5/AKMS": ["standardize operations", "create transparency across shifts"],
    "AKMS": ["codify procedures", "reduce human-factor errors"],
    "N/A": ["improve execution", "create clarity"]
}
CTA_P4 = [
    "Would a 20-minute discussion next week be useful to compare how others in {industry} approach this?",
    "Open to a brief session next week to benchmark {industry} peers and quantify impact?",
    "Would a quick 20-min chat help explore where {product} could remove friction in {industry}?"
]

def subject_line(product: str, title: str, industry_norm: str, account: str) -> str:
    a = safe_str(account)
    t = safe_str(title)
    p = safe_str(product)
    ind = safe_str(industry_norm)
    cat = role_category(t)
    pool = SUBJECT_THEMES.get(cat, SUBJECT_THEMES["ic"])
    choices = pool.get(ind, pool.get("default", ["Improve performance with {product}"]))
    idx = deterministic_pick(a + t + p, len(choices))
    return choices[idx].format(product=p)

def build_email_body(first: str, title: str, account: str, product: str, details: str, industry_norm: str) -> str:
    fn = safe_str(first).title()
    ttl = safe_str(title)
    acct = safe_str(account)
    prod = safe_str(product)
    det = safe_str(details) or "the page you explored"
    ind_read = {
        "discrete": "discrete manufacturing",
        "aerospace": "aerospace & defense",
        "energy": "energy / oil & gas",
        "lifesciences": "life sciences",
        "foodbev": "food & beverage",
        "chemicals": "chemicals",
        "utilities": "utilities",
        "mining": "mining & metals",
        "hitech": "electronics / high-tech",
        "other": "your industry"
    }.get(industry_norm or "discrete", "your industry")

    cat = role_category(ttl)
    p1_choices = ROLE_P1.get(cat, ROLE_P1["ic"])
    p2_choices = ROLE_P2.get(cat, ROLE_P2["ic"])
    p3_choices = PRODUCT_P3.get(prod, PRODUCT_P3["N/A"])
    verb_choices = PRODUCT_P3_VERB.get(prod, PRODUCT_P3_VERB["N/A"])

    i1 = deterministic_pick(acct + "p1", len(p1_choices))
    i2 = deterministic_pick(acct + "p2", len(p2_choices))
    i3 = deterministic_pick(acct + "p3", len(p3_choices))
    i4 = deterministic_pick(acct + "v", len(verb_choices))
    i5 = deterministic_pick(acct + "cta", len(CTA_P4))

    greeting = f"Hi {fn}," if fn else "Hello,"
    para1 = f"{greeting} as a {ttl or 'professional'} at {acct}, teams often face the same challenge: {p1_choices[i1]}"
    para2 = f"{p2_choices[i2]} Leaders we work with in {ind_read} want fewer surprises and clearer signal."
    para3 = f"{p3_choices[i3]} In short, {verb_choices[i4]} without adding complexity."
    para4 = CTA_P4[i5].format(industry=ind_read, product=prod) + f" I can tailor it to your context and the interest we saw around \"{det}\"."

    signature = (
        "—\n"
        "Best regards,\n"
        "<Your Name>\n"
        "Hexagon\n"
        "<Phone> | <Email>"
    )

    return "\n\n".join([para1, para2, para3, para4, signature])

if all([f_known, f_unknown, f_intent, f_master]):
    # Read activity files
    df_known = read_any(f_known)
    df_unknown = read_any(f_unknown)
    df_intent = read_any(f_intent)
    master = read_any(f_master)

    df_known["__Source__"] = "Known"
    df_unknown["__Source__"] = "Unknown"
    df_intent["__Source__"] = "Intent"

    # Concat all activity, with First/Last/Title only in known (NaN elsewhere)
    activity = pd.concat([df_known, df_unknown, df_intent], ignore_index=True, sort=False)

    # Validate required columns in activity
    missing_act = [c for c in [col_account, col_details] if c not in activity.columns]
    if missing_act:
        st.error(f"Activity file(s) missing required column(s): {', '.join(missing_act)}")
    else:
        # Validate master columns
        missing_master = [c for c in [master_account_col, master_rep_col] if c not in master.columns]
        if missing_master:
            st.error(f"Master file missing required column(s): {', '.join(missing_master)}")
            st.stop()

        # Normalize keys
        activity["__acct_key__"] = activity[col_account].apply(norm_account)
        master["__acct_key__"] = master[master_account_col].apply(norm_account)

        # Merge rep and industry from master (left join, so unmatched get NaN)
        merge_cols = [master_rep_col]
        if master_ind_col in master.columns:
            merge_cols.append(master_ind_col)
        master_slim = master[["__acct_key__"] + merge_cols].drop_duplicates(subset="__acct_key__")
        merged = activity.merge(master_slim, on="__acct_key__", how="left")

        # Fill NaNs for output
        for c in [col_first, col_last, col_title]:
            if c in merged.columns:
                merged[c] = merged[c].fillna("")

        # Derived columns per row
        merged["Product Solution"] = merged[col_details].apply(product_from_details)
        merged["Industry Norm"] = merged.get(master_ind_col, "").apply(norm_industry)  # for internal use

        # Compute Subject and Email per row
        merged["Subject Line"] = merged.apply(
            lambda r: subject_line(
                r["Product Solution"],
                r.get(col_title, ""),
                r["Industry Norm"],
                r[col_account]
            ),
            axis=1
        )
        merged["Email Body"] = merged.apply(
            lambda r: build_email_body(
                r.get(col_first, ""),
                r.get(col_title, ""),
                r[col_account],
                r["Product Solution"],
                r[col_details],
                r["Industry Norm"]
            ),
            axis=1
        )

        # Assigned: rep not blank/NaN
        merged[master_rep_col] = merged[master_rep_col].fillna("")
        merged["Assigned"] = merged[master_rep_col].astype(bool)

        # Split
        with_rep = merged[merged["Assigned"]].copy()
        without_rep = merged[~merged["Assigned"]].copy()

        # Rep fragments filter (case-insensitive partial match)
        frags = [f.strip().lower() for f in rep_frags.split(",") if f.strip()]
        if frags:
            mask = with_rep[master_rep_col].str.lower().apply(lambda s: any(f in s for f in frags))
            with_rep = with_rep[mask]

        # Sort by Account Name
        with_rep = with_rep.sort_values(col_account)
        without_rep = without_rep.sort_values(col_account)

        # Final columns (Current Team - Primary is master_rep_col, blanks where appropriate)
        out_cols = [master_rep_col, col_account, col_first, col_last, col_title, col_details,
                    "Product Solution", "Subject Line", "Email Body", "Origin File"]

        # Filter to existing columns
        with_rep_out = with_rep[[c for c in out_cols if c in with_rep.columns]]
        without_rep_out = without_rep[[c for c in out_cols if c in without_rep.columns]]

        # Metrics
        st.success(f"Merged {len(merged):,} activity rows across {len(merged['__acct_key__'].unique()):,} unique accounts.")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Total Activity Rows", len(merged))
        with c2:
            st.metric("Assigned Rows (pre-filter)", len(merged[merged["Assigned"]]))
        with c3:
            st.metric("Unassigned Rows", len(without_rep))

        st.subheader("Preview: Rep Accounts (filtered by rep fragments)")
        st.dataframe(with_rep_out.head(25), use_container_width=True)

        st.subheader("Preview: Unassigned Web Activity")
        st.dataframe(without_rep_out.head(25), use_container_width=True)

        # Downloads
        st.download_button(
            "⬇️ Download — Rep Accounts",
            with_rep_out.to_csv(index=False).encode("utf-8"),
            file_name="rep_accounts.csv",
            mime="text/csv",
        )
        st.download_button(
            "⬇️ Download — Unassigned Web Activity",
            without_rep_out.to_csv(index=False).encode("utf-8"),
            file_name="unassigned_web_activity.csv",
            mime="text/csv",
        )
else:
    st.info("Upload all four files (Known, Unknown, Intent, and Master Account List) to begin.")