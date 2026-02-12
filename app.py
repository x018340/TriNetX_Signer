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
def create_overlay(name, sig_bytes):
    packet = BytesIO()
    can = canvas.Canvas(packet, pagesize=(595.27, 841.89))
    try:
        pdfmetrics.registerFont(TTFont('ChineseFont', FONT_PATH))
        can.setFont('ChineseFont', 16)
    except:
        can.setFont("Helvetica", 16)
    
    # Text Placement
    can.drawString(350, 230, f"立約人：{name}")
    can.drawString(350, 205, f"日期：{datetime.now().strftime('%Y/%m/%d')}")
    
    # --- FIX 1: Process Signature to remove black box ---
    sig_img = Image.open(BytesIO(sig_bytes)).convert("RGBA")
    # Create a white background image
    white_bg = Image.new("RGBA", sig_img.size, "WHITE")
    # Composite signature over white
    final_sig = Image.alpha_composite(white_bg, sig_img).convert("RGB")
    
    # Place Signature
    can.drawInlineImage(final_sig, 350, 130, width=150, height=70)
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
st.title("新光醫院TriNetX資料庫使用管理辦法同意書")
st.caption("線上簽署系統")

# --- FIX 2: Better Image-Based PDF Preview (Bypasses Chrome Block) ---
st.write("請閱覽合約條款")
with st.container(height=500, border=True):
    # We display images sequentially. 
    # If the images aren't in the repo yet, it shows the error message.
    pages = ["assets/page1.png", "assets/page2.png", "assets/page3.png"]
    missing_pages = False
    for p in pages:
        try:
            st.image(p, use_container_width=True)
        except:
            missing_pages = True
    
    if missing_pages:
        st.warning("⚠️ 預覽圖片載入失敗。請確認 assets 資料夾內是否有 page1.png, page2.png, page3.png。")
        with open(TEMPLATE_PDF, "rb") as f:
            st.download_button("📥 下載 PDF 檔案閱讀", f, "Agreement.pdf")

st.divider()

# --- INPUTS ---
col1, col2 = st.columns(2)
with col1:
    full_name = st.text_input("立約人姓名", placeholder="請輸入中文姓名")
with col2:
    agree = st.checkbox("我已詳細閱讀並同意上述規定")

st.write("**立約人簽署 (Signature):**")
canvas_result = st_canvas(
    fill_color="white", stroke_width=4, stroke_color="black",
    background_color="#FFFFFF", height=200, width=400, key="agreement_sig"
)

if st.button("確認並簽署 (Confirm & Sign)", type="primary", use_container_width=True, disabled=not (full_name and agree)):
    if canvas_result.image_data is not None and np.std(canvas_result.image_data) > 1:
        with st.spinner("⏳ 正在產生文件並儲存..."):
            try:
                # 1. Process Sig
                img = Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')
                buf_sig = BytesIO()
                img.save(buf_sig, format="PNG")
                
                # 2. Build PDF
                final_pdf = generate_final_pdf(full_name, buf_sig.getvalue())
                b64_pdf = base64.b64encode(final_pdf).decode("utf-8")
                
                # 3. Upload via GAS
                fname = f"{datetime.now().strftime('%Y%m%d')}_{full_name}.pdf"
                payload = {
                    "api_key": GAS_KEY,
                    "folderId": ADMIN_FOLDER_ID,
                    "filename": fname,
                    "pdf_blob": b64_pdf
                }
                
                r = requests.post(GAS_URL, json=payload, timeout=60)
                
                if r.status_code == 200 and r.json().get("ok"):
                    st.success("簽署成功！文件已存檔。請按上一頁返回表單")
                    st.download_button("📥 下載副本", final_pdf, fname, "application/pdf")
                else:
                    st.error("❌ 上傳失敗，請檢查網路連線或聯繫管理員。")
                    
            except Exception as e:
                st.error(f"❌ 系統錯誤: {str(e)}")
    else:
        st.warning("⚠️ 請先於區域內簽名。")
