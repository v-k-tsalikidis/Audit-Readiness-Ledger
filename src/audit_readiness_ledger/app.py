"""Audit-Readiness-Ledger: Enterprise Audit Workbench & Gatekeeper Suite.

Comprehensive ISO/IEC 27001:2022 Assurance Platform:
- Interactive On-Site Audit Workbench (Mobile/Tablet/Desktop)
- Automated Policy Document Scanner (.docx, .md, .txt)
- Remediation & Re-Audit Verification Lifecycle (CAP / POA&M)
- Portable Session Persistence (Zero Office lock-in via JSON/CSV)
- Formal Executive Assurance Reporting
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from audit_readiness_ledger.cli import analyse, today_here
from audit_readiness_ledger.gates import (
    ISO_27001_DEFAULT_MANDATORY_CONTROLS,
    AccreditationVerdict,
)
from audit_readiness_ledger.hygiene import Status
from audit_readiness_ledger.scoring import score_assessment
from audit_readiness_ledger.signatures import Coverage
from audit_readiness_ledger.workbench import (
    AuditEntry,
    AuditSession,
    AuditState,
    RemediationStatus,
    initialize_blank_session,
)


# Page Configuration
st.set_page_config(
    page_title="Audit Readiness Ledger | ISO 27001 Suite",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Professional Defense & Enterprise Styling
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    .brand-container {
        padding-top: 6px;
        padding-bottom: 18px;
        margin-bottom: 24px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    }

    .brand-title {
        font-family: 'Space Grotesk', -apple-system, sans-serif;
        font-size: 1.95rem;
        font-weight: 800;
        letter-spacing: -0.035em;
        color: #FFFFFF;
        line-height: 1.15;
    }

    .brand-accent {
        color: #3B82F6;
    }

    .brand-subtitle {
        font-family: 'Inter', sans-serif;
        font-size: 0.76rem;
        font-weight: 600;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #94A3B8;
        margin-top: 8px;
        margin-bottom: 0px;
    }

    .metric-card {
        background-color: #0e1117;
        border: 1px solid #262730;
        border-radius: 6px;
        padding: 14px;
        text-align: center;
    }
    .verdict-failed {
        background-color: rgba(220, 38, 38, 0.12);
        border: 2px solid #dc2626;
        border-left: 8px solid #dc2626;
        border-radius: 6px;
        padding: 18px;
        margin-bottom: 20px;
    }
    .verdict-passed-obs {
        background-color: rgba(217, 119, 6, 0.12);
        border: 2px solid #d97706;
        border-left: 8px solid #d97706;
        border-radius: 6px;
        padding: 18px;
        margin-bottom: 20px;
    }
    .verdict-compliant {
        background-color: rgba(16, 185, 129, 0.12);
        border: 2px solid #059669;
        border-left: 8px solid #059669;
        border-radius: 6px;
        padding: 18px;
        margin-bottom: 20px;
    }
    @media (max-width: 768px) {
        .metric-card {
            margin-bottom: 12px;
        }
        .verdict-failed, .verdict-passed-obs, .verdict-compliant {
            padding: 12px;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def find_default_docs_folder() -> Path:
    """Locate bundled Meltemi Logistics example set."""
    base_dir = Path(__file__).resolve().parent.parent.parent
    sample_dir = base_dir / "examples" / "meltemi-logistics" / "documents"
    if sample_dir.exists():
        return sample_dir
    return Path.cwd()


# ---------------- SESSION STATE INITIALIZATION ----------------
if "audit_session" not in st.session_state:
    st.session_state["audit_session"] = initialize_blank_session()

session: AuditSession = st.session_state["audit_session"]


# ---------------- SIDEBAR CONTROLS ----------------
st.sidebar.markdown(
    """
    <div class="brand-container">
        <div class="brand-title">Audit Readiness <span class="brand-accent">Ledger</span></div>
        <div class="brand-subtitle">Assurance, Workbench &amp; Remediation Suite</div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.sidebar.markdown("### Session Management")
