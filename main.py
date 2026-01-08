import streamlit as st
import google.genai as genai
import tempfile
import os
import pandas as pd
import json
import io
from datetime import datetime
from fpdf import FPDF
import re
import traceback
import time
from google.genai.errors import ServerError, APIError

# --- CONSTANTS & CONFIGURATION ---
COMPANY_NAME = "Rüttenscheid Baukonzepte GmbH"

# Master AI Prompt - Handles ALL file types
MASTER_EXTRACTION_PROMPT = """
Du bist ein erfahrener Baukalkulator mit 25 Jahren Erfahrung bei der Rüttenscheid Baukonzepte GmbH.

DEINE AUFGABE:
Analysiere das hochgeladene Dokument (GAEB-Datei, PDF, Excel, Word) und extrahiere ALLE Bauleistungspositionen mit vollständiger Kalkulation.

⚠️ WICHTIG - ZEICHENCODIERUNG:
Falls du korrupte Zeichen wie �, �, oder ähnliche Symbole siehst, korrigiere sie zu korrekten deutschen Umlauten:

B�den → Böden
M�rtel → Mörtel
F�hren → Führen
Oberfl�che → Oberfläche
Verg�tung → Vergütung
Schl�ssel → Schlüssel
Nutze den Kontext, um die korrekte Bedeutung zu erkennen und deutsche Umlaute (ä, ö, ü, ß) richtig einzusetzen.
WICHTIGE ANWEISUNGEN:

POSITIONSIDENTIFIKATION:
✓ POSITION IST: Jede Zeile mit einer Leistungsbeschreibung UND Mengenangabe
✓ Beispiele: "Einrichten Baustelle", "Abbruch Mauerwerk", "Lieferung Beton C25/30"
✗ KEINE POSITION: Reine Überschriften, Abschnittstitel, Bemerkungen ohne Menge
✗ Beispiele: "Kogr. 391", "Baustelleneinrichtung" (nur Titel), "Hinweis: ..."

DATEN EXTRAKTION:

Positionsnummer: Extrahiere die EXAKTE Nummer (z.B. "01.01.0010", "0010", "1.2.3")
Falls keine Nummer vorhanden: Vergebe fortlaufende Nummern (0001, 0002, 0003, ...)

Beschreibung: Vollständige Leistungsbeschreibung (nicht nur Titel!)
Beispiel: "Erdarbeiten, Oberboden abtragen und zwischenlagern, Schichtdicke bis 30 cm"

Menge: Die EXAKTE numerische Menge (z.B. 150.5, 25, 1)
Falls nicht angegeben: 1.0

Einheit: Die EXAKTE Maßeinheit (m, m², m³, St, Std, t, kg, Psch, to, l, etc.)
Falls nicht angegeben: "Psch" (Pauschale)

PREISKALKULATION (SEHR WICHTIG):
Berechne für JEDE Position einen realistischen, marktgerechten Einheitspreis (netto, ohne MwSt.).

Berücksichtige:

Materialkosten (Einkauf, Beschaffung, Verschnitt 3-5%)
Lohnkosten (Facharbeiter ~45-55 EUR/Std, Hilfskraft ~35-45 EUR/Std)
Gerätekosten (Abschreibung, Betriebsstoffe, Vorhalten)
Transportkosten (An- und Abfahrt, Materialtransport)
Baustellengemeinkosten (BGK: ~8-12%)
Allgemeine Geschäftskosten (AGK: ~5-8%)
Wagnis & Gewinn (W&G: ~3-5%)
PREISBEISPIELE zur Orientierung:

Baustelleneinrichtung: 1.500 - 5.000 EUR (Pauschale)
Erdaushub Bagger: 8-15 EUR/m³
Beton C25/30 liefern und einbauen: 180-250 EUR/m³
Mauerwerk Ziegel herstellen: 85-120 EUR/m²
Bewehrung liefern und verlegen: 1.200-1.800 EUR/t
Schalung herstellen und abbrechen: 35-65 EUR/m²
Dachziegel decken: 45-75 EUR/m²
Putz innen auftragen: 25-40 EUR/m²
Fliesen verlegen: 40-80 EUR/m²
⚠️ KRITISCH: JEDE Position MUSS einen Preis > 0 haben!
Keine Position darf unit_price: 0.0 haben!

AUSGABEFORMAT:
Gib NUR ein valides JSON-Array zurück.
KEINE Markdown-Formatierung, KEINE Erklärungen, KEINE zusätzlichen Texte.
NUR das reine JSON-Array.

Format:
[
{"pos": "0010", "description": "Vollständige Beschreibung", "quantity": 10.5, "unit": "m²", "unit_price": 45.50},
{"pos": "0020", "description": "Nächste Position...", "quantity": 25.0, "unit": "m³", "unit_price": 125.00}
]

QUALITÄTSKRITERIEN:
✓ Mindestens 5 Zeichen pro Beschreibung
✓ Alle Mengen müssen Zahlen sein (keine Texte)
✓ Alle Preise müssen > 0 sein
✓ Einheiten müssen sinnvolle Baueinheiten sein

Starte jetzt die Analyse und gib NUR das JSON-Array zurück!
"""

