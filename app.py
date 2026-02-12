import streamlit as st
from PIL import Image
from streamlit_drawable_canvas import st_canvas
from io import BytesIO
import base64
import requests
import numpy as np
from datetime import datetime
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# --- CONFIGURATION ---
ADMIN_FOLDER_ID = "1Me5THau4ibDuhuHfk6t3WbEZQNuQ_TZx" 
GAS_URL = st.secrets["gas"]["upload_url"]
GAS_KEY = st.secrets["gas"]["api_key"]
FONT_PATH = "assets/font_CH.ttf"
TEMPLATE_PDF = "assets/template.pdf"

st.set_page_config(page_title="TriNetX Signer", page_icon="✍️", layout="centered")

# --- FUNCTIONS ---
def display_pdf(file_path):
    """Displays the PDF in an iframe for PC users."""
    with open(file_path, "rb") as f:
        base64_pdf = base64.b64encode(f.read()).decode('utf-8')
    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600" type="application/pdf"></iframe>'
    st.markdown(pdf_display, unsafe_allow_html=True)

def create_overlay(name, sig_bytes):
    packet = BytesIO()
    can = canvas.Canvas(packet, pagesize=(595.27, 841.89)) # A4 Size
    try:
        pdfmetrics.registerFont(TTFont('ChineseFont', FONT_PATH))
        can.setFont('ChineseFont', 16)
    except:
        can.setFont("Helvetica", 16)
    
    # Adjust coordinates for Page 3 (X, Y from bottom-left)
    # Right side: X=350~400
    can.drawString(350, 230, f"立約人：{name}")
    can.drawString(350, 205, f"日期：{datetime.now().strftime('%Y/%m/%d')}")
    
    sig_img = Image.open(BytesIO(sig_bytes))
    can.drawInlineImage(sig_img, 350, 130, width=150, height=70)
    can.save()
    packet.seek(0)
    return packet

def generate_final_pdf(name, sig_bytes):
    existing_pdf = PdfReader(open(TEMPLATE_PDF, "rb"))
    output = PdfWriter()
    overlay_pdf = PdfReader(create_overlay(name, sig_bytes))
    overlay_page = overlay_pdf.pages[0]
    
    for i in range(len(existing_pdf.pages)):
        page = existing_pdf.pages[i]
        if i == 2: # Page 3
            page.merge_page(overlay_page)
        output.add_page(page)
    
    pdf_out = BytesIO()
    output.write(pdf_out)
    return pdf_out.getvalue()

# --- UI ---
st.title("TriNetX 資料庫使用管理辦法")
st.caption("線上簽署系統 (V2.1)")

# 📄 PDF VIEWER
st.write("### 📄 請閱讀下方文件內容")
try:
    display_pdf(TEMPLATE_PDF)
except Exception as e:
    st.error(f"無法載入預覽: {e}")

st.divider()

# --- INPUTS ---
col1, col2 = st.columns(2)
with col1:
    full_name = st.text_input("立約人姓名 (Full Name)", placeholder="請輸入姓名")
with col2:
    agree = st.checkbox("我已詳細閱讀並同意上述規定")

st.write("**立約人簽署 (Signature):**")
canvas_result = st_canvas(
    fill_color="white", stroke_width=4, stroke_color="black",
    background_color="#FFFFFF", height=200, width=400, key="agreement_sig"
)

if st.button("確認並簽署 (Confirm & Sign)", type="primary", use_container_width=True, disabled=not (full_name and agree)):
    if canvas_result.image_data is not None and np.std(canvas_result.image_data) > 1:
        with st.spinner("⏳ 正在產生 PDF 並同步至雲端..."):
            try:
                # 1. Image
                img = Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')
                buf_sig = BytesIO()
                img.save(buf_sig, format="PNG")
                
                # 2. PDF
                final_pdf = generate_final_pdf(full_name, buf_sig.getvalue())
                b64_pdf = base64.b64encode(final_pdf).decode("utf-8")
                
                # 3. Request
                fname = f"{datetime.now().strftime('%Y%m%d')}_{full_name}.pdf"
                payload = {
                    "action": "upload",
                    "api_key": GAS_KEY,
                    "folderId": ADMIN_FOLDER_ID,
                    "filename": fname,
                    "pdf_blob": b64_pdf
                }
                
                # Use json=payload to ensure correct content-type
                r = requests.post(GAS_URL, json=payload, timeout=60)
                
                if r.status_code == 200:
                    res = r.json()
                    if res.get("ok"):
                        st.success("🎉 簽署成功！文件已儲存至管理者資料夾。")
                        st.balloons()
                        st.download_button("📥 下載您的副本 (Download Your Copy)", final_pdf, fname, "application/pdf")
                    else:
                        st.error(f"❌ 雲端錯誤: {res.get('error')}")
                else:
                    st.error(f"❌ 伺服器無回應 ({r.status_code})")
                    
            except Exception as e:
                st.error(f"❌ 系統錯誤: {str(e)}")
    else:
        st.warning("⚠️ 請先於白色區域內簽名。")
