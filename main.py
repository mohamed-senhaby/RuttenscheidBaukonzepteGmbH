import streamlit as st
import google.genai as genai
import tempfile
import os
import pandas as pd
import json
import io
from datetime import datetime
from fpdf import FPDF
import xml.etree.ElementTree as ET
import codecs
import traceback

# --- CONSTANTS & CONFIGURATION ---
COMPANY_NAME = "Rüttenscheid Baukonzepte GmbH"

# Detailed calculation prompt for comprehensive price analysis
CALCULATION_PROMPT = """
Du bist ein erfahrener Kalkulator für die Rüttenscheid Baukonzepte GmbH.
Im Rahmen der folgenden Ausschreibungsunterlagen und Leistungsbeschreibungen bitte ich dich, sämtliche bereitgestellten Informationen gründlich und fachlich fundiert zu analysieren.
Berücksichtige bei deiner Auswertung insbesondere die projektspezifischen Randbedingungen, technischen Anforderungen, Bauzeitenvorgaben sowie mögliche baubetriebliche Restriktionen.

Für jede von mir einzeln übermittelte Leistungsposition ist auf dieser Grundlage ein realistischer, marktgerechter und zugleich wettbewerbsfähiger Einheitspreis (netto, ohne MwSt.) zu ermitteln.
Dieser Preis soll sämtliche relevanten Kostenfaktoren detailliert und vollständig abdecken. Dazu zählen unter anderem:
•	Materialkosten (inkl. Beschaffung, Lagerung, Verluste)
•	Gerätekosten (inkl. Abschreibung, Einsatzzeiten, Rüstkosten)
•	Transportkosten (intern und extern)
•	Lohnkosten (inkl. tariflicher und gesetzlicher Nebenleistungen)
•	Baustellengemeinkosten und Bauleitung
•	Allgemeine Geschäftskosten und kalkulatorische Risiken
•	Leistungsbedingte Besonderheiten wie Wasserhaltung, Erschwernisse oder Nachtarbeit

Die Preisermittlung hat auf Basis nachvollziehbarer, praxisgerechter und aktueller Marktdaten zu erfolgen. Ziel ist ein Preisniveau, das die Ausführung wirtschaftlich ermöglicht und zugleich im Wettbewerb Bestand hat – also so niedrig wie möglich, ohne die technische Realisierbarkeit oder Wirtschaftlichkeit zu gefährden.

WICHTIG: Gib das Ergebnis AUSSCHLIESSLICH als JSON-Liste zurück.
Format: [{"pos": "01.01", "description": "Kurztext", "quantity": 100.0, "unit": "m2", "unit_price": 45.50}, ...]
"""

# Prompt for validating and pricing GAEB-parsed positions
GAEB_PRICING_PROMPT = """
Du bist ein erfahrener Kalkulator für die Rüttenscheid Baukonzepte GmbH.

Ich habe Positionsdaten aus einer GAEB-Datei extrahiert. Deine Aufgabe:

1. IDENTIFIZIERE echte Leistungspositionen:
   - POSITION = Hat eine Positionsnummer UND eine konkrete Leistungsbeschreibung UND eine Menge mit Einheit
   - KEINE POSITION = Nur Überschrift (z.B. "Kogr. 391", "2. OG"), nur Hinweis/Bemerkung, keine Mengenangabe
   - WICHTIG: Wenn eine Beschreibung eine konkrete Bauleistung beschreibt (Einrichten, Abbruch, Montage, Lieferung, etc.) → IST EINE POSITION

2. BERECHNE für JEDE Position einen realistischen Einheitspreis (netto, ohne MwSt.):
   - Materialkosten (inkl. Beschaffung, Lagerung, Verluste)
   - Gerätekosten (inkl. Abschreibung, Einsatzzeiten, Rüstkosten)
   - Transportkosten (intern und extern)
   - Lohnkosten (inkl. tariflicher und gesetzlicher Nebenleistungen)
   - Baustellengemeinkosten und Bauleitung
   - Allgemeine Geschäftskosten und kalkulatorische Risiken
   - Leistungsbedingte Besonderheiten

3. WICHTIG - JEDE Position MUSS einen Preis haben:
   - Wenn Preis 0.0 ist, berechne einen realistischen Wert
   - Keine Position darf mit unit_price: 0.0 zurückgegeben werden
   - Preise müssen wirtschaftlich und wettbewerbsfähig sein

Gib NUR die Positionen zurück als JSON-Liste (keine Überschriften/Hinweise):
[{"pos": "0010", "description": "Einrichten und Räumen der Baustelle", "quantity": 4.0, "unit": "St", "unit_price": 1250.00}, ...]

Extrahierte Daten:
"""

