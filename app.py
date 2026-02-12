import streamlit as st
from PIL import Image
from streamlit_drawable_canvas import st_canvas
from io import BytesIO
import base64
import requests
from datetime import datetime
import numpy as np
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# --- CONFIGURATION ---
# The Folder ID you provided
ADMIN_FOLDER_ID = "1Me5THau4ibDuhuHfk6t3WbEZQNuQ_TZx" 

# Secrets
GAS_URL = st.secrets["gas"]["upload_url"]
GAS_KEY = st.secrets["gas"]["api_key"]

# Files
FONT_PATH = "assets/font_CH.ttf"
TEMPLATE_PDF = "assets/template.pdf"

st.set_page_config(page_title="TriNetX Agreement Signer", page_icon="✍️", layout="centered")

# --- PDF GENERATION LOGIC ---
def create_overlay(name, sig_bytes):
    packet = BytesIO()
    # A4 Size: 595.27 x 841.89 points
    can = canvas.Canvas(packet, pagesize=(595.27, 841.89))
    
    # Register Font
    try:
        pdfmetrics.registerFont(TTFont('ChineseFont', FONT_PATH))
        can.setFont('ChineseFont', 14)
    except:
        # Fallback if font missing (for debugging)
        can.setFont("Helvetica", 14)
    
    # --- COORDINATES (Page 3, Bottom Right) ---
    # X=Left to Right, Y=Bottom to Top
    
    # 1. Write Name
    can.drawString(380, 215, f"立約人：{name}")
    
    # 2. Write Date
    can.drawString(380, 190, f"日期：{datetime.now().strftime('%Y/%m/%d')}")
    
    # 3. Place Signature Image
    # Adjust X,Y to fit nicely below the text
    sig_img = Image.open(BytesIO(sig_bytes))
    can.drawInlineImage(sig_img, 380, 120, width=120, height=60)
    
    can.save()
    packet.seek(0)
    return packet

def generate_final_pdf(name, sig_bytes):
    # Read the original 3-page PDF
    existing_pdf = PdfReader(open(TEMPLATE_PDF, "rb"))
    output = PdfWriter()
    
    # Create the signature layer (transparent PDF)
    overlay_pdf = PdfReader(create_overlay(name, sig_bytes))
    overlay_page = overlay_pdf.pages[0]
    
    # Loop through all pages
    for i in range(len(existing_pdf.pages)):
        page = existing_pdf.pages[i]
        
        # Merge signature ONLY onto Page 3 (Index 2)
        if i == 2: 
            page.merge_page(overlay_page)
            
        output.add_page(page)
    
    pdf_out = BytesIO()
    output.write(pdf_out)
    return pdf_out.getvalue()

# --- APP UI ---
st.title("TriNetX 資料庫使用管理辦法")
st.caption("線上簽署系統")

st.info("👇 請閱讀文件，並於最下方簽署。")

# 1. Preview the PDF (Optional - helps user read before signing)
# We can display the images of the pages if you saved them as png, 
# or just assume they read the physical copy/link provided in MS Forms.
with st.expander("📄 點擊展開閱讀合約內容 (Preview Document)", expanded=True):
    # Use an iframe to show the PDF if hosted, or just instructions.
    # Since we have the file locally, we can let them download the blank template to read.
    with open(TEMPLATE_PDF, "rb") as f:
        st.download_button("📥 下載完整條款閱讀 (Download Rules)", f, "TriNetX_Rules.pdf")

st.divider()

# 2. Input Section
col1, col2 = st.columns(2)
with col1:
    full_name = st.text_input("立約人姓名 (Full Name)", placeholder="請輸入中文全名")
with col2:
    agree = st.checkbox("我已詳細閱讀並同意「TriNetX 資料庫使用管理辦法」之所有規定")

st.write("**請於下方簽名 (Please Sign Below):**")

# 3. Signature Pad
pad_width = 350 # Mobile friendly default
canvas_result = st_canvas(
    fill_color="white",
    stroke_width=4,
    stroke_color="black",
    background_color="#FFFFFF",
    height=180,
    width=pad_width,
    key="agreement_sig"
)

# 4. Submission Logic
if st.button("確認並簽署 (Confirm & Sign)", type="primary", use_container_width=True, disabled=not (full_name and agree)):
    
    # Check if signed
    if canvas_result.image_data is None or np.std(canvas_result.image_data) < 1:
        st.error("⚠️ 請先在簽名板上簽名 (Please sign first).")
        st.stop()

    with st.spinner("正在製作合約 PDF 並上傳... (Generating & Uploading...)"):
        try:
            # A. Convert Canvas to Bytes
            img = Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')
            buffered_sig = BytesIO()
            img.save(buffered_sig, format="PNG")
            
            # B. Generate PDF
            final_pdf_bytes = generate_final_pdf(full_name, buffered_sig.getvalue())
            
            # C. Upload to Google Drive
            timestamp = datetime.now().strftime('%Y%m%d')
            filename = f"{timestamp}_{full_name}_TriNetX同意書.pdf"
            
            payload = {
                "action": "upload",
                "api_key": GAS_KEY,
                "folderId": ADMIN_FOLDER_ID,
                "filename": filename,
                "mimeType": "application/pdf",
                "data_base_64": base64.b64encode(final_pdf_bytes).decode("utf-8")
            }
            
            r = requests.post(GAS_URL, json=payload, timeout=45) # Longer timeout for PDF upload
            
            if r.json().get("ok"):
                st.success("✅ 簽署成功！(Success)")
                st.balloons()
                
                # D. Backup Download
                st.download_button(
                    label="📥 下載您的簽署副本 (Download Your Copy)",
                    data=final_pdf_bytes,
                    file_name=filename,
                    mime="application/pdf",
                    type="secondary"
                )
                st.info("您現在可以關閉此視窗。")
            else:
                st.error(f"上傳失敗: {r.text}")
                
        except Exception as e:
            st.error(f"系統錯誤: {str(e)}")
