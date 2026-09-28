import re
from pathlib import Path
from typing import Dict, Any
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepInFrame
)

def sanitize_for_pdf(val: Any) -> str:
    if not val:
        return ""
    text = str(val)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\xff]', '', text)
    return text.strip()

def format_clickable_link(label: str, url: str) -> str:
    clean_url = sanitize_for_pdf(url)
    clean_label = sanitize_for_pdf(label)
    if not clean_url:
        return clean_label
    if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
        clean_url = f"https://{clean_url}"
    return f'<a href="{clean_url}" color="#0284c7"><u>{clean_label}</u></a>'

def build_pdf_resume(profile: Dict[str, Any], output_path: str):
    # Standard Letter: 612 x 792 pt. Top/Bottom 28pt, Left/Right 28pt.
    # Printable Area: Width = 556pt, Height = 736pt
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=28,
        rightMargin=28,
        topMargin=28,
        bottomMargin=28
    )

    name_style = ParagraphStyle(
        'ResumeName',
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=2
    )

    contact_style = ParagraphStyle(
        'ResumeContact',
        fontName='Helvetica',
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor("#334155"),
        spaceAfter=5
    )

    section_heading = ParagraphStyle(
        'ResumeHeading',
        fontName='Helvetica-Bold',
        fontSize=9.8,
        leading=12.5,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=6,
        spaceAfter=2,
        textTransform='uppercase'
    )

    body_style = ParagraphStyle(
        'ResumeBody',
        fontName='Helvetica',
        fontSize=8.8,
        leading=12.2,
        textColor=colors.HexColor("#1e293b")
    )

    item_title_style = ParagraphStyle(
        'ResumeItemTitle',
        fontName='Helvetica-Bold',
        fontSize=9.2,
        leading=12.5,
        textColor=colors.HexColor("#0f172a")
    )

    item_sub_style = ParagraphStyle(
        'ResumeItemSub',
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#475569")
    )

    bullet_style = ParagraphStyle(
        'ResumeBullet',
        fontName='Helvetica',
        fontSize=8.6,
        leading=12.0,
        textColor=colors.HexColor("#1e293b"),
        leftIndent=14,
        bulletIndent=2,
        spaceAfter=1.8
    )

    elements = []

    # 1. Header (Name & Links)
    contact = profile.get("contact", {})
    name = sanitize_for_pdf(contact.get("full_name", "Software Engineer"))
    elements.append(Paragraph(name, name_style))

    contact_parts = []
    if contact.get("email"):
        contact_parts.append(sanitize_for_pdf(contact['email']))
    if contact.get("phone"):
        contact_parts.append(sanitize_for_pdf(contact['phone']))
    if contact.get("location"):
        contact_parts.append(sanitize_for_pdf(contact['location']))
    if contact.get("linkedin_url"):
        contact_parts.append(format_clickable_link("LinkedIn", contact['linkedin_url']))
    if contact.get("github_url"):
        contact_parts.append(format_clickable_link("GitHub", contact['github_url']))
    if contact.get("portfolio_url"):
        contact_parts.append(format_clickable_link("Portfolio", contact['portfolio_url']))

    contact_line = " &nbsp;|&nbsp; ".join(contact_parts)
    elements.append(Paragraph(contact_line, contact_style))
    elements.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#94a3b8"), spaceAfter=4))

    def add_section_header(title: str):
        elements.append(Paragraph(title, section_heading))
        elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1"), spaceAfter=3.5))

    # 2. Summary
    summary = sanitize_for_pdf(profile.get("summary", ""))
    if summary:
        add_section_header("Professional Summary")
        elements.append(Paragraph(summary, body_style))
        elements.append(Spacer(1, 2.5))

    # 3. Technical Skills
    skills = profile.get("skills", {})
    if skills:
        add_section_header("Technical Skills")
        if isinstance(skills, dict):
            for category, skill_list in skills.items():
                if skill_list:
                    cat_txt = f"<b>{sanitize_for_pdf(category)}:</b> " + ", ".join([sanitize_for_pdf(s) for s in skill_list])
                    elements.append(Paragraph(cat_txt, body_style))
        elif isinstance(skills, list):
            elements.append(Paragraph(", ".join([sanitize_for_pdf(s) for s in skills]), body_style))
        elements.append(Spacer(1, 2.5))

    # 4. Work Experience
    experience = profile.get("experience", [])
    if experience:
        add_section_header("Professional Experience")
        for exp in experience:
            company = sanitize_for_pdf(exp.get("company", ""))
            role = sanitize_for_pdf(exp.get("role", ""))
            start = sanitize_for_pdf(exp.get("start_date", ""))
            end = sanitize_for_pdf(exp.get("end_date", "Present"))
            loc = sanitize_for_pdf(exp.get("location", ""))
            dates = f"{start} - {end}" if start else end
            if loc:
                dates = f"{loc} | {dates}"

            title_row = [
                Paragraph(f"<b>{role}</b> &nbsp;-&nbsp; {company}", item_title_style),
                Paragraph(f"<para align='right'>{dates}</para>", item_sub_style)
            ]
            t = Table([title_row], colWidths=[395, 161])
            t.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('LEFTPADDING', (0,0), (-1,-1), 0),
                ('RIGHTPADDING', (0,0), (-1,-1), 0),
                ('BOTTOMPADDING', (0,0), (-1,-1), 0.5),
                ('TOPPADDING', (0,0), (-1,-1), 1)
            ]))
            elements.append(t)

            for h in exp.get("highlights", []):
                elements.append(Paragraph(sanitize_for_pdf(h), bullet_style, bulletText='\u2022'))
            elements.append(Spacer(1, 1.5))

    # 5. Technical Projects
    projects = profile.get("projects", [])
    if projects:
        add_section_header("Key Technical Projects")
        for prj in projects:
            p_name = sanitize_for_pdf(prj.get("name", ""))
            p_role = sanitize_for_pdf(prj.get("role", ""))
            p_url = prj.get("url")

            title_html = f"<b>{p_name}</b>"
            if p_role:
                title_html += f" &nbsp;|&nbsp; <i>{p_role}</i>"
            if p_url:
                title_html += f" &nbsp;({format_clickable_link('Live Demo ->', p_url)})"

            p_row = [
                Paragraph(title_html, item_title_style),
                Paragraph("", item_sub_style)
            ]
            t = Table([p_row], colWidths=[430, 126])
            t.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('LEFTPADDING', (0,0), (-1,-1), 0),
                ('RIGHTPADDING', (0,0), (-1,-1), 0),
                ('BOTTOMPADDING', (0,0), (-1,-1), 0.5),
                ('TOPPADDING', (0,0), (-1,-1), 1)
            ]))
            elements.append(t)

            for h in prj.get("highlights", []):
                elements.append(Paragraph(sanitize_for_pdf(h), bullet_style, bulletText='\u2022'))
            elements.append(Spacer(1, 1.5))

    # 6. Education
    education = profile.get("education", [])
    if education:
        add_section_header("Education")
        for edu in education:
            inst = sanitize_for_pdf(edu.get("institution", ""))
            deg = sanitize_for_pdf(edu.get("degree", ""))
            yr = sanitize_for_pdf(edu.get("graduation_year", ""))

            edu_row = [
                Paragraph(f"<b>{deg}</b> &nbsp;-&nbsp; {inst}", item_title_style),
                Paragraph(f"<para align='right'>{yr}</para>", item_sub_style)
            ]
            t = Table([edu_row], colWidths=[430, 126])
            t.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('LEFTPADDING', (0,0), (-1,-1), 0),
                ('RIGHTPADDING', (0,0), (-1,-1), 0),
                ('BOTTOMPADDING', (0,0), (-1,-1), 0.5),
                ('TOPPADDING', (0,0), (-1,-1), 1)
            ]))
            elements.append(t)

    # STRICT 1-PAGE AUTO-FIT ENFORCER:
    # 556pt width x 736pt height is the exact printable box.
    # mode='shrink' forces content to adjust perfectly to 1 page if it ever attempts to spill.
    locked_frame = KeepInFrame(
        maxWidth=556,
        maxHeight=736,
        content=elements,
        mode='shrink'
    )

    doc.build([locked_frame])
