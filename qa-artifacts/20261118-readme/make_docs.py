"""Render a few realistic synthetic documents (no real personal data) as PNG scans."""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

out = Path(sys.argv[1])
font = "/System/Library/Fonts/Supplemental/Arial.ttf"
bold = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
DOCS = {
    "bolletta-luce-ottobre": ("Luce Chiara Energia S.p.A.", "Bolletta energia elettrica", ["Periodo: 1-31 ottobre 2026", "Data emissione: 14/11/2026", "Cliente: Famiglia Rossi, Via dei Tigli 8, Milano", "Consumo: 212 kWh", "Totale da pagare: 64,30 EUR", "Scadenza: 05/12/2026"]),
    "avviso-tari-2026": ("Comune di Valverde", "Avviso di pagamento TARI 2026", ["Tassa sui rifiuti - anno 2026", "Data: 02/10/2026", "Intestatario: Famiglia Rossi", "Superficie: 85 mq, 3 occupanti", "Importo annuo: 312,00 EUR in due rate", "Prima rata entro il 16/12/2026"]),
    "contratto-locazione": ("Studio Notarile Bianchi", "Contratto di locazione ad uso abitativo", ["Stipulato il 01/03/2026", "Immobile: Via dei Tigli 8, interno 4", "Durata: 4 anni + 4", "Canone mensile: 850,00 EUR", "Deposito cauzionale: 2.550,00 EUR", "Registrazione Agenzia delle Entrate n. 4821"]),
    "polizza-auto": ("Assicurazioni Serene", "Polizza RC Auto - certificato", ["Polizza n. RC-2026-118430", "Decorrenza: 15/04/2026 - Scadenza: 15/04/2027", "Veicolo: utilitaria targa AB123CD", "Premio annuo: 412,50 EUR", "Classe di merito: 1", "Assistenza stradale inclusa"]),
    "payslip-october": ("Northwind Analytics Ltd", "Payslip - October 2026", ["Pay date: 27/10/2026", "Employee: M. Rossi, Data analyst", "Gross pay: 3,450.00 EUR", "Tax and contributions: 1,012.40 EUR", "Net pay: 2,437.60 EUR", "Holiday balance: 14 days"]),
    "ricevuta-farmacia": ("Farmacia San Marco", "Ricevuta fiscale", ["Data: 09/11/2026 ore 18:42", "Farmaci da banco e parafarmaco", "Totale: 23,80 EUR", "Detraibile ai fini fiscali", "Codice fiscale del cliente registrato", "Grazie e arrivederci"]),
}
for name, (sender, title, lines) in DOCS.items():
    image = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(image)
    draw.text((110, 110), sender, fill="#1b4d3e", font=ImageFont.truetype(bold, 46))
    draw.line((110, 185, 1130, 185), fill="#1b4d3e", width=4)
    draw.text((110, 240), title, fill="black", font=ImageFont.truetype(bold, 52))
    for index, line in enumerate(lines):
        draw.text((110, 380 + index * 90), line, fill="black", font=ImageFont.truetype(font, 40))
    draw.text((110, 1600), "Documento di esempio generato per la demo di Ripiano", fill="#777", font=ImageFont.truetype(font, 28))
    image.save(out / f"{name}.png")
print("made", len(DOCS))
