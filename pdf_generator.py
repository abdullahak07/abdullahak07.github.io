from __future__ import annotations
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from models import Quote

def build_pdf(q: Quote) -> bytes:
    buf=BytesIO(); doc=SimpleDocTemplate(buf, pagesize=A4, rightMargin=36,leftMargin=36,topMargin=36,bottomMargin=36); s=getSampleStyleSheet(); story=[]
    story += [Paragraph(q.business_name, s['Title']), Paragraph(f"ABN: {q.abn}", s['Normal']), Paragraph(f"Quote {q.quote_number or 'DRAFT'} • Valid for 30 days", s['Heading2']), Spacer(1,12)]
    c=q.customer
    if c: story.append(Paragraph(f"Customer: {getattr(c,'name',None) or c.get('name','')}<br/>{getattr(c,'address',None) or c.get('address','')}", s['Normal']))
    rows=[["Description","Qty","Materials","Hours","Rate","Line Total"]]
    for i in q.line_items:
        total=i.quantity*i.material_unit_cost*(1+i.material_markup_percent/100)+i.labor_hours*i.hourly_rate
        rows.append([i.description, f"{i.quantity:g}", f"${i.material_unit_cost:.2f}", f"{i.labor_hours:.1f}", f"${i.hourly_rate:.2f}", f"${total:.2f}"])
    rows += [["","","","","Subtotal",f"${q.subtotal:.2f}"],["","","","","GST 10%",f"${q.gst:.2f}"],["","","","","Total",f"${q.total:.2f}"]]
    table=Table(rows, colWidths=[190,35,70,55,60,70]); table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#111827')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),.4,colors.grey),('FONTNAME',(0,-1),(-1,-1),'Helvetica-Bold')]))
    story += [Spacer(1,12), table, Spacer(1,18), Paragraph("Terms", s['Heading3']), Paragraph(q.terms, s['Normal']), Spacer(1,16), Paragraph("[ Accept Quote ]", s['Heading2'])]
    doc.build(story); return buf.getvalue()