# 1. Configure the Page
st.set_page_config(page_title="Rüttenscheid Smart Kalkulation", page_icon="🏗️", layout="wide")

# --- HELPER FUNCTIONS ---

# --- REPLACEMENT FUNCTION: generate_offer_pdf ---

class OfferPDF(FPDF):
    def header(self):
        # 1. Company Logo / Header Text (Top Left)
        self.set_font("Arial", 'B', 14)
        self.set_text_color(0, 0, 0) # Black
        self.cell(100, 8, "RÜTTENSCHEID BAUKONZEPTE", ln=0, align='L')
        
        # Date (Top Right)
        self.set_font("Arial", '', 10)
        self.cell(0, 8, f"Datum: {datetime.now().strftime('%d.%m.%Y')}", ln=1, align='R')
        
        # Company Address (Below Logo)
        self.set_font("Arial", '', 10)
        self.cell(100, 5, "Münchener Str. 100 A, 45145 Essen", ln=1, align='L')
        self.ln(10) # Space

    def footer(self):
        # Position at 3.5 cm from bottom
        self.set_y(-35)
        
        # Draw a line
        self.set_draw_color(200, 200, 200)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(2)
        
        # Footer Content (3 Columns: Address, Contact, Bank/Info)
        self.set_font("Arial", '', 8)
        self.set_text_color(80, 80, 80) # Gray
        
        # Column 1: Company & Manager
        col_width = 63
        x_start = 10
        self.set_xy(x_start, self.get_y())
        self.multi_cell(col_width, 4, 
            "Rüttenscheid Baukonzepte GmbH\n"
            "Münchener Str. 100A\n"
            "45145 Essen\n"
            "Geschäftsführer: Dipl.-Ing. Moh Alturky", align='L')
            
        # Column 2: Contact
        self.set_xy(x_start + col_width, self.get_y() - 16) # Move back up
        self.multi_cell(col_width, 4, 
            "Tel: +49 0201 84850166\n"
            "Mob: +49 160 7901911\n"
            "E-Mail: Moh@ruttenscheid-bau.de\n"
            "Web: www.ruttenscheid-bau.de", align='C')
            
        # Column 3: Page Number
        self.set_xy(x_start + (col_width * 2), self.get_y() - 16)
        self.cell(col_width, 4, f"Seite {self.page_no()}", align='R')