uploaded_file = st.sidebar.file_uploader("Resume Saved Audit (JSON)", type=["json"])
if uploaded_file is not None:
    try:
        content = uploaded_file.read().decode("utf-8")
        st.session_state["audit_session"] = AuditSession.from_json(content)
        st.sidebar.success("Audit session loaded.")
        st.rerun()
    except Exception as exc:
        st.sidebar.error(f"Invalid session file: {exc}")

col_meta1, col_meta2 = st.sidebar.columns(2)
with col_meta1:
    session.organization_name = st.text_input("Organization", value=session.organization_name)
with col_meta2:
    session.auditor_name = st.text_input("Lead Auditor", value=session.auditor_name)

session.audit_date = st.sidebar.date_input("Audit Date", value=date.fromisoformat(session.audit_date)).isoformat()

st.sidebar.markdown("---")

# Quick Download Session Button in Sidebar
st.sidebar.download_button(
    label="Save Current Session (JSON)",
    data=session.to_json(),
    file_name=f"audit_session_{session.organization_name.replace(' ', '_')}_{session.audit_date}.json",
    mime="application/json",
    help="Download portable session to resume later on tablet or mobile without software installation",
)

if st.sidebar.button("Reset to Blank Baseline"):
    st.session_state["audit_session"] = initialize_blank_session()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown(
    """
    **Assurance Architecture:**
    - **Dual-Engine:** Separates coverage score from deterministic Pass/Fail Gate.
    - **5-State Model:** Distinguishes unreviewed omissions from formal exclusions.
    - **Zero Lock-In:** Pure JSON/CSV portability; runs offline on any device.
    """
)


# ---------------- TOP VERDICT & METRIC HEADER ----------------
assessment, gate_eval = session.evaluate_assurance()

st.title("ISO/IEC 27001:2022 Assurance & Remediation Suite")
st.caption(
    f"Audit Target: {session.organization_name} | Auditor: {session.auditor_name} | Date: {session.audit_date}"
)

# Render Verdict Banner
if session.unassessed_count > 0:
    st.warning(
        f"ASSESSMENT INCOMPLETE: {session.unassessed_count} controls remain unassessed. "
        "Complete all control evaluations or justify exclusions before finalizing the verdict."
    )