# Secondary prompt if first attempt returns zero prices
PRICING_CORRECTION_PROMPT = """
Du bist Kalkulations-Experte. Die folgenden Positionen haben teilweise Preis 0.00 oder unrealistische Preise.

AUFGABE: Korrigiere ALLE Preise und stelle sicher, dass jede Position einen realistischen Marktpreis hat.

REGELN:

JEDE Position MUSS unit_price > 0 haben
Preise müssen marktgerecht und wettbewerbsfähig sein
Berücksichtige Material, Lohn, Geräte, Transport, BGK, AGK, W&G
Orientierung an typischen Baupreisen 2024/2025
PREISREFERENZEN:

Einfache Arbeiten (Aushub, Abbruch): 10-50 EUR
Mittlere Komplexität (Mauerwerk, Schalung): 50-150 EUR
Hohe Komplexität (Beton, Bewehrung): 150-300 EUR
Spezialleistungen (Abdichtung, Dämmung): 300+ EUR
Eingabe-Positionen:
{positions_json}

AUSGABE: NUR das vollständige JSON-Array mit ALLEN Positionen und korrigierten Preisen.
Keine Erklärungen, nur JSON!
"""

# --- AI EXTRACTION FUNCTIONS ---
def get_mime_type(file_path):
    """
    Determine MIME type based on file extension.
    """
    ext = os.path.splitext(file_path)[1].lower()
    
    mime_types = {
        # Documents
        '.pdf': 'application/pdf',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.doc': 'application/msword',
        '.txt': 'text/plain',
        
        # Spreadsheets
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.xls': 'application/vnd.ms-excel',
        
        # GAEB files (German construction standard) - all as text/plain for Gemini compatibility
        '.d81': 'text/plain', '.d82': 'text/plain', '.d83': 'text/plain',
        '.d84': 'text/plain', '.d85': 'text/plain', '.d86': 'text/plain', '.d90': 'text/plain',
        '.x81': 'text/plain', '.x82': 'text/plain', '.x83': 'text/plain',
        '.x84': 'text/plain', '.x85': 'text/plain', '.x86': 'text/plain', '.x90': 'text/plain',
        '.p81': 'text/plain', '.p82': 'text/plain', '.p83': 'text/plain',
        '.p84': 'text/plain', '.p85': 'text/plain', '.p86': 'text/plain', '.p90': 'text/plain',
    }
    
    return mime_types.get(ext, 'application/octet-stream')