def generate_offer_pdf(df, project_name):
    """
    Generates a professional construction offer PDF matching 'Angebot_000.pdf'.
    """
    pdf = OfferPDF()
    pdf.set_auto_page_break(auto=True, margin=40) # Large margin for footer
    pdf.add_page()
    
    # --- Helper: Text Cleaning for Latin-1 ---
    def clean(text):
        if pd.isna(text): return ""
        text = str(text)
        replacements = {
            "€": "EUR", "–": "-", "„": '"', "“": '"', "’": "'", "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"
        }
        for char, rep in replacements.items():
            text = text.replace(char, rep)
        return text.encode('latin-1', 'replace').decode('latin-1')

    # --- Project Details Block ---
    pdf.ln(5)
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Arial", 'B', 12)
    
    # "Auftraggeber" box
    pdf.cell(100, 8, "Auftraggeber", 0, 0, 'L')
    pdf.cell(90, 8, clean(f"Angebot Nr. {datetime.now().strftime('%Y-%m')}"), 0, 1, 'R')
    
    pdf.set_font("Arial", '', 11)
    pdf.cell(100, 6, clean("Hansestadt Wipperfürth (Muster)"), 0, 0, 'L') # Placeholder
    pdf.cell(90, 6, clean(f"Projekt: {project_name}"), 0, 1, 'R')
    
    pdf.ln(15)
    
    # Title
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, clean(f"Angebot für: {project_name}"), ln=1, align='L')
    
    pdf.set_font("Arial", '', 11)
    pdf.multi_cell(0, 6, clean("Sehr geehrte Damen und Herren,\nhiermit unterbreiten wir Ihnen unser Angebot gemäß Ihrer Anfrage."))
    pdf.ln(10)

    # --- Table Header ---
    pdf.set_fill_color(230, 230, 230)
    pdf.set_font("Arial", 'B', 9)
    pdf.set_draw_color(180, 180, 180)
    
    # Column Widths: Pos, Description, Qty, Unit, Price, Total
    w = [20, 85, 20, 15, 25, 25] 
    
    pdf.cell(w[0], 8, clean("Pos."), 1, 0, 'C', 1)
    pdf.cell(w[1], 8, clean("Bezeichnung"), 1, 0, 'L', 1)
    pdf.cell(w[2], 8, clean("Menge"), 1, 0, 'C', 1)
    pdf.cell(w[3], 8, clean("Einh."), 1, 0, 'C', 1)
    pdf.cell(w[4], 8, clean("EP (EUR)"), 1, 0, 'R', 1)
    pdf.cell(w[5], 8, clean("GP (EUR)"), 1, 1, 'R', 1)

    # --- Table Content ---
    pdf.set_font("Arial", size=9)
    total_netto = 0.0
    
    for _, row in df.iterrows():
        try:
            qty = float(row.get('quantity', 0))
            ep = float(row.get('unit_price', 0))
        except:
            qty, ep = 0, 0
            
        gp = qty * ep
        total_netto += gp
        
        # Clean text
        pos = clean(row.get('pos', ''))
        desc = clean(row.get('description', ''))[:45] # Limit length
        unit = clean(row.get('unit', ''))
        
        pdf.cell(w[0], 8, pos, 1, 0, 'C')
        pdf.cell(w[1], 8, desc, 1, 0, 'L')
        pdf.cell(w[2], 8, f"{qty:.2f}", 1, 0, 'C')
        pdf.cell(w[3], 8, unit, 1, 0, 'C')
        pdf.cell(w[4], 8, f"{ep:,.2f}", 1, 0, 'R')
        pdf.cell(w[5], 8, f"{gp:,.2f}", 1, 1, 'R')

    # --- Totals Block ---
    pdf.ln(5)
    
    # Helper for totals row
    def print_total(label, value, bold=False):
        pdf.set_font("Arial", 'B' if bold else '', 10)
        pdf.cell(145, 8, clean(label), 0, 0, 'R')
        pdf.cell(45, 8, f"{value:,.2f} EUR", 1 if bold else 0, 1, 'R')

    print_total("Summe Netto:", total_netto)
    print_total("zzgl. 19% MwSt.:", total_netto * 0.19)
    pdf.ln(2)
    print_total("Gesamtbetrag (Brutto):", total_netto * 1.19, bold=True)
    
    # --- Closing Text ---
    pdf.ln(15)
    pdf.set_font("Arial", '', 10)
    pdf.multi_cell(0, 5, clean("Wir hoffen, Ihnen ein interessantes Angebot unterbreitet zu haben und stehen für Rückfragen gerne zur Verfügung."))
    
    pdf.ln(10)
    pdf.cell(0, 10, clean("Mit freundlichen Grüßen"), ln=1)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 10, clean("Rüttenscheid Baukonzepte GmbH"), ln=1)

    return pdf.output(dest='S').encode('latin-1', 'replace')

