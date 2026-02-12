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

st.set_page_config(page_title="TriNetX Signer", page_icon="✍️")

# --- PDF GENERATION ---
def create_overlay(name, sig_bytes):
    packet = BytesIO()
    can = canvas.Canvas(packet, pagesize=(595.27, 841.89))
    try:
        pdfmetrics.registerFont(TTFont('ChineseFont', FONT_PATH))
        can.setFont('ChineseFont', 14)
    except:
        can.setFont("Helvetica", 14)
    
    # Coordinates for Page 3
    can.drawString(380, 215, f"立約人：{name}")
    can.drawString(380, 195, f"日期：{datetime.now().strftime('%Y/%m/%d')}")
    
    sig_img = Image.open(BytesIO(sig_bytes))
    can.drawInlineImage(sig_img, 380, 120, width=120, height=60)
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
st.subheader("線上簽署系統")

# 📄 PREVIEW SECTION (The fix for reading)
st.write("### 📄 請閱讀合約內容 (Contract Review)")
with st.container(height=500, border=True):
    try:
        st.image("assets/page1.png", caption="Page 1", use_container_width=True)
        st.image("assets/page2.png", caption="Page 2", use_container_width=True)
        st.image("assets/page3.png", caption="Page 3", use_container_width=True)
    except:
        st.warning("⚠️ 無法載入預覽圖片，請下載下方 PDF 閱讀。")
        with open(TEMPLATE_PDF, "rb") as f:
            st.download_button("📥 下載完整條款 (Download PDF)", f, "TriNetX_Rules.pdf")

st.divider()

# --- INPUT SECTION ---
full_name = st.text_input("立約人姓名 (Full Name)", placeholder="請輸入中文全名")
agree = st.checkbox("我已詳細閱讀並同意上述「TriNetX 資料庫使用管理辦法」之所有規定")

st.write("**請於下方灰色區域簽名 (Please Sign Below):**")
canvas_result = st_canvas(
    fill_color="white", stroke_width=4, stroke_color="black",
    background_color="#FFFFFF", height=180, width=350, key="agreement_sig"
)

if st.button("確認並簽署 (Confirm & Sign)", type="primary", use_container_width=True, disabled=not (full_name and agree)):
    if canvas_result.image_data is not None and np.std(canvas_result.image_data) > 1:
        with st.spinner("正在處理上傳..."):
            try:
                # 1. Process Signature
                img = Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')
                buffered_sig = BytesIO()
                img.save(buffered_sig, format="PNG")
                
                # 2. Build PDF
                final_pdf_bytes = generate_final_pdf(full_name, buffered_sig.getvalue())
                
                # 3. Base64 for upload
                pdf_b64 = base64.b64encode(final_pdf_bytes).decode("utf-8")
                
                # 4. Upload to GAS
                filename = f"{datetime.now().strftime('%Y%m%d')}_{full_name}.pdf"
                payload = {
                    "action": "upload",
                    "api_key": GAS_KEY,
                    "folderId": ADMIN_FOLDER_ID,
                    "filename": filename,
                    "pdf_blob": pdf_b64  # Key name simplified
                }
                
                r = requests.post(GAS_URL, json=payload, timeout=45)
                res_data = r.json()
                
                if res_data.get("ok"):
                    st.success("✅ 簽署完成！文件已存檔。")
                    st.balloons()
                    st.download_button("📥 下載您的副本 (Download Your Copy)", final_pdf_bytes, filename, "application/pdf")
                else:
                    st.error(f"❌ 上傳失敗: {res_data.get('error')}")
            except Exception as e:
                st.error(f"❌ 系統錯誤: {str(e)}")
    else:
        st.warning("⚠️ 請務必在簽名板上簽署。")
