import streamlit as st
import google.genai as genai
import tempfile
import os
import pandas as pd
import json
import io
from datetime import datetime
from fpdf import FPDF

# --- CONSTANTS & CONFIGURATION ---
COMPANY_NAME = "Rüttenscheid Baukonzepte GmbH"

# This prompt is extracted from your 'chatgbt_Rü.docx' file
CALCULATION_PROMPT = """
Du bist ein erfahrener Kalkulator für die Rüttenscheid Baukonzepte GmbH.
Im Rahmen der folgenden Ausschreibungsunterlagen und Leistungsbeschreibungen bitte ich dich, sämtliche bereitgestellten Informationen gründlich und fachlich fundiert zu analysieren.
Berücksichtige bei deiner Auswertung insbesondere die projektspezifischen Randbedingungen, technischen Anforderungen, Bauzeitenvorgaben sowie mögliche baubetriebliche Restriktionen.

Für jede von mir einzeln übermittelte Leistungsposition ist auf dieser Grundlage ein realistischer, marktgerechter und zugleich wettbewerbsfähiger Einheitspreis (netto, ohne MwSt.) zu ermitteln.
Dieser Preis soll sämtliche relevanten Kostenfaktoren detailliert und vollständig abdecken (Material, Gerät, Transport, Lohn, Gemeinkosten).

WICHTIG: Gib das Ergebnis AUSSCHLIESSLICH als JSON-Liste zurück. 
Format: [{"pos": "01.01", "description": "Kurztext", "quantity": 100.0, "unit": "m2", "unit_price": 0.0}, ...]
Wenn keine Mengen im Dokument stehen, schätze sie oder setze 1.0.
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

def extract_data_with_ai(uploaded_file, client):
    """Uploads file to Gemini and extracts position data based on chatgbt_Rü logic."""
    try:
        suffix = f".{uploaded_file.name.split('.')[-1]}"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded_file.getvalue())
            temp_file_path = tmp.name

        # Upload file
        file_ref = client.files.upload(file=temp_file_path)
        
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
client = None
if api_key:
    client = genai.Client(api_key=api_key)

# --- SMART KALKULATION ---
st.title(f"🏗️ {COMPANY_NAME} - Kalkulation")
st.markdown("Ersetzen Sie Nextbau: LV analysieren, Preise kalkulieren, Angebot exportieren.")

if not client:
    st.error("Bitte API Key konfigurieren.")
    st.stop()

# Step 1: Upload
st.subheader("1. Import: Ausschreibung (LV) hochladen")
uploaded_lv = st.file_uploader("Laden Sie das LV (PDF/Docx) der Stadt hoch:", type=['pdf', 'docx', 'txt'])

if "calculation_df" not in st.session_state:
    st.session_state.calculation_df = pd.DataFrame(columns=["pos", "description", "quantity", "unit", "unit_price"])

if uploaded_lv:
    if st.button("🚀 LV Analysieren & Positionen extrahieren"):
        with st.spinner("AI analysiert das Dokument nach 'chatgbt_Rü' Vorgaben..."):
            df_result = extract_data_with_ai(uploaded_lv, client)
            if not df_result.empty:
                st.session_state.calculation_df = df_result
                st.success(f"{len(df_result)} Positionen erfolgreich extrahiert!")

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