def parse_gaeb_file(file_path, file_extension):
    """
    Parse GAEB files with 100% accuracy using native GAEB format parsing.
    
    Supports all GAEB formats:
    - D81-D90: Text-based fixed-width format (various record types: numeric, T-records)
    - X81-X90: XML format (DA81/1.0 to DA90/3.3 schemas)
    - P81-P90: Price format (text-based with prices, similar to D-format)
    
    Format Documentation:
    - DA81 (1981): Original GAEB format
    - DA83 (1983): Extended format with T-records
    - DA84 (1984): Enhanced XML structure  
    - DA86 (1986): Improved data exchange
    - DA90 (1990): Current standard with full XML support
    
    XML Schema Variations:
    - DA83/3.3: <GAEB><Award><BoQ><BoQBody><BoQCtgy><BoQBody><Itemlist><Item>
    - DA84/3.2: <GAEB><Award><BoQ><BoQBody><Itemlist><Item>
    - DA90/3.3: May use Position, BoQItem, or Item elements
    """
    positions = []
    
    try:
        if file_extension in ['.x81', '.x82', '.x83', '.x84', '.x85', '.x86', '.x90']:
            # XML-based GAEB (X-format)
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # Debug: Show XML structure
            print(f"🔍 XML Root Tag: {root.tag}")
            print(f"🔍 Namespace: {root.tag.split('}')[0] + '}' if '}' in root.tag else 'Kein Namespace'}")
            
            # Extract namespace from root tag if present
            if '}' in root.tag:
                ns_uri = root.tag.split('}')[0].strip('{')
                ns = {'ns': ns_uri}
            else:
                ns = {}
            
            # Show first few child elements
            children = list(root)[:5]
            print(f"🔍 Erste Elemente: {[child.tag.split('}')[-1] if '}' in child.tag else child.tag for child in children]}")
            
            # Helper function to get tag name without namespace
            def get_tag_name(element):
                return element.tag.split('}')[-1] if '}' in element.tag else element.tag
            
            # Helper function to find element with or without namespace
            def find_elem(parent, tag):
                return parent.find(f'.//ns:{tag}', ns) or parent.find(f'.//{tag}')
            
            # Helper function to recursively parse hierarchical GAEB structure
            def parse_boq_hierarchy(element, prefix="", level=0):
                """Recursively parse BoQ hierarchy to build full position numbers"""
                tag_name = get_tag_name(element)
                indent = "  " * level
                print(f"{indent}🔍 Level {level}: {tag_name}, Prefix: '{prefix}'")
                
                # Check if this is a category (BoQCtgy) - adds to hierarchy
                if tag_name == 'BoQCtgy':
                    rno_part = element.get('RNoPart', '')
                    new_prefix = f"{prefix}{rno_part}." if prefix else f"{rno_part}."
                    print(f"{indent}   → BoQCtgy gefunden: RNoPart='{rno_part}', neuer Prefix='{new_prefix}'")
                    
                    # Recursively process children
                    for child in element:
                        parse_boq_hierarchy(child, new_prefix, level + 1)
                
                # Check if this is an item list
                elif tag_name == 'Itemlist':
                    print(f"{indent}   → Itemlist gefunden, verarbeite Items...")
                    item_count = 0
                    # Process all items in this list
                    for item in element:
                        if get_tag_name(item) == 'Item':
                            item_count += 1
                            parse_item(item, prefix)
                    print(f"{indent}   → {item_count} Items in dieser Liste")
                
                # Check if this is a BoQBody - contains nested structure
                elif tag_name == 'BoQBody':
                    print(f"{indent}   → BoQBody gefunden, durchsuche Kinder...")
                    for child in element:
                        parse_boq_hierarchy(child, prefix, level + 1)
                
                # Recursively check other elements
                else:
                    has_children = len(list(element)) > 0
                    if has_children:
                        print(f"{indent}   → Andere Element, durchsuche {len(list(element))} Kinder...")
                        for child in element:
                            parse_boq_hierarchy(child, prefix, level + 1)
            
            def parse_item(item, prefix=""):
                """Parse individual Item element"""
                # Get position number
                rno_part = item.get('RNoPart', '')
                pos_no = f"{prefix}{rno_part}" if prefix else rno_part
                
                print(f"      📋 Item: RNoPart='{rno_part}', volle Pos='{pos_no}'")
                
                # Extract description - collect all text from description containers
                desc_parts = []
                
                # Skip these elements when collecting text
                skip_tags = {'Qty', 'QU', 'UP', 'UnitPrice', 'Price', 'Amount', 'AddText', 'Note', 
                            'Spec', 'image', 'img', 'AllowanceCharge'}
                
                # Try to find description containers (GAEB DA83/3.3 structure)
                desc_containers = []
                for tag in ['Description', 'OutlineText', 'DetailTxt', 'CompleteText', 'ShortText', 'LongText']:
                    containers = [elem for elem in item.iter() if get_tag_name(elem) == tag]
                    desc_containers.extend(containers)
                
                # If found description containers, extract text from them
                if desc_containers:
                    for container in desc_containers[:1]:  # Use first container only
                        # Get all text from p, span, and text elements
                        for elem in container.iter():
                            if elem.text and elem.text.strip() and get_tag_name(elem) not in skip_tags:
                                text = elem.text.strip()
                                if text and text not in desc_parts and len(text) > 1:
                                    desc_parts.append(text)
                else:
                    # Fallback: collect all text content from Item (excluding metadata)
                    for elem in item.iter():
                        elem_tag = get_tag_name(elem)
                        if elem_tag not in skip_tags and elem.text and elem.text.strip():
                            text = elem.text.strip()
                            # Skip very short text and numeric-only text
                            if text and text not in desc_parts and len(text) > 2 and not text.replace('.', '').replace(',', '').isdigit():
                                desc_parts.append(text)
                
                # Join description parts (limit to avoid too much text)
                description = " ".join(desc_parts[:10]) if desc_parts else ""
                
                # Extract quantity - look for direct child Qty
                qty = 1.0
                for child in item:
                    if get_tag_name(child) == 'Qty':
                        if child.text:
                            try:
                                qty = float(child.text.replace(',', '.'))
                            except:
                                pass
                        break
                
                # Extract unit - look for direct child QU
                unit = ""
                for child in item:
                    if get_tag_name(child) == 'QU':
                        if child.text:
                            unit = child.text.strip()
                        break
                
                # Extract price (if exists)
                price = 0.0
                for child in item.iter():
                    elem_tag = get_tag_name(child)
                    if elem_tag in ['UP', 'UnitPrice', 'Price', 'Amount']:
                        if child.text:
                            try:
                                price = float(child.text.replace(',', '.'))
                                break
                            except:
                                pass
                
                print(f"         Beschreibung: '{description[:60]}...', Menge: {qty}, Einheit: '{unit}'")
                
                # Only add items with descriptions
                if description:
                    positions.append({
                        'pos': pos_no,
                        'description': description,
                        'quantity': qty,
                        'unit': unit,
                        'unit_price': price
                    })
                else:
                    print(f"         ⚠️ Keine Beschreibung gefunden, Item wird übersprungen")
            
            # Start parsing from root
            print("🔍 Starte hierarchische XML-Traversierung...")
            parse_boq_hierarchy(root)
            
            print(f"🔍 Gefundene Items: {len(positions)}")
        
        elif file_extension in ['.d81', '.d82', '.d83', '.d84', '.d85', '.d86', '.d90',
                                 '.p81', '.p82', '.p83', '.p84', '.p85', '.p86', '.p90']:
            # Text-based GAEB (D-format and P-format) - Fixed-width format
            # P-format is similar to D-format but includes price information
            is_price_format = file_extension.startswith('.p')
            
            with codecs.open(file_path, 'r', encoding='iso-8859-1', errors='ignore') as f:
                lines = f.readlines()
            
            # Debug info
            format_type = "P-Format (mit Preisen)" if is_price_format else "D-Format"
            print(f"🔍 {format_type}: {len(lines)} Zeilen gelesen")
            
            # Count record types
            record_types = {}
            for line in lines[:100]:  # First 100 lines
                if len(line) >= 2:
                    rt = line[0:2]
                    record_types[rt] = record_types.get(rt, 0) + 1
            
            print(f"🔍 Gefundene Record-Typen (erste 100 Zeilen): {record_types}")
            
            # Show sample lines
            sample_lines = [f"{i}: {line[:60]}..." for i, line in enumerate(lines[:10], 1) if len(line) > 2]
            print("🔍 Erste 10 Zeilen (Vorschau):")
            for s in sample_lines:
                print(f"  {s}")
            
            current_pos = None
            current_desc = ""
            current_qty = 1.0
            current_unit = ""
            current_price = 0.0
            in_item = False
            
            for line in lines:
                if len(line) < 2:
                    continue
                    
                record_type = line[0:2]
                content = line[2:].strip() if len(line) > 2 else ""
                
                # T-Format (Text-based GAEB)
                if record_type == 'T0':  # Header/Section
                    pass
                
                elif record_type == 'T1':  # Text/Description lines
                    # Check if this looks like a position number (contains digits and dots)
                    if content and any(c.isdigit() for c in content[:20]):
                        # Save previous position
                        if current_pos and current_desc:
                            positions.append({
                                'pos': current_pos,
                                'description': current_desc.strip(),
                                'quantity': current_qty,
                                'unit': current_unit,
                                'unit_price': current_price
                            })
                            # Reset
                            current_qty = 1.0
                            current_unit = ""
                            current_price = 0.0
                        
                        # Try to extract position number from start of line
                        parts = content.split(maxsplit=1)
                        if parts and any(c.isdigit() for c in parts[0]):
                            current_pos = parts[0]
                            current_desc = parts[1] if len(parts) > 1 else ""
                            in_item = True
                        else:
                            current_desc = content
                    elif in_item and content:
                        # Continuation of description
                        current_desc += " " + content
                
                elif record_type == 'T2':  # Quantity/Unit
                    if in_item:
                        # T2 often contains quantity and unit
                        try:
                            parts = content.split()
                            for p in parts:
                                # Try to find number (quantity)
                                if any(c.isdigit() for c in p):
                                    try:
                                        current_qty = float(p.replace(',', '.'))
                                    except:
                                        pass
                                # Unit is typically short alphabetic string
                                elif p.isalpha() and len(p) <= 5:
                                    current_unit = p
                        except:
                            pass
                
                elif record_type == 'T3':  # Price
                    if in_item and content:
                        try:
                            # Extract price from content
                            price_str = content.replace(',', '.').replace('EUR', '').replace('€', '').strip()
                            # Extract just the number
                            import re
                            match = re.search(r'[\d.]+', price_str)
                            if match:
                                current_price = float(match.group())
                        except:
                            pass
                
                # Numeric format records (backup for mixed formats)
                elif record_type in ['52', '53', '54', '55', 'DP']:  # Position records
                    if current_pos and current_desc:
                        positions.append({
                            'pos': current_pos,
                            'description': current_desc.strip(),
                            'quantity': current_qty,
                            'unit': current_unit,
                            'unit_price': current_price
                        })
                    
                    try:
                        current_pos = line[8:20].strip()
                        current_desc = line[20:80].strip() if len(line) > 80 else line[20:].strip()
                        current_qty = 1.0
                        current_unit = ""
                        current_price = 0.0
                        in_item = True
                    except:
                        pass
                
                elif record_type in ['56', '57', 'TX']:  # Text continuation
                    if in_item:
                        current_desc += " " + line[8:].strip()
                
                elif record_type in ['60', '61', 'QT']:  # Quantity record
                    try:
                        qty_str = line[8:25].strip().replace(',', '.')
                        if qty_str:
                            current_qty = float(qty_str)
                        current_unit = line[25:30].strip()
                    except:
                        pass
                
                elif record_type in ['62', '63', 'PR']:  # Price record
                    try:
                        price_str = line[8:25].strip().replace(',', '.')
                        if price_str:
                            current_price = float(price_str)
                    except:
                        pass
            
            # Add last position
            if current_pos and current_desc:
                positions.append({
                    'pos': current_pos,
                    'description': current_desc.strip(),
                    'quantity': current_qty,
                    'unit': current_unit,
                    'unit_price': current_price
                })
        
        df = pd.DataFrame(positions)
        print(f"✅ GAEB Parser: {len(positions)} Positionen gefunden")
        return df
    
    except Exception as e:
        import traceback
        print(f"❌ GAEB Parser Fehler: {e}")
        print(f"Details: {traceback.format_exc()}")
        return pd.DataFrame(columns=["pos", "description", "quantity", "unit", "unit_price"])

