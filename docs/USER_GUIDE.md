# Audit Readiness Ledger: User Guide & Tutorial

## 1. Quick Start

### Launch the Web Assurance Suite
```bash
audit-readiness-ledger --web
```
*(Or directly via Streamlit: `PYTHONPATH=src streamlit run src/audit_readiness_ledger/app.py`)*

Open your browser at **`http://localhost:8501`**. The suite is optimized for desktop monitors, iPads/tablets, and mobile viewports.

---

## 2. Walk-Through: Conducting an On-Site Audit

### Step 1: Initialize Session & Target Scope
1. Open the **Sidebar**.
2. Enter the **Organization Name** (e.g., *Meltemi Logistics S.A.*) and the **Lead Auditor** name.
3. Select the **Audit Date**.

### Step 2: Evaluate Controls on the Interactive Workbench
1. Navigate to the **Interactive Audit Workbench** tab.
2. Select an Annex A Domain tab:
   - **A.5 Organizational Controls** (37 controls)
   - **A.6 People Controls** (8 controls)
   - **A.7 Physical Controls** (14 controls)
   - **A.8 Technological Controls** (34 controls)
3. Expand any control to evaluate:
   - Choose the **Audit State** (`UNASSESSED`, `FULLY IMPLEMENTED`, `PARTIALLY IMPLEMENTED`, `NOT IMPLEMENTED`, `NOT APPLICABLE`).
   - Check or uncheck **Mandatory Hard Gate (Prerequisite)** according to your Statement of Applicability (SoA).
   - Enter **Evidence Notes** (e.g., *"CCTV and physical badge logs verified at Server Room A"*) or enter the **Exclusion Justification** if marked as `NOT APPLICABLE`.
4. The Top Banner and Metrics update dynamically with your changes.

### Step 3: Automated Document Ingestion (Optional)
If the organization has a repository of written policy files (`.docx`, `.md`, `.txt`):
1. Navigate to the **Automated Policy Scanner** tab.
2. Enter the folder path (defaults to the bundled `examples/meltemi-logistics/documents`).
3. Click **Run Automated Document Scan**.
4. The scanner reads the documents, identifies exact term matches, and auto-populates the workbench entries with line-by-line evidence citations.

---

## 3. Managing the Corrective Action Plan (CAP)

For every control marked as `NOT IMPLEMENTED` or `PARTIALLY IMPLEMENTED`:
1. Navigate to the **Corrective Action & Re-Audit** tab.
2. Review the identified gaps:
   - Fill in **Root Cause (What went wrong)**: e.g., *"Decommissioning of legacy reader during renovation"*.
   - Enter **Corrective Action Required**: e.g., *"Install multi-factor biometric lock and update visitor log procedure"*.
   - Assign the **Remediation Owner** and specify a **Target Resolution Date** (`YYYY-MM-DD`).
   - Set status to `IN_PROGRESS` or `PENDING_RE_AUDIT`.

---

## 4. Conducting a Follow-Up Re-Audit

When the organization completes corrective actions:
1. Load the existing audit session via the sidebar (`Resume Saved Audit`).
2. Navigate to **Corrective Action & Re-Audit**.
3. Under the remediated control:
   - Select **Remediation Status** $\rightarrow$ **`VERIFIED_CLOSED`**.
   - Enter **Re-Audit Verification Notes**: e.g., *"On-site physical inspection confirmed new biometric reader operational with alarm integration"*.
   - Enter the **Verified Date**.
4. The Gatekeeper automatically clears the blocker. If all mandatory gates are now satisfied, the top verdict immediately transitions to **`[PASSED]`**.

---

## 5. Session Persistence & Exporting Reports

### Save & Resume Without Microsoft Office
* **Save Session:** Click **Save Current Session (JSON)** in the sidebar to download a `.json` backup of your complete work.
* **Resume Session:** Use the **Resume Saved Audit (JSON)** uploader to continue an assessment on any device or browser without data loss.

### Exporting Formal Deliverables
In the **Executive Assurance Report** tab:
* **Download Formal Report (.md):** A board-level executive report containing the verdict banner, maturity percentage, list of blockers, Corrective Action Plan table, and Lessons Learned.
* **Export Audit Findings (.csv):** A complete data export of all 93 controls, notes, and CAP items.
* **Export Complete Session (.json):** Raw machine-readable audit file.
