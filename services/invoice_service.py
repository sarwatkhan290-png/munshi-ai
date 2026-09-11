from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


def generate_invoice_pdf(customer_name, items, shop_name="Munshi AI Shop", shop_phone="+92 300 0000000", shop_email="hello@munshi.ai", shop_address="Business District, Lahore"):
    """Create a clean, branded invoice PDF for a customer and return bytes."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()
    style_title = styles['Title']
    style_normal = styles['BodyText']
    style_small = styles['Small']
    style_header = styles['Heading2']

    total_amount = sum(float(item.get('amount', 0)) for item in items)
    paid_amount = sum(float(item.get('paid', 0)) for item in items)
    due_amount = max(total_amount - paid_amount, 0)

    story = []
    story.append(Paragraph(shop_name, style_title))
    story.append(Paragraph("Professional Business Invoice", style_header))
    story.append(Paragraph(f"Phone: {shop_phone} | Email: {shop_email}", style_small))
    story.append(Paragraph(f"Address: {shop_address}", style_small))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"Invoice to: {customer_name}", style_normal))
    story.append(Spacer(1, 12))

    table_data = [["Description", "Amount", "Paid", "Due"]]
    for item in items:
        table_data.append([
            item.get('description', 'Transaction'),
            f"Rs. {float(item.get('amount', 0)):,.0f}",
            f"Rs. {float(item.get('paid', 0)):,.0f}",
            f"Rs. {float(item.get('due', 0)):,.0f}",
        ])

    table = Table(table_data, colWidths=[210, 90, 90, 90])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(table)
    story.append(Spacer(1, 18))
    story.append(Paragraph(f"Total: Rs. {total_amount:,.0f}", style_normal))
    story.append(Paragraph(f"Paid: Rs. {paid_amount:,.0f}", style_normal))
    story.append(Paragraph(f"Balance Due: Rs. {due_amount:,.0f}", style_normal))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Thank you for your business. We value your trust.", style_small))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