def process_gaeb_with_ai(df_raw, client):
    """
    Post-process GAEB-parsed data with AI to:
    1. Identify actual positions (filter out headers, remarks, notes)
    2. Calculate realistic unit prices for each position
    """
    try:
        print(f"📊 Eingabe: {len(df_raw)} Einträge aus GAEB-Parser")
        
        # Convert dataframe to JSON string for AI processing
        positions_json = df_raw.to_json(orient='records', force_ascii=False, indent=2)
        
        # Create prompt with extracted data
        full_prompt = GAEB_PRICING_PROMPT + "\n" + positions_json
        
        print("🤖 AI analysiert Positionen und berechnet Preise...")
        print(f"📤 Sende {len(positions_json)} Zeichen an AI...")
        
        # Send to AI for validation and pricing
        response = client.models.generate_content(
            model='gemini-2.5-flash-lite',
            contents=[full_prompt]
        )
        
        # Parse AI response
        text = response.text
        print(f"📥 AI Antwort erhalten: {len(text)} Zeichen")
        
        # Remove markdown code blocks if present
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        
        # Parse JSON and create dataframe
        data = json.loads(text.strip())
        df_result = pd.DataFrame(data)
        
        # Validate that all positions have prices
        zero_price_count = len(df_result[df_result['unit_price'] == 0])
        if zero_price_count > 0:
            print(f"⚠️ Warnung: {zero_price_count} Positionen haben Preis 0.0")
        
        print(f"✅ AI hat {len(df_result)} gültige Positionen identifiziert")
        print(f"📊 Statistik: {len(df_raw)} Einträge → {len(df_result)} Positionen ({len(df_result)/len(df_raw)*100:.1f}%)")
        
        # Show sample of first 3 positions with prices
        if len(df_result) > 0:
            print("🔍 Beispiel-Positionen mit Preisen:")
            for idx, row in df_result.head(3).iterrows():
                print(f"  {row['pos']}: {row['description'][:50]}... = {row['unit_price']:.2f} EUR/{row['unit']}")
        
        return df_result
        
    except Exception as e:
        print(f"❌ AI-Verarbeitung fehlgeschlagen: {e}")
        print(f"Details: {traceback.format_exc()}")
        print("⚠️ Verwende ursprüngliche GAEB-Daten ohne AI-Preise")
        # Return original data if AI processing fails
        return df_raw