if gate_eval.verdict is AccreditationVerdict.FAILED:
    st.markdown(
        f"""
        <div class="verdict-failed">
            <h3 style="color: #dc2626; margin: 0; font-family: monospace; letter-spacing: 0.05em;">
                [ACCREDITATION VERDICT: FAILED (GATE BLOCKER)]
            </h3>
            <p style="font-size: 1.05rem; margin: 8px 0 0 0; color: #f3f4f6;">
                <strong>{len(gate_eval.blockers)} Mandatory Security Controls</strong> are currently non-compliant.
                In formal ISO 27001 certification or NATO accreditation, open non-conformities on baseline prerequisites invalidate accreditation regardless of overall maturity score.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
elif gate_eval.verdict is AccreditationVerdict.PASSED_WITH_OBSERVATIONS:
    st.markdown(
        f"""
        <div class="verdict-passed-obs">
            <h3 style="color: #d97706; margin: 0; font-family: monospace; letter-spacing: 0.05em;">
                [ACCREDITATION VERDICT: PASSED WITH OBSERVATIONS]
            </h3>
            <p style="font-size: 1.05rem; margin: 8px 0 0 0; color: #f3f4f6;">
                All <strong>{gate_eval.total_mandatory} Mandatory Baseline Gates</strong> are satisfied.
                <strong>{len(gate_eval.observations)} Desirable Controls</strong> remain open as audit observations and are tracked in the Corrective Action Plan.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        """
        <div class="verdict-compliant">
            <h3 style="color: #059669; margin: 0; font-family: monospace; letter-spacing: 0.05em;">
                [ACCREDITATION VERDICT: FULLY COMPLIANT]
            </h3>
            <p style="font-size: 1.05rem; margin: 8px 0 0 0; color: #f3f4f6;">
                All applicable ISO/IEC 27001:2022 controls are fully implemented and verified. Zero open non-conformities.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

# Executive KPI Metrics Row
col_kpi1, col_kpi2, col_kpi3, col_kpi4, col_kpi5 = st.columns(5)
with col_kpi1:
    st.metric("Overall Maturity", f"{assessment.overall_score}%", delta=f"Strict: {assessment.overall_strict_score}%")
with col_kpi2:
    st.metric(
        "Mandatory Gates",
        f"{gate_eval.satisfied_mandatory} / {gate_eval.total_mandatory}",
        delta=f"{gate_eval.mandatory_pass_rate}% Pass Rate",
        delta_color="normal" if gate_eval.satisfied_mandatory == gate_eval.total_mandatory else "inverse",
    )
with col_kpi3:
    st.metric("Desirable Controls", f"{gate_eval.satisfied_desirable} / {gate_eval.total_desirable}", delta=f"{gate_eval.desirable_pass_rate}%")
with col_kpi4:
    st.metric("Open Remediations", f"{session.open_remediations_count}", delta="CAP Items", delta_color="inverse" if session.open_remediations_count > 0 else "off")
with col_kpi5:
    st.metric("Excluded (N/A)", f"{session.excluded_count}", delta=f"{session.unassessed_count} Pending Review", delta_color="off")

st.markdown("---")


# ---------------- PRIMARY TABS ----------------
main_tab_workbench, main_tab_remediation, main_tab_scanner, main_tab_report = st.tabs(
    [
        "Interactive Audit Workbench",
        f"Corrective Action & Re-Audit ({session.open_remediations_count})",
        "Automated Policy Scanner",
        "Executive Assurance Report",
    ]
)


# ==============================================================================
# TAB 1: INTERACTIVE AUDIT WORKBENCH
# ==============================================================================
with main_tab_workbench:
    st.markdown("### On-Site Control Assessment")
    st.caption(
        "Tablet and mobile-friendly evaluation interface. Evaluate controls across the 4 ISO 27001 Annex A domains. "
        "Distinguish verified implementations, partial controls, non-conformities, and formal exclusions."
    )

    domain_tabs = st.tabs([
        "A.5 Organizational Controls (37)",
        "A.6 People Controls (8)",
        "A.7 Physical Controls (14)",
        "A.8 Technological Controls (34)",
    ])

    domain_mapping = {
        0: "Organizational controls",
        1: "People controls",
        2: "Physical controls",
        3: "Technological controls",
    }

    state_labels = {
        AuditState.UNASSESSED: "UNASSESSED (Pending Review)",
        AuditState.FULLY_IMPLEMENTED: "FULLY IMPLEMENTED (100%)",
        AuditState.PARTIALLY_IMPLEMENTED: "PARTIALLY IMPLEMENTED (50%)",
        AuditState.NOT_IMPLEMENTED: "NOT IMPLEMENTED (0% / Gap)",
        AuditState.NOT_APPLICABLE: "NOT APPLICABLE (Excluded via SoA)",
    }

    state_options = list(state_labels.keys())

    for tab_idx, dtab in enumerate(domain_tabs):
        target_theme = domain_mapping[tab_idx]
        with dtab:
            controls_in_theme = [
                entry for entry in session.entries.values() if entry.theme == target_theme
            ]

            for entry in controls_in_theme:
                with st.expander(
                    f"{entry.control_id} — {entry.title} | [{entry.state.value.upper()}] {'[MANDATORY GATE]' if entry.is_mandatory else ''}",
                    expanded=(entry.state is AuditState.UNASSESSED or entry.state is AuditState.NOT_IMPLEMENTED),
                ):
                    c_col1, c_col2 = st.columns([2, 1])

                    with c_col1:
                        new_state = st.selectbox(
                            "Audit State",
                            options=state_options,
                            index=state_options.index(entry.state),
                            format_func=lambda s: state_labels[s],
                            key=f"state_{entry.control_id}",
                        )
                        entry.state = new_state

                        entry.evidence_notes = st.text_area(
                            "Evidence Notes / Justification of Exclusion",
                            value=entry.evidence_notes,
                            key=f"ev_{entry.control_id}",
                            placeholder="Document name, line number, physical observation, or statement of applicability exclusion justification...",
                            height=70,
                        )

                    with c_col2:
                        entry.is_mandatory = st.checkbox(
                            "Mandatory Hard Gate (Prerequisite)",
                            value=entry.is_mandatory,
                            key=f"mand_{entry.control_id}",
                            help="If checked, failure on this control directly fails the accreditation verdict.",
                        )

                        if entry.state in {AuditState.NOT_IMPLEMENTED, AuditState.PARTIALLY_IMPLEMENTED}:
                            st.caption("Non-conformity detected: Recorded in Corrective Action Plan.")
                            if entry.remediation_status is RemediationStatus.NOT_APPLICABLE:
                                entry.remediation_status = RemediationStatus.OPEN
                        elif entry.state in {AuditState.FULLY_IMPLEMENTED, AuditState.NOT_APPLICABLE}:
                            if entry.remediation_status is RemediationStatus.OPEN:
                                entry.remediation_status = RemediationStatus.NOT_APPLICABLE


# ==============================================================================
# TAB 2: CORRECTIVE ACTION PLAN & RE-AUDIT LIFECYCLE
# ==============================================================================
with main_tab_remediation:
    st.markdown("### Corrective Action Plan (CAP) & Re-Audit Tracking")
    st.caption(
        "Track remediation of identified gaps. When a corrective action is verified on-site, "
        "record the re-audit check to resolve the blocker and update the accreditation verdict."
    )

    gaps_requiring_action = [
        entry
        for entry in session.entries.values()
        if entry.state in {AuditState.NOT_IMPLEMENTED, AuditState.PARTIALLY_IMPLEMENTED}
        or entry.remediation_status is not RemediationStatus.NOT_APPLICABLE
    ]

    if not gaps_requiring_action:
        st.success("No open non-conformities or corrective actions required. All applicable controls are verified.")
    else:
        remed_status_options = [
            RemediationStatus.OPEN,
            RemediationStatus.IN_PROGRESS,
            RemediationStatus.PENDING_RE_AUDIT,
            RemediationStatus.VERIFIED_CLOSED,
        ]

        for entry in gaps_requiring_action:
            gate_badge = "[MANDATORY BLOCKER]" if entry.is_mandatory else "[OBSERVATION]"
            with st.container():
                st.markdown(f"#### {entry.control_id}: {entry.title} `{gate_badge}`")
                r_col1, r_col2, r_col3 = st.columns([2, 2, 1])

                with r_col1:
                    entry.root_cause = st.text_area(
                        "Root Cause (What went wrong)",
                        value=entry.root_cause,
                        key=f"rc_{entry.control_id}",
                        placeholder="e.g. Access control hardware decommissioned during refurbishment...",
                        height=80,
                    )
                    entry.corrective_action = st.text_area(
                        "Corrective Action Required (What must be fixed)",
                        value=entry.corrective_action,
                        key=f"ca_{entry.control_id}",
                        placeholder="e.g. Install biometric reader and integrate alarm monitoring...",
                        height=80,
                    )

                with r_col2:
                    entry.remediation_owner = st.text_input(
                        "Remediation Owner",
                        value=entry.remediation_owner,
                        key=f"owner_{entry.control_id}",
                        placeholder="e.g. Facilities & CISO",
                    )
                    entry.target_date = st.text_input(
                        "Target Resolution Date",
                        value=entry.target_date,
                        key=f"tdate_{entry.control_id}",
                        placeholder="YYYY-MM-DD",
                    )
                    entry.verification_notes = st.text_area(
                        "Re-Audit Verification Notes",
                        value=entry.verification_notes,
                        key=f"vnotes_{entry.control_id}",
                        placeholder="Auditor observation upon re-inspection...",
                        height=70,
                    )

                with r_col3:
                    current_idx = (
                        remed_status_options.index(entry.remediation_status)
                        if entry.remediation_status in remed_status_options
                        else 0
                    )
                    new_status = st.selectbox(
                        "Remediation Status",
                        options=remed_status_options,
                        index=current_idx,
                        format_func=lambda s: s.value.upper(),
                        key=f"rstat_{entry.control_id}",
                    )
                    entry.remediation_status = new_status

                    if new_status is RemediationStatus.VERIFIED_CLOSED:
                        entry.verified_date = st.text_input(
                            "Verified Date",
                            value=entry.verified_date or date.today().isoformat(),
                            key=f"vdate_{entry.control_id}",
                        )
                        st.success("Remediation Verified: Blocker resolved in Gatekeeper.")

                st.markdown("---")


# ==============================================================================
# TAB 3: AUTOMATED POLICY SCANNER
# ==============================================================================
with main_tab_scanner:
    st.markdown("### Automated Policy Document Ingestion")
    st.caption(
        "Deterministic textual analysis of .docx, .md, and .txt policy files. "
        "Scans your document library and automatically maps verified text hits to ISO 27001 controls."
    )

    scan_folder_input = st.text_input(
        "Local Policy Folder Path",
        value=str(find_default_docs_folder()),
        help="Directory holding .docx, .md, .txt files to ingest",
    )

    col_scan_btn1, col_scan_btn2 = st.columns([1, 2])
    with col_scan_btn1:
        trigger_scan = st.button("Run Automated Document Scan")

    if trigger_scan:
        with st.spinner("Scanning policy folder deterministically..."):
            folder_path = Path(scan_folder_input)
            if not folder_path.exists() or not folder_path.is_dir():
                st.error(f"Directory not found: {folder_path}")
            else:
                try:
                    analysis_result = analyse(folder_path, "iso-27001-2022", date.today())
                    st.success(f"Scan complete: Read {len(analysis_result.documents_read)} files.")

                    # Auto-populate workbench entries from document findings
                    updated_count = 0
                    for finding in analysis_result.findings:
                        cid = finding.control_id
                        if cid in session.entries:
                            if finding.coverage is Coverage.ADDRESSED:
                                session.entries[cid].state = AuditState.FULLY_IMPLEMENTED
                                hits_summary = ", ".join(f"{h.document}:L{h.line}" for h in finding.hits[:2])
                                session.entries[cid].evidence_notes = f"Verified via document scan: {hits_summary}"
                                updated_count += 1
                            elif finding.coverage is Coverage.UNCLEAR:
                                session.entries[cid].state = AuditState.PARTIALLY_IMPLEMENTED
                                session.entries[cid].evidence_notes = "Partial evidence found in scan (Unclear/Deferred)."
                                updated_count += 1
                            elif finding.coverage is Coverage.NOT_ADDRESSED:
                                session.entries[cid].state = AuditState.NOT_IMPLEMENTED
                                session.entries[cid].evidence_notes = "No document in set speaks to this control."
                                updated_count += 1

                    st.info(f"Workbench synchronized: {updated_count} controls updated from document evidence.")
                    st.rerun()
                except Exception as err:
                    st.error(f"Error during scan: {err}")


# ==============================================================================
# TAB 4: EXECUTIVE ASSURANCE REPORT
# ==============================================================================
with main_tab_report:
    st.markdown("### Formal Executive Audit Report")
    st.caption("Audit-grade executive summary formatted for governance boards and certifying authorities.")

    session.lessons_learned = st.text_area(
        "Auditor Remarks & Lessons Learned",
        value=session.lessons_learned,
        placeholder="Document general observations, organizational readiness strengths, and strategic recommendations...",
        height=90,
    )

    # Domain Breakdown Chart
    theme_records = []
    for tname, tscore in assessment.theme_scores.items():
        theme_records.append({
            "Domain": tname.replace(" controls", ""),
            "Score %": tscore.score_percentage,
            "Addressed": tscore.addressed,
            "Unclear": tscore.unclear,
            "Not Addressed": tscore.not_addressed,
            "Total": tscore.total,
        })
    df_report_themes = pd.DataFrame(theme_records)

    st.markdown("#### Domain Maturity Breakdown")
    st.bar_chart(df_report_themes.set_index("Domain")[["Score %"]], color="#2563eb", height=240)

    # Markdown Report Generator
    def build_full_markdown_report() -> str:
        lines = [
            f"# ISO/IEC 27001:2022 Executive Audit & Assurance Report",
            f"\n**Target Organization:** {session.organization_name}  ",
            f"**Lead Auditor:** {session.auditor_name}  ",
            f"**Audit Date:** {session.audit_date}  ",
            f"**Framework:** {session.framework_name}\n",
            f"## 1. Executive Accreditation Verdict\n",
            f"- **Verdict:** `{gate_eval.verdict_label}`",
            f"- **Overall Maturity Score:** **{assessment.overall_score}%** (Strict Pass Rate: {assessment.overall_strict_score}%)",
            f"- **Mandatory Baseline Gates:** **{gate_eval.satisfied_mandatory} / {gate_eval.total_mandatory} ({gate_eval.mandatory_pass_rate}%)**",
            f"- **Desirable Controls:** **{gate_eval.satisfied_desirable} / {gate_eval.total_desirable} ({gate_eval.desirable_pass_rate}%)**",
            f"- **Formal Exclusions (N/A):** **{session.excluded_count}** controls\n",
            f"## 2. Mandatory Gate Blockers ({len(gate_eval.blockers)})\n",
        ]
        if gate_eval.blockers:
            lines.append("| Control ID | Title | Domain | Audit Finding |")
            lines.append("| :--- | :--- | :--- | :--- |")
            for b in gate_eval.blockers:
                e = session.entries.get(b.control_id)
                lines.append(f"| **{b.control_id}** | {e.title if e else ''} | {e.theme if e else ''} | **BLOCKER (Non-Conformity)** |")
        else:
            lines.append("Zero mandatory gate blockers identified. All baseline security prerequisites satisfied.\n")

        lines.append("\n## 3. Corrective Action Plan (CAP) & Remediation Tracker\n")
        cap_items = [e for e in session.entries.values() if e.remediation_status is not RemediationStatus.NOT_APPLICABLE]
        if cap_items:
            lines.append("| Control | Action Required | Owner | Target Date | Status |")
            lines.append("| :--- | :--- | :--- | :--- | :--- |")
            for ci in cap_items:
                lines.append(f"| **{ci.control_id}** | {ci.corrective_action or 'Action pending'} | {ci.remediation_owner or '-'} | {ci.target_date or '-'} | `{ci.remediation_status.value.upper()}` |")
        else:
            lines.append("No active corrective action items recorded.\n")

        if session.lessons_learned:
            lines.append(f"\n## 4. Auditor Remarks & Lessons Learned\n")
            lines.append(session.lessons_learned + "\n")

        lines.append(f"\n## 5. Domain Maturity Summary\n")
        lines.append("| Domain | Score % | Addressed | Unclear | Not Addressed | Total |")
        lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
        for tr in theme_records:
            lines.append(f"| {tr['Domain']} | {tr['Score %']}% | {tr['Addressed']} | {tr['Unclear']} | {tr['Not Addressed']} | {tr['Total']} |")

        return "\n".join(lines)

    report_markdown = build_full_markdown_report()

    col_rep_btn1, col_rep_btn2, col_rep_btn3 = st.columns(3)
    with col_rep_btn1:
        st.download_button(
            label="Download Formal Report (.md)",
            data=report_markdown,
            file_name=f"ISO_27001_Audit_Report_{session.organization_name.replace(' ', '_')}_{session.audit_date}.md",
            mime="text/markdown",
        )
    with col_rep_btn2:
        st.download_button(
            label="Export Audit Findings (.csv)",
            data=session.to_csv(),
            file_name=f"ISO_27001_Findings_{session.organization_name.replace(' ', '_')}_{session.audit_date}.csv",
            mime="text/csv",
        )
    with col_rep_btn3:
        st.download_button(
            label="Export Complete Session (.json)",
            data=session.to_json(),
            file_name=f"ISO_27001_Session_{session.organization_name.replace(' ', '_')}_{session.audit_date}.json",
            mime="application/json",
        )

    st.markdown("#### Preview")
    st.markdown(report_markdown)
