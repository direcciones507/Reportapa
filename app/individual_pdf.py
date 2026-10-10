"""Private single-page case sheet, separate from the aggregated summary."""
import io, re
from xml.sax.saxutils import escape
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Paragraph, KeepInFrame


def individual_pdf(report, directory, states):
    out=io.BytesIO(); pdf=canvas.Canvas(out,pagesize=A4)
    width,height=A4; margin=32; area=width-2*margin
    pdf.setTitle('ReportaPA - ficha individual confidencial')
    pdf.setFillColor(HexColor('#123f58'));pdf.rect(0,height-83,width,83,fill=1,stroke=0)
    pdf.setFillColor(HexColor('#ffffff'));pdf.setFont('Helvetica-Bold',20)
    pdf.drawString(margin,height-36,'ReportaPA | Ficha individual')
    pdf.setFont('Helvetica',10);pdf.drawString(margin,height-59,report['id']+' - CONFIDENCIAL')
    style=ParagraphStyle('case',fontName='Helvetica',fontSize=9,leading=11,spaceAfter=5,splitLongWords=True)
    content=[]
    def line(title,value):
        content.append(Paragraph('<b>'+escape(title)+':</b> '+escape(str(value)).replace('\n','<br/>'),style))
    d=report['data'];updated=report.get('ayuda_actualizada_at')
    line('Fecha del reporte',report['created_at'].strftime('%d/%m/%Y %H:%M UTC'))
    line('Persona / familia',d['name']);line('Teléfono',d['phone'])
    line('Ubicación',' / '.join(d[k] for k in ('province','district','township','community')))
    line('Google Maps',d['maps']);line('Estado operativo',report['status'])
    line('Estado de ayuda',states[report.get('estado_ayuda','pendiente_confirmar')])
    line('Último seguimiento',updated.strftime('%d/%m/%Y %H:%M UTC') if updated else 'Sin confirmar')
    line('Daños',(d.get('damage_type','')+' - '+d['damage']).strip(' -'))
    line('Necesidades',', '.join(d['needs']) or 'No indicadas')
    if d.get('needs_detail'): line('Detalle de necesidades',d['needs_detail'])
    if report.get('ayuda_observacion'): line('Observación de seguimiento',report['ayuda_observacion'])
    # Fixed text area, fitted as a unit. Never paginate or discard long descriptions.
    text_bottom=245; text_top=height-100
    frame=KeepInFrame(area,text_top-text_bottom,content,mode='shrink',hAlign='LEFT',vAlign='TOP')
    _,h=frame.wrapOn(pdf,area,text_top-text_bottom);frame.drawOn(pdf,margin,text_top-h)
    pdf.setFillColor(HexColor('#123f58'));pdf.setFont('Helvetica-Bold',10)
    pdf.drawString(margin,225,'Fotografías privadas (hasta 3)')
    cell=(area-16)/3; y=75
    photos=report.get('photos',[])[:3]
    if not photos:
        pdf.setFont('Helvetica',9);pdf.drawString(margin,197,'Sin fotografías adjuntas.')
    for i,name in enumerate(photos):
        x=margin+i*(cell+8)
        pdf.setStrokeColor(HexColor('#cad7df'));pdf.rect(x,y,cell,138,stroke=1,fill=0)
        try:
            if not re.fullmatch(r'[a-f0-9]{32}\.jpg',name): raise ValueError('invalid photo key')
            image=ImageReader(str(directory/name));iw,ih=image.getSize()
            scale=min((cell-8)/iw,130/ih);w,h=iw*scale,ih*scale
            pdf.drawImage(image,x+(cell-w)/2,y+(138-h)/2,width=w,height=h)
        except (OSError,ValueError):
            pdf.setFont('Helvetica',8);pdf.drawString(x+6,y+65,'Foto no disponible')
    pdf.setFillColor(HexColor('#526b79'));pdf.setFont('Helvetica',8)
    pdf.drawString(margin,49,'Información privada: compartir únicamente con personal autorizado.')
    pdf.drawString(margin,36,'Registro ciudadano independiente. No garantiza inspección ni entrega de ayuda.')
    pdf.save();return out.getvalue()
