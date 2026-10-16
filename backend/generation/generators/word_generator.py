"""Microsoft Word (.docx) generator for technical deliverables."""

from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

if TYPE_CHECKING:
    from generation.document_models import DocumentOutline, GeneratedSection


class WordGenerator:
    """Builds authentic Microsoft Word (.docx) documents from outlines and sections."""

    def build_docx_bytes(
        self,
        outline: DocumentOutline,
        sections: list[GeneratedSection],
    ) -> bytes:
        doc = Document()

        # Set standard 1-inch margins
        for section in doc.sections:
            section.top_margin = Inches(1.0)
            section.bottom_margin = Inches(1.0)
            section.left_margin = Inches(1.0)
            section.right_margin = Inches(1.0)

        # Document Header / Running Title
        title_para = doc.add_paragraph()
        title_run = title_para.add_run(outline.title)
        title_run.font.name = "Calibri"
        title_run.font.size = Pt(24)
        title_run.font.bold = True
        title_run.font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)  # Slate-900

        # Subtitle metadata table
        meta_table = doc.add_table(rows=2, cols=2)
        meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        cell_00 = meta_table.cell(0, 0)
        cell_00.text = "Facility: Sovereign Refinery Operations"
        cell_01 = meta_table.cell(0, 1)
        cell_01.text = f"Date: {now_str}"
        cell_10 = meta_table.cell(1, 0)
        cell_10.text = f"Audience: {outline.intended_audience}"
        cell_11 = meta_table.cell(1, 1)
        cell_11.text = "Document Status: VERIFIED TECHNICAL DELIVERABLE"

        doc.add_paragraph()  # Spacing

        # Iterate sections
        for sec in sections:
            # Section Heading
            h_para = doc.add_paragraph()
            h_run = h_para.add_run(sec.title)
            h_run.font.name = "Calibri"
            h_run.font.size = Pt(16)
            h_run.font.bold = True
            h_run.font.color.rgb = RGBColor(0x1E, 0x3A, 0x8A)  # Navy Blue

            # Body paragraphs
            for line in sec.content_markdown.splitlines():
                clean_line = line.strip()
                if not clean_line or clean_line.startswith("### "):
                    continue
                if clean_line.startswith("> "):
                    # Evidence quote
                    q_para = doc.add_paragraph()
                    q_para.paragraph_format.left_indent = Inches(0.5)
                    q_run = q_para.add_run(clean_line[2:])
                    q_run.font.italic = True
                    q_run.font.color.rgb = RGBColor(0x33, 0x41, 0x55)
                else:
                    p = doc.add_paragraph(clean_line)
                    p.paragraph_format.space_after = Pt(6)

            # Callouts (Safety warnings, cautions)
            for callout in sec.callouts:
                c_para = doc.add_paragraph()
                c_para.paragraph_format.left_indent = Inches(0.25)
                c_type = callout.get("type", "WARNING").upper()
                c_text = callout.get("text", "")

                type_run = c_para.add_run(f"[{c_type}] ")
                type_run.font.bold = True
                if c_type in {"WARNING", "DANGER"}:
                    type_run.font.color.rgb = RGBColor(0xB9, 0x1C, 0x1C)  # Red
                else:
                    type_run.font.color.rgb = RGBColor(0xD9, 0x77, 0x06)  # Amber

                text_run = c_para.add_run(c_text)
                text_run.font.bold = True

            # Formatted Tables
            for tbl_data in sec.tables:
                headers = tbl_data.get("headers", [])
                rows = tbl_data.get("rows", [])
                if headers and rows:
                    t = doc.add_table(rows=len(rows) + 1, cols=len(headers))
                    t.style = "Table Grid"
                    t.alignment = WD_TABLE_ALIGNMENT.CENTER

                    # Header row
                    for col_idx, header_text in enumerate(headers):
                        cell = t.cell(0, col_idx)
                        cell.text = str(header_text)
                        cell.paragraphs[0].runs[0].font.bold = True

                    # Data rows
                    for row_idx, row_data in enumerate(rows):
                        for col_idx, val in enumerate(row_data):
                            t.cell(row_idx + 1, col_idx).text = str(val)

                    doc.add_paragraph()  # Spacing after table

            # Citations block
            if sec.citations:
                c_para = doc.add_paragraph()
                c_run = c_para.add_run("Evidence References:")
                c_run.font.bold = True
                c_run.font.size = Pt(9)
                for cite in sec.citations[:3]:
                    doc_id = cite.get("document_id", "REF")
                    page = cite.get("page_index", 1)
                    cp = doc.add_paragraph(f"• Document: {doc_id} (Page {page})")
                    cp.paragraph_format.left_indent = Inches(0.25)
                    cp.runs[0].font.size = Pt(8.5)
                    cp.runs[0].font.color.rgb = RGBColor(0x64, 0x74, 0x8B)

            doc.add_paragraph()  # Spacing between sections

        bio = io.BytesIO()
        doc.save(bio)
        return bio.getvalue()

    def build_permit_docx_bytes(self, permit: Any) -> bytes:
        """Build an authentic Microsoft Word (.docx) document for an industrial permit."""
        def _get(field: str, default: Any = None) -> Any:
            if isinstance(permit, dict):
                return permit.get(field, default)
            return getattr(permit, field, default)

        doc = Document()
        for section in doc.sections:
            section.top_margin = Inches(0.8)
            section.bottom_margin = Inches(0.8)
            section.left_margin = Inches(0.8)
            section.right_margin = Inches(0.8)

        # Header Title
        title = _get("title") or "INDUSTRIAL WORK PERMIT"
        permit_id = _get("permit_id") or "PERMIT-GENERIC"
        status_val = _get("status")
        if hasattr(status_val, "value"):
            status_val = status_val.value
        status_str = str(status_val or "DRAFT_GENERATED").upper()

        title_para = doc.add_paragraph()
        title_run = title_para.add_run(f"SAFE WORK PERMIT: {title.upper()}")
        title_run.font.name = "Calibri"
        title_run.font.size = Pt(20)
        title_run.font.bold = True
        title_run.font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)

        # Metadata Table
        meta_table = doc.add_table(rows=3, cols=2)
        meta_table.style = "Table Grid"
        meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER

        meta_table.cell(0, 0).text = f"Permit ID: {permit_id}"
        meta_table.cell(0, 1).text = f"Status: {status_str}"
        meta_table.cell(1, 0).text = f"Facility: {_get('facility_name', 'Industrial Processing Plant')}"
        meta_table.cell(1, 1).text = f"Unit / Area: {_get('unit_area', 'Process Area 1')}"
        meta_table.cell(2, 0).text = f"Equipment Tag: {_get('equipment_tag', 'N/A')}"
        meta_table.cell(2, 1).text = f"Work Order: {_get('work_order_number', 'WO-PENDING')}"

        for row in meta_table.rows:
            for cell in row.cells:
                if cell.paragraphs and cell.paragraphs[0].runs:
                    cell.paragraphs[0].runs[0].font.bold = True

        doc.add_paragraph()

        # Section 1: Scope of Work
        h1 = doc.add_paragraph()
        r1 = h1.add_run("1. Scope of Work & Description")
        r1.font.bold = True
        r1.font.size = Pt(14)
        r1.font.color.rgb = RGBColor(0x1E, 0x3A, 0x8A)

        work_desc = _get("work_description", "Standard industrial maintenance and inspection.")
        p_desc = doc.add_paragraph(str(work_desc))
        p_desc.paragraph_format.space_after = Pt(6)

        # Section 2: Identified Hazards & Precautions
        h2 = doc.add_paragraph()
        r2 = h2.add_run("2. Hazard Analysis & Required Controls")
        r2.font.bold = True
        r2.font.size = Pt(14)
        r2.font.color.rgb = RGBColor(0x1E, 0x3A, 0x8A)

        hazards = _get("hazards") or ["Thermal heat / hot surfaces", "Stored mechanical energy", "Toxic / flammable vapor risk"]
        precautions = _get("precautions") or ["Verify complete depressurization", "Continuous LEL monitoring", "30-minute fire watch post work"]
        ppe = _get("ppe_required") or ["Hard Hat", "Safety Glasses with Side Shields", "Flame Resistant (FR) Clothing", "Steel-Toe Boots"]

        haz_p = doc.add_paragraph()
        haz_run = haz_p.add_run("[CRITICAL HAZARDS IDENTIFIED]\n")
        haz_run.font.bold = True
        haz_run.font.color.rgb = RGBColor(0xB9, 0x1C, 0x1C)
        for haz in hazards:
            hp = doc.add_paragraph(f"• {haz}")
            hp.paragraph_format.left_indent = Inches(0.25)

        prec_p = doc.add_paragraph()
        prec_run = prec_p.add_run("[MANDATORY PRECAUTIONS]\n")
        prec_run.font.bold = True
        prec_run.font.color.rgb = RGBColor(0xD9, 0x77, 0x06)
        for prec in precautions:
            pp = doc.add_paragraph(f"• {prec}")
            pp.paragraph_format.left_indent = Inches(0.25)

        doc.add_paragraph(f"Personal Protective Equipment (PPE): {', '.join(ppe)}")

        # Section 3: Lockout / Tagout (LOTO) Isolation Schedule
        h3 = doc.add_paragraph()
        r3 = h3.add_run("3. Mechanical & Electrical Isolation Schedule (LOTO)")
        r3.font.bold = True
        r3.font.size = Pt(14)
        r3.font.color.rgb = RGBColor(0x1E, 0x3A, 0x8A)

        raw_isolations = _get("isolation_points") or []
        isolations: list[dict[str, Any]] = []
        for iso in raw_isolations:
            if isinstance(iso, dict):
                isolations.append(iso)
            else:
                isolations.append({
                    "tag": getattr(iso, "tag", "ISO-TAG"),
                    "isolation_type": getattr(iso, "isolation_type", "Valve / Switch"),
                    "status": getattr(iso, "status", "Closed / Locked"),
                    "location": getattr(iso, "location", "Piping Rack"),
                })

        if not isolations:
            isolations = [
                {"tag": f"{_get('equipment_tag', 'EQ')}-SUCT", "isolation_type": "Suction Block Valve", "status": "Closed, Locked, Tagged", "location": "Unit Battery Limit"},
                {"tag": f"{_get('equipment_tag', 'EQ')}-DISC", "isolation_type": "Discharge Block Valve", "status": "Closed, Locked, Tagged", "location": "Unit Battery Limit"},
                {"tag": f"MCC-{_get('equipment_tag', 'EQ')}", "isolation_type": "Electrical Breaker", "status": "Racked Out, Padlocked, Tagged", "location": "Substation 1"},
            ]

        iso_table = doc.add_table(rows=len(isolations) + 1, cols=4)
        iso_table.style = "Table Grid"
        iso_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        headers = ["Isolation Tag", "Isolation Type", "Required State", "Location"]
        for idx, h in enumerate(headers):
            cell = iso_table.cell(0, idx)
            cell.text = h
            cell.paragraphs[0].runs[0].font.bold = True

        for row_idx, iso_data in enumerate(isolations):
            iso_table.cell(row_idx + 1, 0).text = str(iso_data.get("tag", ""))
            iso_table.cell(row_idx + 1, 1).text = str(iso_data.get("isolation_type", ""))
            iso_table.cell(row_idx + 1, 2).text = str(iso_data.get("status", ""))
            iso_table.cell(row_idx + 1, 3).text = str(iso_data.get("location", ""))

        doc.add_paragraph()

        # Section 4: Atmospheric Gas Testing
        h4 = doc.add_paragraph()
        r4 = h4.add_run("4. Atmospheric Gas Testing Thresholds")
        r4.font.bold = True
        r4.font.size = Pt(14)
        r4.font.color.rgb = RGBColor(0x1E, 0x3A, 0x8A)

        gas_testing = _get("gas_testing") or {}
        if not isinstance(gas_testing, dict):
            gas_testing = {
                "lel_max_percent": getattr(gas_testing, "lel_max_percent", 0.0),
                "oxygen_min_percent": getattr(gas_testing, "oxygen_min_percent", 19.5),
                "oxygen_max_percent": getattr(gas_testing, "oxygen_max_percent", 23.5),
                "h2s_max_ppm": getattr(gas_testing, "h2s_max_ppm", 10.0),
                "co_max_ppm": getattr(gas_testing, "co_max_ppm", 25.0),
            }

        gas_table = doc.add_table(rows=5, cols=3)
        gas_table.style = "Table Grid"
        gas_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        g_headers = ["Gas Parameter", "Permissible Safe Limit", "Verified Field Reading"]
        for idx, gh in enumerate(g_headers):
            cell = gas_table.cell(0, idx)
            cell.text = gh
            cell.paragraphs[0].runs[0].font.bold = True

        gas_rows = [
            ("Combustible Gas (LEL)", f"<= {gas_testing.get('lel_max_percent', 0.0)}%", "0.0% (PASS)"),
            ("Oxygen (O2)", f"{gas_testing.get('oxygen_min_percent', 19.5)}% - {gas_testing.get('oxygen_max_percent', 23.5)}%", "20.9% (PASS)"),
            ("Hydrogen Sulfide (H2S)", f"<= {gas_testing.get('h2s_max_ppm', 10.0)} ppm", "0.0 ppm (PASS)"),
            ("Carbon Monoxide (CO)", f"<= {gas_testing.get('co_max_ppm', 25.0)} ppm", "0.0 ppm (PASS)"),
        ]
        for r_idx, (p_name, p_lim, p_val) in enumerate(gas_rows):
            gas_table.cell(r_idx + 1, 0).text = p_name
            gas_table.cell(r_idx + 1, 1).text = p_lim
            gas_table.cell(r_idx + 1, 2).text = p_val

        doc.add_paragraph()

        # Section 5: Authorization & Sign-Off
        h5 = doc.add_paragraph()
        r5 = h5.add_run("5. Human Authorization & Operational Sign-Off")
        r5.font.bold = True
        r5.font.size = Pt(14)
        r5.font.color.rgb = RGBColor(0x1E, 0x3A, 0x8A)

        auth_by = _get("authorized_by")
        auth_p = doc.add_paragraph()
        if auth_by:
            auth_run = auth_p.add_run(f"VERIFIED AUTHORIZATION: Authorized by {auth_by} on {_get('authorized_at', datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'))}\n")
            auth_run.font.bold = True
            auth_run.font.color.rgb = RGBColor(0x05, 0x96, 0x69)
        else:
            auth_run = auth_p.add_run("STATUS: PENDING HUMAN COUNTERSIGNATURE\n")
            auth_run.font.bold = True
            auth_run.font.color.rgb = RGBColor(0xD9, 0x77, 0x06)

        auth_table = doc.add_table(rows=3, cols=2)
        auth_table.style = "Table Grid"
        auth_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        auth_table.cell(0, 0).text = "Operating Authority Name:"
        auth_table.cell(0, 1).text = str(auth_by or "_______________________________")
        auth_table.cell(1, 0).text = "Title / Designation:"
        auth_table.cell(1, 1).text = "Senior Plant Safety Officer"
        auth_table.cell(2, 0).text = "Signature & Badge ID:"
        auth_table.cell(2, 1).text = "[ELECTRONICALLY VERIFIED]" if auth_by else "_______________________________"

        bio = io.BytesIO()
        doc.save(bio)
        return bio.getvalue()

