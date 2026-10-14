from pathlib import Path
from xml.sax.saxutils import escape
import re,json
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Image,HRFlowable
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from pypdf import PdfReader

root=Path(__file__).resolve().parents[1]
out=root/'reports/mobility_planning_memo.pdf'
doc=SimpleDocTemplate(str(out),pagesize=A4,leftMargin=42,rightMargin=42,topMargin=32,bottomMargin=34,title='January Review and Feb 17-23 Demand Plan',author='Urban Mobility Demand Planning')
body=ParagraphStyle('body',fontName='Helvetica',fontSize=9.5,leading=12.2,spaceAfter=6,textColor=HexColor('#263238'))
heading=ParagraphStyle('heading',parent=body,fontName='Helvetica-Bold',fontSize=11,leading=14,spaceBefore=7,spaceAfter=4,textColor=HexColor('#18394b'))
title=ParagraphStyle('title',parent=body,fontName='Helvetica-Bold',fontSize=18,leading=22,spaceAfter=6,textColor=HexColor('#18394b'))
note=ParagraphStyle('note',parent=body,fontSize=8,leading=10,textColor=HexColor('#536571'))
def markup(text):return re.sub(r'\*\*(.+?)\*\*',r'<b>\1</b>',escape(text))
parts=(root/'docs/mobility_planning_memo.md').read_text().strip().split('\n\n')
story=[Paragraph('January review and holiday-week plan',title),Paragraph('NYC Uber + Lyft | Information cutoff: 16 February 2025 | Historical planning simulation',note),Spacer(1,6),HRFlowable(width='100%',thickness=1,color=HexColor('#d6e1e6')),Spacer(1,8)]
for block in parts[2:]:
    if block.startswith('## '):
        if block.startswith('## What remains'):
            story += [Image(str(root/'reports/memo_planned_trips.png'),width=500,height=118),Spacer(1,3)]
        story.append(Paragraph(escape(block[3:]),heading))
    else:story.append(Paragraph(markup(block),body))
story += [Spacer(1,3),Paragraph('Sources: NYC TLC completed trips; portfolio notebook sections on the January fee comparison and cutoff holiday-week forecast. Every numeric claim is traceable in the accompanying source table.',note)]
def footer(canvas,doc):
    canvas.setFont('Helvetica',7.5);canvas.setFillColor(HexColor('#536571'))
    canvas.drawString(42,18,'Urban Mobility Demand Planning | Planning evidence only; retrospective results are reported separately')
    canvas.drawRightString(A4[0]-42,18,str(doc.page))
doc.build(story,onFirstPage=footer,onLaterPages=footer)
reader=PdfReader(out)
assert len(reader.pages)==1,f'Expected one page; got {len(reader.pages)}'
text=reader.pages[0].extract_text()
assert 'WAPE' not in text and '$25.88' not in text and '1.608' not in text
assert '4,871,468' in text and '27.00%' in text
(root/'docs/memo_pdf_verification.json').write_text(json.dumps({'pages':len(reader.pages),'cutoff':'2025-02-16','one_chart':True,'no_test_accuracy_or_post_cutoff_credit_results':True,'planned_trips_and_January_share_present':True,'visual_review_completed':False},indent=2)+'\n')
print(out,'one page, no post-cutoff results')