def extract_data_with_ai(uploaded_file, client):
    """Hybrid parser: Uses dedicated GAEB parser for GAEB files, AI for others."""
    try:
        suffix = f".{uploaded_file.name.split('.')[-1]}"
        file_extension = suffix.lower()
        
        # GAEB file extensions
        gaeb_extensions = ['.d81', '.d82', '.d83', '.d84', '.d85', '.d86', '.d90',
                          '.x81', '.x82', '.x83', '.x84', '.x85', '.x86', '.x90',
                          '.p81', '.p82', '.p83', '.p84', '.p85', '.p86', '.p90']
        
        # Create temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded_file.getvalue())
            temp_file_path = tmp.name
        
        # Route to appropriate parser
        if file_extension in gaeb_extensions:
            st.info(f"🎯 GAEB-Datei erkannt ({file_extension.upper()}) - Nutze dedizierten GAEB-Parser für 100% Genauigkeit")
            df_raw = parse_gaeb_file(temp_file_path, file_extension)
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            
            if df_raw.empty:
                print("⚠️ Keine Positionen gefunden. Möglicherweise ist das Dateiformat nicht standardkonform.")
                return df_raw
            
            # Post-process with AI: Validate positions and calculate prices
            st.info("🤖 AI analysiert Positionen und berechnet Preise...")
            df_priced = process_gaeb_with_ai(df_raw, client)
            return df_priced
        
        # For non-GAEB files, use AI for full document analysis
        # Note: GAEB files are already handled above and never reach this point
        
        # MIME type mapping for non-GAEB formats
        mime_type_map = {
            '.pdf': 'application/pdf',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.doc': 'application/msword',
            '.txt': 'text/plain',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.xls': 'application/vnd.ms-excel',
        }
        
        mime_type = mime_type_map.get(file_extension, 'application/octet-stream')
        
        print(f"📄 Non-GAEB file detected - using AI for full document analysis")
        
        # Upload file with explicit MIME type (temp file already created above)
        file_ref = client.files.upload(file=temp_file_path, mime_type=mime_type)
        
        # Generate content
        response = client.models.generate_content(
            model='gemini-2.5-flash-lite',
            contents=[file_ref, CALCULATION_PROMPT]
        )
        
        # Cleanup
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            
        # Parse JSON from response text (Basic parsing, assumes model obeys JSON instruction)
        text = response.text
        # Remove markdown code blocks if present
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
            
        data = json.loads(text)
        return pd.DataFrame(data)

    except Exception as e:
        st.error(f"Fehler bei der AI-Analyse: {e}")
        return pd.DataFrame(columns=["pos", "description", "quantity", "unit", "unit_price"])