def call_ai_with_retry(client, model, contents, max_retries=3, initial_delay=5):
    """
    Call AI API with exponential backoff retry logic and automatic model switching.
    Tries alternative models when encountering 503 (overloaded) or 429 (quota exceeded) errors.
    Returns tuple: (response, model_used)
    """
    # Define available models in priority order
    available_models = [
        'gemini-2.5-flash',
        'gemini-2.5-flash-lite',
        'gemini-2.0-flash',
        'gemini-2.0-flash-lite',
        'gemini-2.5-pro'
    ]
    
    # Start with the requested model, then try others if needed
    if model in available_models:
        # Move requested model to front
        models_to_try = [model] + [m for m in available_models if m != model]
    else:
        models_to_try = available_models
    
    last_error = None
    
    for model_idx, current_model in enumerate(models_to_try):
        print(f"🤖 Trying model: {current_model}")
        
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model=current_model,
                    contents=contents
                )
                if model_idx > 0:
                    print(f"✅ Successfully switched to model: {current_model}")
                return response, current_model
                
            except ServerError as e:
                last_error = e
                if e.status_code == 503:
                    # Model overloaded - try next model
                    print(f"⚠️ Model {current_model} is overloaded (503)")
                    if model_idx < len(models_to_try) - 1:
                        print(f"🔄 Switching to next model...")
                        break  # Break inner loop to try next model
                    elif attempt < max_retries - 1:
                        wait_time = initial_delay * (2 ** attempt)
                        print(f"⚠️ All models tried. Retrying in {wait_time}s... (Attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                    else:
                        # Last model, last attempt
                        continue
                else:
                    raise
                    
            except APIError as e:
                last_error = e
                if hasattr(e, 'status_code') and e.status_code == 429:
                    error_str = str(e)
                    
                    # Check if this is a token quota error (per-minute limit)
                    if 'input_token_count' in error_str or 'GenerateContentInputTokensPerModelPerMinute' in error_str:
                        print(f"⚠️ Token quota exceeded for {current_model}")
                        
                        # Extract retry delay from error message
                        retry_delay = 60  # Default
                        match = re.search(r'retry in (\d+(?:\.\d+)?)', error_str, re.IGNORECASE)
                        if match:
                            retry_delay = float(match.group(1))
                        
                        if model_idx < len(models_to_try) - 1:
                            print(f"🔄 Switching to next model...")
                            break  # Try next model
                        elif attempt < max_retries - 1:
                            print(f"⚠️ Waiting {retry_delay:.0f}s before retry...")
                            time.sleep(retry_delay)
                        else:
                            continue
                    else:
                        # Daily request quota exceeded - try next model
                        print(f"⚠️ Request quota exceeded for {current_model}")
                        if model_idx < len(models_to_try) - 1:
                            print(f"🔄 Switching to next model...")
                            break  # Try next model
                        else:
                            raise
                            
                elif hasattr(e, 'status_code') and e.status_code in [500, 502, 504]:
                    if attempt < max_retries - 1:
                        wait_time = initial_delay * (2 ** attempt)
                        print(f"⚠️ API error ({e.status_code}). Retrying in {wait_time}s... (Attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                    else:
                        if model_idx < len(models_to_try) - 1:
                            print(f"🔄 Trying next model...")
                            break
                        else:
                            raise
                else:
                    raise
    
    # If we got here, all models failed
    if last_error:
        raise last_error
    else:
        raise Exception("All models exhausted without successful response")

def safe_remove_file(file_path, max_retries=3, delay=0.5):
    """
    Safely remove a file with retry logic for Windows file locking issues.
    """
    for attempt in range(max_retries):
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            return True
        except PermissionError:
            if attempt < max_retries - 1:
                time.sleep(delay)
            else:
                print(f"⚠️ Could not delete temporary file: {file_path}")
                return False
        except Exception as e:
            print(f"⚠️ Error deleting file: {e}")
            return False
    return False

def sanitize_filename(filename):
    """
    Sanitize filename by replacing special characters and umlauts.
    """
    # Replace German umlauts
    replacements = {
        'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss',
        'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue',
        ' ': '_',  # Replace spaces with underscores
        '/': '-', '\\': '-', ':': '-', '*': '-', '?': '-',
        '"': '-', '<': '-', '>': '-', '|': '-'
    }
    
    sanitized = filename
    for char, replacement in replacements.items():
        sanitized = sanitized.replace(char, replacement)
    
    # Remove any remaining non-ASCII characters
    sanitized = ''.join(c for c in sanitized if ord(c) < 128)
    
    return sanitized

def read_excel_as_text(file_path):
    """
    Read Excel file and convert to text format for AI processing.
    """
    try:
        # Read all sheets with context manager to ensure proper cleanup
        with pd.ExcelFile(file_path) as excel_file:
            text_content = ""
            
            for sheet_name in excel_file.sheet_names:
                df = pd.read_excel(excel_file, sheet_name=sheet_name)
                text_content += f"\n\n=== SHEET: {sheet_name} ===\n\n"
                text_content += df.to_string(index=False)
        
        return text_content
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        return None

def extract_with_ai(file_path, file_extension, client):
    """
    Master extraction function - sends file directly to AI for complete analysis.
    """
    # Start total timer
    total_start_time = time.time()
    
    try:
        print(f"\n{'='*70}")
        print(f"🤖 AI-POWERED EXTRACTION")
        print(f"📄 File: {os.path.basename(file_path)}")
        print(f"📝 Extension: {file_extension}")
        print(f"{'='*70}\n")
        
        # Check if file is Excel - handle differently
        ext = file_extension.lower()
        if ext in ['.xlsx', '.xls']:
            print(f"📊 Processing Excel file locally...")
            read_start = time.time()
            excel_text = read_excel_as_text(file_path)
            read_time = time.time() - read_start
            print(f"✅ Excel file read successfully ({read_time:.2f}s)")
            
            if excel_text is None:
                raise Exception("Failed to read Excel file")
            
            # Send text content to AI
            print(f"\n🧠 AI analyzing document...")
            print(f"   Starting with: gemini-2.5-flash-lite (will auto-switch if needed)")
            
            analysis_start = time.time()
            prompt_with_data = f"{MASTER_EXTRACTION_PROMPT}\n\nDOKUMENT INHALT:\n{excel_text}"
            response, model_used = call_ai_with_retry(
                client=client,
                model='gemini-2.5-flash-lite',
                contents=[prompt_with_data]
            )
        else:
            # For other file types, upload to Gemini
            print(f"📤 Uploading file to AI...")
            upload_start = time.time()
            
            # Determine MIME type
            mime_type = get_mime_type(file_path)
            print(f"   MIME Type: {mime_type}")
            
            # Upload file to Gemini - let it auto-detect or specify in config
            try:
                # Try with config parameter
                file_ref = client.files.upload(
                    file=file_path,
                    config={'mime_type': mime_type}
                )
            except TypeError:
                # Fallback: let it auto-detect
                file_ref = client.files.upload(file=file_path)
            
            upload_time = time.time() - upload_start
            print(f"✅ File uploaded successfully ({upload_time:.2f}s)")
            print(f"   File URI: {file_ref.uri}")
            print(f"   File Name: {file_ref.name}")
            
            # Send to AI with master prompt
            print(f"\n🧠 AI analyzing document...")
            print(f"   Starting with: gemini-2.5-flash-lite (will auto-switch if needed)")
            
            analysis_start = time.time()
            response, model_used = call_ai_with_retry(
                client=client,
                model='gemini-2.5-flash-lite',
                contents=[file_ref, MASTER_EXTRACTION_PROMPT]
            )
        analysis_time = time.time() - analysis_start
        
        if model_used != 'gemini-2.5-flash-lite':
            print(f"   ✓ Used model: {model_used}")
        
        text = response.text
        print(f"\n📥 AI Response received ({analysis_time:.2f}s)")
        print(f"   Length: {len(text)} characters")
        
        # Parse JSON response
        parse_start = time.time()
        df = parse_json_response(text)
        parse_time = time.time() - parse_start
        print(f"   Parsing time: {parse_time:.2f}s")
        
        if not df.empty:
            print(f"\n✅ Extraction successful: {len(df)} positions found")
            
            # Check for zero prices
            zero_prices = (df['unit_price'] == 0).sum()
            if zero_prices > 0:
                print(f"⚠️  Warning: {zero_prices} positions with zero price")
                print(f"🔧 Requesting AI to fix prices...")
                price_fix_start = time.time()
                df = fix_prices_with_ai(df, client)
                price_fix_time = time.time() - price_fix_start
                print(f"   Price fixing time: {price_fix_time:.2f}s")
            
            # Calculate total time
            total_time = time.time() - total_start_time
            print(f"\n{'='*70}")
            print(f"⏱️  TOTAL PROCESSING TIME: {total_time:.2f} seconds ({total_time/60:.2f} minutes)")
            print(f"{'='*70}\n")
            
            return df
        else:
            print(f"❌ No positions extracted from AI response")
            total_time = time.time() - total_start_time
            print(f"⏱️  Total time: {total_time:.2f}s")
            return pd.DataFrame(columns=["pos", "description", "quantity", "unit", "unit_price"])
    
    except Exception as e:
        print(f"❌ AI Extraction Error: {str(e)}")
        print(f"🔍 Details: {traceback.format_exc()}")
        total_time = time.time() - total_start_time
        print(f"⏱️  Time before error: {total_time:.2f}s")
        return pd.DataFrame(columns=["pos", "description", "quantity", "unit", "unit_price"])

def parse_json_response(text):
    """
    Parse JSON from AI response with multiple fallback strategies.
    """
    try:
        # Clean the response
        text = text.strip()
        
        print(f"🔍 Parsing JSON response...")
        
        # Strategy 1: Direct JSON parse
        try:
            data = json.loads(text)
            if isinstance(data, list) and len(data) > 0:
                df = pd.DataFrame(data)
                print(f"✓ JSON parsed (direct): {len(df)} positions")
                return df
        except:
            pass
        
        # Strategy 2: Extract from markdown code blocks
        patterns = [
            r'```json\s*(\[.*?\])\s*```',  # ```json [...] ```
            r'```\s*(\[.*?\])\s*```',       # ``` [...] ```
            r'(\[.*?\])',                    # [...] anywhere in text
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                try:
                    data = json.loads(match)
                    if isinstance(data, list) and len(data) > 0:
                        df = pd.DataFrame(data)
                        print(f"✓ JSON parsed (pattern match): {len(df)} positions")
                        return df
                except:
                    continue
        
        # Strategy 3: Find JSON array manually
        start = text.find('[')
        end = text.rfind(']')
        if start != -1 and end != -1 and end > start:
            try:
                json_str = text[start:end+1]
                data = json.loads(json_str)
                if isinstance(data, list) and len(data) > 0:
                    df = pd.DataFrame(data)
                    print(f"✓ JSON parsed (manual extraction): {len(df)} positions")
                    return df
            except:
                pass
        
        print(f"⚠️  Could not parse JSON from response")
        print(f"📄 Response preview: {text[:500]}")
        return pd.DataFrame(columns=["pos", "description", "quantity", "unit", "unit_price"])
    
    except Exception as e:
        print(f"❌ JSON parsing error: {e}")
        return pd.DataFrame(columns=["pos", "description", "quantity", "unit", "unit_price"])

def fix_prices_with_ai(df, client):
    """
    Send positions back to AI to fix zero or missing prices.
    """
    try:
        print(f"\n🔧 PRICE CORRECTION WITH AI")
        
        # Convert to JSON
        positions_json = df.to_json(orient='records', force_ascii=False, indent=2)
        
        print(f"📤 Sending {len(df)} positions for price correction...")
        
        # Create prompt with positions
        prompt = PRICING_CORRECTION_PROMPT.format(positions_json=positions_json)
        
        # Send to AI with retry logic
        response, model_used = call_ai_with_retry(
            client=client,
            model='gemini-2.5-flash-lite',
            contents=[prompt]
        )
        
        if model_used != 'gemini-2.5-flash-lite':
            print(f"   ✓ Used alternate model: {model_used}")
        
        # Parse response
        df_fixed = parse_json_response(response.text)
        
        if not df_fixed.empty:
            zero_after = (df_fixed['unit_price'] == 0).sum()
            print(f"✅ Prices fixed: {zero_after} zero prices remaining")
            return df_fixed
        else:
            print(f"⚠️  Price fix failed, returning original")
            return df
            
    except Exception as e:
        print(f"❌ Price fixing error: {e}")
        return df

# --- PDF GENERATION ---
class OfferPDF(FPDF):
    def header(self):
        self.set_font("Arial", 'B', 14)
        self.set_text_color(0, 0, 0)
        self.cell(100, 8, "RUTTENSCHEID BAUKONZEPTE", ln=0, align='L')
        self.set_font("Arial", '', 10)
        self.cell(0, 8, f"Datum: {datetime.now().strftime('%d.%m.%Y')}", ln=1, align='R')
        self.set_font("Arial", '', 10)
        self.cell(100, 5, "Munchener Str. 100 A, 45145 Essen", ln=1, align='L')
        self.ln(10)
    
    def footer(self):
        self.set_y(-35)
        self.set_draw_color(200, 200, 200)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(2)
        self.set_font("Arial", '', 8)
        self.set_text_color(80, 80, 80)
        
        col_width = 63
        x_start = 10
        self.set_xy(x_start, self.get_y())
        self.multi_cell(col_width, 4,
            "Ruttenscheid Baukonzepte GmbH\n"
            "Munchener Str. 100A\n"
            "45145 Essen\n"
            "Geschaftsfuhrer: Dipl.-Ing. Moh Alturky", align='L')
        
        self.set_xy(x_start + col_width, self.get_y() - 16)
        self.multi_cell(col_width, 4,
            "Tel: +49 0201 84850166\n"
            "Mob: +49 160 7901911\n"
            "E-Mail: Moh@ruttenscheid-bau.de\n"
            "Web: www.ruttenscheid-bau.de", align='C')
        
        self.set_xy(x_start + (col_width * 2), self.get_y() - 16)
        self.cell(col_width, 4, f"Seite {self.page_no()}", align='R')

def generate_offer_pdf(df, project_name):
    """Generate professional PDF offer."""
    pdf = OfferPDF()
    pdf.set_auto_page_break(auto=True, margin=40)
    pdf.add_page()
    
    def clean(text):
        if pd.isna(text):
            return ""
        text = str(text)
        replacements = {
            "€": "EUR", "–": "-", "„": '"', "“": '"', "'": "'",
            "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "Ä": "Ae",
            "Ö": "Oe", "Ü": "Ue", "²": "2", "³": "3"
        }
        for char, rep in replacements.items():
            text = text.replace(char, rep)
        return text.encode('latin-1', 'replace').decode('latin-1')
    
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(100, 8, "Auftraggeber", 0, 0, 'L')
    pdf.cell(90, 8, clean(f"Angebot Nr. {datetime.now().strftime('%Y-%m-%d')}"), 0, 1, 'R')
    pdf.set_font("Arial", '', 11)
    pdf.cell(100, 6, clean("Bauherr"), 0, 0, 'L')
    pdf.cell(90, 6, clean(f"Projekt: {project_name}"), 0, 1, 'R')
    pdf.ln(15)
    
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, clean(f"Angebot: {project_name}"), ln=1, align='L')
    pdf.set_font("Arial", '', 11)
    pdf.multi_cell(0, 6, clean("Sehr geehrte Damen und Herren,\nhiermit unterbreiten wir Ihnen unser Angebot gemaß Ihrer Anfrage."))
    pdf.ln(10)
    
    # Table Header
    pdf.set_fill_color(230, 230, 230)
    pdf.set_font("Arial", 'B', 9)
    pdf.set_draw_color(180, 180, 180)
    
    w = [20, 85, 20, 15, 25, 25]
    pdf.cell(w[0], 8, "Pos.", 1, 0, 'C', 1)
    pdf.cell(w[1], 8, "Bezeichnung", 1, 0, 'L', 1)
    pdf.cell(w[2], 8, "Menge", 1, 0, 'C', 1)
    pdf.cell(w[3], 8, "Einh.", 1, 0, 'C', 1)
    pdf.cell(w[4], 8, "EP (EUR)", 1, 0, 'R', 1)
    pdf.cell(w[5], 8, "GP (EUR)", 1, 1, 'R', 1)
    
    # Table Content
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
        
        pos = clean(str(row.get('pos', '')))
        desc = clean(str(row.get('description', '')))[:45]
        unit = clean(str(row.get('unit', '')))
        
        pdf.cell(w[0], 8, pos, 1, 0, 'C')
        pdf.cell(w[1], 8, desc, 1, 0, 'L')
        pdf.cell(w[2], 8, f"{qty:.2f}", 1, 0, 'C')
        pdf.cell(w[3], 8, unit, 1, 0, 'C')
        pdf.cell(w[4], 8, f"{ep:,.2f}", 1, 0, 'R')
        pdf.cell(w[5], 8, f"{gp:,.2f}", 1, 1, 'R')
    
    # Totals
    pdf.ln(5)
    
    def print_total(label, value, bold=False):
        pdf.set_font("Arial", 'B' if bold else '', 10)
        pdf.cell(145, 8, clean(label), 0, 0, 'R')
        pdf.cell(45, 8, f"{value:,.2f} EUR", 1 if bold else 0, 1, 'R')
    
    print_total("Summe Netto:", total_netto)
    print_total("zzgl. 19% MwSt.:", total_netto * 0.19)
    pdf.ln(2)
    print_total("Gesamtbetrag (Brutto):", total_netto * 1.19, bold=True)
    
    pdf.ln(15)
    pdf.set_font("Arial", '', 10)
    pdf.multi_cell(0, 5, clean("Wir hoffen, Ihnen ein interessantes Angebot unterbreitet zu haben und stehen fur Ruckfragen gerne zur Verfugung."))
    pdf.ln(10)
    pdf.cell(0, 10, clean("Mit freundlichen Grußen"), ln=1)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 10, clean("Ruttenscheid Baukonzepte GmbH"), ln=1)
    
    return pdf.output(dest='S').encode('latin-1', 'replace')


# --- STREAMLIT UI ---
st.set_page_config(
    page_title="Rüttenscheid Smart Kalkulation",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Initialize API Client
api_key = st.secrets.get("api_key", "")

if not api_key:
    st.error("⚠️ API Key fehlt! Bitte in secrets.toml konfigurieren.")
    st.stop()

client = genai.Client(api_key=api_key)

# Header with logo and company name centered
logo_path = "Data/Screenshot 2026-01-07 214122.png"

# Create centered header with logo and text
col1, col_center, col3 = st.columns([1, 2, 1])

with col_center:
    if os.path.exists(logo_path):
        # Center the smaller logo using columns
        logo_col1, logo_col2, logo_col3 = st.columns([1, 1, 1])
        with logo_col2:
            st.image(logo_path, width=200)
    
    st.markdown(f"""
    <div style='text-align: center;'>
        <h1 style='color: #1e3a8a; margin: 1px0 0; font-size: 2.5em;'>{COMPANY_NAME}</h1>
        <p style='color: #3b82f6; font-size: 1.2em; margin: 10px 0 0 0;'>🤖 KI-Gestützte Angebotserstellung</p>
    </div>
    """, unsafe_allow_html=True)


# Initialize session state
if "calculation_df" not in st.session_state:
    st.session_state.calculation_df = pd.DataFrame(
        columns=["pos", "description", "quantity", "unit", "original_price", "unit_price", "price_factor"]
    )
if "price_factor" not in st.session_state:
    st.session_state.price_factor = 1.0
if "project_name" not in st.session_state:
    st.session_state.project_name = "Bauprojekt"
if "file_uploader_key" not in st.session_state:
    st.session_state.file_uploader_key = 0

# Step 1: Upload
st.markdown("---")
col_header1, col_header2 = st.columns([4, 1])
with col_header1:
    st.subheader("📤 Schritt 1: Dokument hochladen")
with col_header2:
    if not st.session_state.calculation_df.empty:
        if st.button("🔄 Neu starten", use_container_width=True, help="Alle Daten löschen und von vorne beginnen"):
            st.session_state.calculation_df = pd.DataFrame(
                columns=["pos", "description", "quantity", "unit", "original_price", "unit_price", "price_factor"]
            )
            st.session_state.price_factor = 1.0
            st.session_state.file_uploader_key += 1  # Reset file uploader
            st.rerun()

uploaded_file = st.file_uploader(
    "Wählen Sie eine Datei:",
    type=['pdf', 'docx', 'doc', 'txt', 'xlsx', 'xls',
          'd81', 'd82', 'd83', 'd84', 'd85', 'd86', 'd90',
          'x81', 'x82', 'x83', 'x84', 'x85', 'x86', 'x90',
          'p81', 'p82', 'p83', 'p84', 'p85', 'p86', 'p90'],
    help="Unterstützte Formate: GAEB (D/X/P), PDF, Word, Excel",
    key=f"file_uploader_{st.session_state.file_uploader_key}"
)

if uploaded_file:
    file_ext = uploaded_file.name.split('.')[-1].upper()
    file_size = uploaded_file.size / 1024
    
    st.markdown("""<div style='background-color: #f0f9ff; padding: 15px; border-radius: 8px; border-left: 4px solid #3b82f6; margin: 10px 0;'>""", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"**📄 Datei:**<br>{uploaded_file.name}", unsafe_allow_html=True)
    with col2:
        st.markdown(f"**📋 Format:**<br>{file_ext}", unsafe_allow_html=True)
    with col3:
        st.markdown(f"**💾 Größe:**<br>{file_size:.1f} KB", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    
    if st.button("🚀 Jetzt analysieren", type="primary", use_container_width=True, help="Dokument mit KI analysieren und Positionen extrahieren"):
        with st.spinner("🤖 KI analysiert das Dokument... Bitte warten..."):
            
            # Save uploaded file temporarily
            suffix = f".{uploaded_file.name.split('.')[-1]}"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(uploaded_file.getvalue())
                temp_path = tmp.name
            
            try:
                # Extract with AI
                df_result = extract_with_ai(temp_path, suffix.lower(), client)
                
                # Cleanup temp file
                safe_remove_file(temp_path)
                
                if not df_result.empty:
                    # Clean and validate data
                    df_result = df_result[df_result['description'].notna()]
                    df_result = df_result[df_result['description'].str.len() > 3]
                    df_result['quantity'] = pd.to_numeric(df_result['quantity'], errors='coerce').fillna(1.0)
                    df_result['unit_price'] = pd.to_numeric(df_result['unit_price'], errors='coerce').fillna(0.0)
                    # Store original prices
                    df_result['original_price'] = df_result['unit_price'].copy()
                    # Initialize price factor
                    df_result['price_factor'] = 1.0
                    df_result = df_result.reset_index(drop=True)
                    
                    st.session_state.calculation_df = df_result
                    st.session_state.price_factor = 1.0
                    st.success(f"✅ **Erfolgreich!** {len(df_result)} Positionen extrahiert")
                    
                    # Statistics with enhanced display
                    st.markdown("#### 📊 Extraktionsergebnis")
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("📋 Positionen", f"{len(df_result)}", help="Anzahl der gefundenen Positionen")
                    with col2:
                        priced = (df_result['unit_price'] > 0).sum()
                        st.metric("💰 Mit Preis", f"{priced}", help="Positionen mit Preisangabe")
                    with col3:
                        total = (df_result['quantity'] * df_result['unit_price']).sum()
                        st.metric("💵 Summe Netto", f"{total:,.0f} €", help="Gesamtsumme ohne MwSt.")
                    with col4:
                        total_brutto = total * 1.19
                        st.metric("✅ Summe Brutto", f"{total_brutto:,.0f} €", help="Gesamtsumme inkl. 19% MwSt.")
                else:
                    st.error("❌ Keine Positionen gefunden. Bitte prüfen Sie das Dokument.")
                    
            except Exception as e:
                st.error(f"❌ Fehler: {str(e)}")
                if "503" in str(e) or "overloaded" in str(e).lower():
                    st.warning("⚠️ Alle verfügbaren KI-Modelle sind derzeit überlastet. Bitte versuchen Sie es in einigen Minuten erneut.")
                    st.info("💡 Das System hat automatisch folgende Modelle versucht: gemini-2.5-flash, gemini-2.5-flash-lite, gemini-2.0-flash, gemini-2.0-flash-lite, gemini-2.5-pro")
                elif "429" in str(e) or "quota" in str(e).lower() or "RESOURCE_EXHAUSTED" in str(e):
                    if "input_token" in str(e) or "token" in str(e).lower():
                        st.warning("⚠️ Token-Limit für alle verfügbaren Modelle überschritten. Das System hat bereits mehrere Modelle versucht.")
                        st.info("💡 Tipp: Bei sehr großen Dateien kann es zu Token-Limits kommen. Versuchen Sie kleinere Dateien oder warten Sie 1-2 Minuten.")
                    else:
                        st.warning("⚠️ API-Quota für alle verfügbaren Modelle überschritten.")
                        st.info("💡 Das System hat automatisch 5 verschiedene Modelle versucht. Bitte warten Sie einige Minuten.")
                elif "Unsupported MIME type" in str(e) or "INVALID_ARGUMENT" in str(e):
                    st.warning("⚠️ Dieses Dateiformat wird möglicherweise nicht direkt unterstützt. Das System verarbeitet das Dokument lokal.")
                safe_remove_file(temp_path)

st.markdown("---")

# Step 2: Edit & Calculate
st.markdown("---")
st.subheader("✏️ Schritt 2: Positionen bearbeiten")

if not st.session_state.calculation_df.empty:
    
    st.markdown("""
    <div style='background-color: #fef3c7; padding: 12px; border-radius: 8px; border-left: 4px solid #f59e0b; margin: 10px 0;'>
        <strong>💡 Bearbeitungstipps:</strong><br>
        • Doppelklicken zum Bearbeiten einer Zelle<br>
        • Zeilen hinzufügen mit dem ➕ Button<br>
        • Zeilen löschen durch Auswahl und 🗑️ Button<br>
        • GP netto wird automatisch berechnet (Menge × EP)
    </div>
    """, unsafe_allow_html=True)
    
    # Calculate total price for display using price_factor
    display_df = st.session_state.calculation_df.copy()
    # Ensure price_factor column exists
    if 'price_factor' not in display_df.columns:
        display_df['price_factor'] = 1.0
    # EP netto stays as original unit_price, GP netto includes factor
    display_df['total_price'] = display_df['quantity'] * display_df['unit_price'] * display_df['price_factor']
    
    edited_df = st.data_editor(
        display_df,
        column_config={
            "pos": st.column_config.TextColumn("Pos.", width="small"),
            "description": st.column_config.TextColumn("Leistungsbezeichnung", width="large"),
            "quantity": st.column_config.NumberColumn("Menge", format="%.2f", min_value=0),
            "unit": st.column_config.TextColumn("Einheit", width="small"),
            "unit_price": st.column_config.NumberColumn("EP netto (€)", format="%.2f", min_value=0, help="Einheitspreis netto (Original-KI-Preis)"),
            "total_price": st.column_config.NumberColumn("GP netto (€)", format="%.2f", disabled=True, help="Gesamtpreis = Menge × EP × Faktor"),
            "original_price": None,  # Hide original_price column
            "price_factor": None  # Hide price_factor column
        },
        column_order=["pos", "description", "quantity", "unit", "unit_price", "total_price"],
        num_rows="dynamic",
        use_container_width=True,
        height=400,
        key="editor"
    )
    
    # Price multiplier with enhanced UI
    st.markdown("")
    st.markdown("**🔢 Preisanpassung - Alle Preise auf einmal ändern**")
    st.markdown("Passen Sie alle Einheitspreise gleichzeitig mit einem Faktor an.")
    col_mult1, col_mult2, col_mult3 = st.columns([2, 2, 1])
    with col_mult1:
        price_multiplier = st.number_input(
            "Multiplikator:",
            min_value=0.1,
            max_value=10.0,
            value=1.0,
            step=0.1,
            help="Faktor zur Preisanpassung"
        )
    with col_mult2:
        st.markdown("<div style='margin-top: 20px;'>", unsafe_allow_html=True)
        example_change = ((price_multiplier - 1) * 100)
        if price_multiplier > 1:
            st.info(f"➕ {example_change:.0f}% Aufschlag")
        elif price_multiplier < 1:
            st.info(f"➖ {abs(example_change):.0f}% Abschlag")
        else:
            st.info("Keine Änderung")
        st.markdown("</div>", unsafe_allow_html=True)
    with col_mult3:
        st.markdown("<div style='margin-top: 28px;'>", unsafe_allow_html=True)
        if st.button("✅ Anwenden", use_container_width=True, type="primary"):
            # Update price_factor instead of unit_price
            edited_df['price_factor'] = price_multiplier
            st.session_state.calculation_df = edited_df
            st.session_state.price_factor = price_multiplier
            st.success(f"✅ Preisfaktor {price_multiplier} angewendet! EP bleibt unverändert, GP wurde angepasst.")
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    
    # Calculate totals
    edited_df["quantity"] = pd.to_numeric(edited_df["quantity"], errors='coerce').fillna(0)
    edited_df["unit_price"] = pd.to_numeric(edited_df["unit_price"], errors='coerce').fillna(0)
    # Ensure price_factor exists
    if 'price_factor' not in edited_df.columns:
        edited_df['price_factor'] = 1.0
    edited_df["price_factor"] = pd.to_numeric(edited_df["price_factor"], errors='coerce').fillna(1.0)
    # Total includes the price factor
    edited_df["total_price"] = edited_df["quantity"] * edited_df["unit_price"] * edited_df["price_factor"]
    
    total_netto = edited_df["total_price"].sum()
    total_mwst = total_netto * 0.19
    total_brutto = total_netto * 1.19
    
    # Display totals
    st.markdown("")
    st.markdown("### 💰 Gesamtkalkulation")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("💵 Summe Netto", f"{total_netto:,.2f} €", help="Gesamtsumme ohne Mehrwertsteuer")
    with col2:
        st.metric("📊 MwSt. (19%)", f"{total_mwst:,.2f} €", help="Mehrwertsteuer 19%")
    with col3:
        st.metric("✅ Summe Brutto", f"{total_brutto:,.2f} €", delta=f"+{total_mwst:,.2f} €", help="Gesamtsumme inkl. MwSt.")
    
    st.markdown("---")
    
    # Step 3: Export
    st.markdown("---")
    st.subheader("📥 Schritt 3: Angebot exportieren")
    
    st.markdown("Geben Sie einen Projektnamen ein und wählen Sie das gewünschte Exportformat.")
    project_name = st.text_input(
        "📝 Projektname:",
        value=st.session_state.project_name,
        key="project_name_input",
        help="Dieser Name erscheint in allen exportierten Dokumenten",
        placeholder="z.B. Neubau Einfamilienhaus",
        on_change=lambda: setattr(st.session_state, 'project_name', st.session_state.project_name_input)
    )
    # Update session state with current value
    st.session_state.project_name = project_name
    
    st.markdown("")
    col1, col2 = st.columns(2)
    
    with col1:
        # Excel Export
        excel_buffer = io.BytesIO()
        # Prepare export dataframe with German column names
        export_df = edited_df[['pos', 'description', 'quantity', 'unit', 'unit_price']].copy()
        # Calculate GP with price factor
        if 'price_factor' in edited_df.columns:
            export_df['total_price'] = edited_df['quantity'] * edited_df['unit_price'] * edited_df['price_factor']
        else:
            export_df['total_price'] = edited_df['quantity'] * edited_df['unit_price']
        export_df.columns = ['Pos.', 'Leistungsbezeichnung', 'Menge', 'Einheit', 'EP netto (€)', 'GP netto (€)']
        export_df.to_excel(excel_buffer, index=False, engine='openpyxl')
        
        # Sanitize project name for filename
        safe_project_name = sanitize_filename(project_name)
        
        st.download_button(
            label="📊 Excel herunterladen",
            data=excel_buffer.getvalue(),
            file_name=f"Kalkulation_{safe_project_name}_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            help="Excel-Datei mit EP (Original-KI-Preis) und GP (mit Faktor berechnet)"
        )
    
    with col2:
        # PDF Export
        if st.button("📄 PDF generieren", use_container_width=True, type="primary"):
            with st.spinner("Erstelle PDF..."):
                try:
                    # Prepare dataframe for PDF with calculated total prices
                    pdf_df = edited_df.copy()
                    if 'price_factor' in pdf_df.columns:
                        pdf_df['total_price'] = pdf_df['quantity'] * pdf_df['unit_price'] * pdf_df['price_factor']
                    pdf_bytes = generate_offer_pdf(pdf_df, project_name)
                    
                    # Sanitize project name for filename
                    safe_project_name = sanitize_filename(project_name)
                    
                    st.download_button(
                        label="⬇️ PDF herunterladen",
                        data=pdf_bytes,
                        file_name=f"Angebot_{safe_project_name}_{datetime.now().strftime('%Y%m%d')}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                        help="PDF-Angebot mit Original-EP und berechneten GP-Werten"
                    )
                except Exception as e:
                    st.error(f"PDF-Fehler: {str(e)}")

else:
    st.markdown("""
    <div style='text-align: center; padding: 40px; background-color: #f9fafb; border-radius: 10px; margin: 20px 0;'>
        <h3 style='color: #6b7280;'>📋 Keine Daten vorhanden</h3>
        <p style='color: #9ca3af; font-size: 1.1em;'>
            Bitte laden Sie zuerst ein Dokument hoch, um mit der Bearbeitung zu beginnen.<br>
            Unterstützte Formate: GAEB, PDF, Excel, Word
        </p>
    </div>
    """, unsafe_allow_html=True)

# Footer with enhanced styling
st.markdown("---")
st.markdown(f"""
<div style='text-align: center; padding: 20px; color: #666;'>
    <p style='margin: 5px 0;'><strong>{COMPANY_NAME}</strong></p>
    <p style='margin: 5px 0; font-size: 0.85em; color: #999;'>© {datetime.now().year} Alle Rechte vorbehalten</p>
</div>
""", unsafe_allow_html=True)