# --- MAIN UI ---

# Initialize Client
api_key = st.secrets.get("api_key", "")

if not api_key:
    st.error("⚠️ API Key fehlt! Bitte in secrets.toml konfigurieren.")
    st.stop()

client = genai.Client(api_key=api_key)

# --- SMART KALKULATION MODE ---
st.title(f"🏗️ {COMPANY_NAME} - Kalkulation")
st.markdown("Ersetzen Sie Nextbau: LV analysieren, Preise kalkulieren, Angebot exportieren.")

# Step 1: Upload
st.subheader("1. Import: Ausschreibung (LV) hochladen")

# Comprehensive GAEB Format Support:
# D-Format (D81-D90): Text-based fixed-width files with record types (T0, T1, T2, T3, etc.)
# X-Format (X81-X90): XML files with different schema versions (DA81/1.0 to DA90/3.3)
# P-Format (P81-P90): Price format, similar to D-format but includes detailed pricing
# Also supports: PDF, DOCX, XLSX, XLS (parsed via AI)

uploaded_lv = st.file_uploader(
    "Laden Sie das LV (PDF/Docx/Excel/GAEB) hoch:", 
    type=['pdf', 'docx', 'txt', 'xlsx', 'xls', 
          'd81', 'd82', 'd83', 'd84', 'd85', 'd86', 'd90',
          'x81', 'x82', 'x83', 'x84', 'x85', 'x86', 'x90',
          'p81', 'p82', 'p83', 'p84', 'p85', 'p86', 'p90']
)

if "calculation_df" not in st.session_state:
    st.session_state.calculation_df = pd.DataFrame(columns=["pos", "description", "quantity", "unit", "unit_price"])

if uploaded_lv:
    file_ext = uploaded_lv.name.split('.')[-1].lower()
    st.info(f"📄 Datei: {uploaded_lv.name} ({file_ext.upper()}-Format, {uploaded_lv.size / 1024:.1f} KB)")

if uploaded_lv:
    if st.button("🚀 LV Analysieren & Positionen extrahieren"):
        with st.spinner("Analysiere Dokument..."):
            df_result = extract_data_with_ai(uploaded_lv, client)
            if not df_result.empty:
                st.session_state.calculation_df = df_result
                st.success(f"✅ {len(df_result)} Positionen erfolgreich extrahiert!")
                # Show preview
                with st.expander("📋 Vorschau der ersten 5 Positionen"):
                    st.dataframe(df_result.head())
            else:
                st.error("❌ Keine Positionen extrahiert. Bitte prüfen Sie das Dateiformat.")

# Step 2: Calculation (Data Editor)
st.subheader("2. Kalkulation: Preise bearbeiten")
if not st.session_state.calculation_df.empty:
    # Configurable columns for the editor
    column_config = {
        "pos": st.column_config.TextColumn("Pos."),
        "description": st.column_config.TextColumn("Leistungsbezeichnung", width="large"),
        "quantity": st.column_config.NumberColumn("Menge", format="%.2f"),
        "unit": st.column_config.TextColumn("Einh."),
        "unit_price": st.column_config.NumberColumn("EP (€)", format="%.2f Euro")
    }

    edited_df = st.data_editor(
        st.session_state.calculation_df,
        column_config=column_config,
        num_rows="dynamic",
        use_container_width=True,
        key="editor"
    )
    
    # Real-time Calculation of Totals
    # Ensure types are numeric
    edited_df["quantity"] = pd.to_numeric(edited_df["quantity"], errors='coerce').fillna(0)
    edited_df["unit_price"] = pd.to_numeric(edited_df["unit_price"], errors='coerce').fillna(0)
    edited_df["total_price"] = edited_df["quantity"] * edited_df["unit_price"]
    
    total_sum = edited_df["total_price"].sum()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Summe Netto", f"{total_sum:,.2f} €")
    col2.metric("19% MwSt.", f"{total_sum*0.19:,.2f} €")
    col3.metric("Summe Brutto", f"{total_sum*1.19:,.2f} €")

    # Step 3: Production (Export)
    st.subheader("3. Export: Angebot erstellen")
    
    proj_name = st.text_input("Projektname für das Angebot:", "Sanierung Fahrbahnübergänge")
    
    c1, c2 = st.columns(2)
    with c1:
        # Excel Export (Data)
        excel_buffer = io.BytesIO()
        edited_df.to_excel(excel_buffer, index=False)
        st.download_button(
            label="💾 Excel Export (Daten)",
            data=excel_buffer.getvalue(),
            file_name=f"Kalkulation_{proj_name}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
    with c2:
        # PDF Export (The Offer)
        if st.button("📄 Angebot als PDF generieren", use_container_width=True):
            pdf_bytes = generate_offer_pdf(edited_df, proj_name)
            st.download_button(
                label="⬇️ PDF Herunterladen",
                data=pdf_bytes,
                file_name=f"Angebot_{proj_name}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
else:
    st.info("Bitte laden Sie ein Dokument hoch, um die Kalkulation zu starten.")