# -*- coding: utf-8 -*-
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import time
import gspread.exceptions
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

# === محاولة تحميل أفضل مكتبة متاحة ===
ZXING_OK = False
PYZBAR_OK = False
CV2_OK   = False

try:
    import zxingcpp
    ZXING_OK = True
except ImportError:
    pass

try:
    from pyzbar.pyzbar import decode as pyzbar_decode
    PYZBAR_OK = True
except ImportError:
    pass

try:
    import cv2
    CV2_OK = True
except ImportError:
    pass

# ====== إعدادات الصفحة ======
st.set_page_config(page_title="📦 سكانر الشحنات", page_icon="📦", layout="centered")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;900&display=swap');
* { font-family: 'Cairo', sans-serif !important; direction: rtl; }
.stApp { background: linear-gradient(135deg, #0f0c29, #302b63, #24243e); }
h1, h2, h3 { color: #f0c040 !important; text-align: center; text-shadow: 0 0 20px rgba(240,192,64,0.4); }
.result-found {
    background: linear-gradient(135deg, rgba(0,200,100,0.15), rgba(0,200,100,0.05));
    border: 2px solid rgba(0,200,100,0.6);
    border-radius: 14px; padding: 24px; margin: 12px 0; text-align: center;
}
.result-notfound {
    background: rgba(255,80,80,0.1); border: 1px solid rgba(255,80,80,0.4);
    border-radius: 12px; padding: 16px; text-align: center; color: #ff6b6b;
}
.awb-number { font-size: 2rem; font-weight: 900; color: #f0c040; display: block; }
.date-text  { font-size: 1rem; color: #aaa; display: block; margin-top: 4px; }
.stButton > button {
    background: linear-gradient(135deg, #f0c040, #d4a017) !important;
    color: #1a1a2e !important; font-weight: 700 !important; font-size: 1.1rem !important;
    border: none !important; border-radius: 12px !important; padding: 12px 28px !important;
    width: 100% !important; box-shadow: 0 4px 20px rgba(240,192,64,0.3) !important;
}
.stTextInput > div > div > input {
    background: rgba(255,255,255,0.08) !important;
    border: 1px solid rgba(240,192,64,0.4) !important;
    border-radius: 10px !important; color: #fff !important;
    font-size: 1.3rem !important; text-align: center !important; padding: 12px !important;
}
div[data-testid="metric-container"] {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(240,192,64,0.2);
    border-radius: 12px; padding: 16px;
}
#MainMenu {visibility: hidden;} footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ====== Google Sheets ======
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds_dict = st.secrets["gcp_service_account"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
SHEET_NAME = "Complaints"

@st.cache_resource
def get_shipments_sheet():
    ss = client.open(SHEET_NAME)
    try:
        ws = ss.worksheet("Shipments")
    except gspread.exceptions.WorksheetNotFound:
        ws = ss.add_worksheet(title="Shipments", rows="5000", cols="5")
        ws.append_row(["رقم الشحنة", "التاريخ"])
    return ws

shipments_sheet = get_shipments_sheet()

def safe_append(sheet, row_data, retries=5, delay=1):
    for _ in range(retries):
        try:
            sheet.append_row(row_data)
            return True
        except Exception:
            time.sleep(delay)
    return False

def safe_delete(sheet, row_index, retries=5, delay=1):
    for _ in range(retries):
        try:
            sheet.delete_rows(row_index)
            return True
        except Exception:
            time.sleep(delay)
    return False

@st.cache_data(ttl=30)
def load_shipments():
    try:
        return shipments_sheet.get_all_values()
    except Exception:
        return []

# ====== معالجة الصور ======
def make_variants(image: Image.Image):
    """يولّد نسخاً محسّنة من الصورة لزيادة فرص القراءة"""
    variants = []
    orig = image.convert("RGB")
    w, h = orig.size

    # --- نسخ بأحجام مختلفة ---
    for scale in [1.0, 1.5, 2.0, 3.0]:
        resized = orig.resize((int(w*scale), int(h*scale)), Image.LANCZOS)
        variants.append(resized)

    # --- grayscale محسّن ---
    gray = image.convert("L")
    for contrast_val in [2.0, 3.0]:
        c = ImageEnhance.Contrast(gray).enhance(contrast_val)
        s = ImageEnhance.Sharpness(c).enhance(3.0)
        variants.append(s.convert("RGB"))
        # مكبّر أيضاً
        big = s.resize((w*2, h*2), Image.LANCZOS)
        variants.append(big.convert("RGB"))

    # --- unsharp mask (يوضّح حواف الباركود) ---
    for radius in [1, 2]:
        blurred = orig.filter(ImageFilter.GaussianBlur(radius=radius))
        arr_orig = np.array(orig, dtype=np.float32)
        arr_blur = np.array(blurred, dtype=np.float32)
        sharpened = np.clip(arr_orig + 1.5*(arr_orig - arr_blur), 0, 255).astype(np.uint8)
        variants.append(Image.fromarray(sharpened))

    return variants

def try_zxing(img: Image.Image):
    if not ZXING_OK:
        return None
    try:
        arr = np.array(img.convert("RGB"))
        results = zxingcpp.read_barcodes(arr)
        if results:
            return results[0].text
    except Exception:
        pass
    return None

def try_pyzbar(img: Image.Image):
    if not PYZBAR_OK:
        return None
    try:
        results = pyzbar_decode(img)
        if results:
            return results[0].data.decode("utf-8")
    except Exception:
        pass
    return None

def try_opencv(img: Image.Image):
    if not CV2_OK:
        return None
    try:
        arr  = np.array(img.convert("RGB"))
        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)

        # QRCodeDetector
        data, _, _ = cv2.QRCodeDetector().detectAndDecode(gray)
        if data:
            return data

        # adaptive threshold → pyzbar
        for block in [11, 21, 31]:
            thresh = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, block, 2
            )
            r = try_pyzbar(Image.fromarray(thresh))
            if r:
                return r

        # otsu → pyzbar
        _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        r = try_pyzbar(Image.fromarray(otsu))
        if r:
            return r

        # CLAHE (تحسين التباين المحلي) → pyzbar
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        cl    = clahe.apply(gray)
        r = try_pyzbar(Image.fromarray(cl))
        if r:
            return r

    except Exception:
        pass
    return None

def decode_barcode(image: Image.Image):
    """يجرب كل المكتبات على كل الـ variants"""
    variants = make_variants(image)
    for v in variants:
        for fn in [try_zxing, try_pyzbar, try_opencv]:
            r = fn(v)
            if r and r.strip():
                return r.strip()
    return None

# ====== عرض النتيجة ======
def show_result(awb, data):
    found = [row for row in data[1:] if len(row) > 0 and str(row[0]).strip() == awb.strip()]
    if found:
        date = found[0][1] if len(found[0]) > 1 else ""
        st.markdown(f"""
        <div class="result-found">
            <span style="font-size:2.5rem;">✅</span>
            <span class="awb-number">{awb}</span>
            <span class="date-text">📅 تاريخ التسجيل: {date}</span>
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="result-notfound">
            ⚠️ الشحنة <strong>{awb}</strong> غير موجودة في السجل
        </div>""", unsafe_allow_html=True)

# ====== الواجهة ======
st.markdown("<h1>📦 سكانر الشحنات</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center; color:#aaa; margin-top:-12px;'>تسجيل ومتابعة أرقام الشحنات الصادرة</p>", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["📷 سكان", "📋 القائمة"])

with tab1:
    st.markdown("### 📷 التقاط صورة الباركود")
    st.markdown("""
    <div style="background:rgba(240,192,64,0.1); border:1px solid rgba(240,192,64,0.3);
        border-radius:10px; padding:12px; text-align:center; color:#f0c040; margin-bottom:12px; font-size:0.95rem;">
        💡 <strong>للحصول على أفضل نتيجة:</strong><br>
        وجّه الكاميرا بحيث يملأ الباركود معظم الإطار
    </div>
    """, unsafe_allow_html=True)

    camera_image = st.camera_input("📸", label_visibility="collapsed")

    if camera_image:
        image = Image.open(camera_image)
        with st.spinner("🔍 جار قراءة الباركود..."):
            result = decode_barcode(image)

        if result:
            st.success(f"✅ **{result}**")
            data = load_shipments()
            show_result(result, data)
        else:
            st.warning("⚠️ لم يتم التعرف - حاول مرة أخرى")

    st.markdown("---")
    st.markdown("### 🔍 بحث يدوي")
    search_awb = st.text_input("رقم الشحنة", placeholder="اكتب رقم الشحنة...", label_visibility="collapsed")
    if search_awb.strip():
        data = load_shipments()
        show_result(search_awb.strip(), data)

with tab2:
    st.markdown("### 📋 جميع الشحنات المسجلة")
    data = load_shipments()
    if len(data) > 1:
        rows = data[1:]
        st.metric("📦 إجمالي الشحنات", len(rows))
        for idx, row in enumerate(reversed(rows[:100])):
            awb  = row[0] if len(row) > 0 else ""
            date = row[1] if len(row) > 1 else ""
            real_row_index = len(rows) - idx + 1
            with st.expander(f"📦 {awb}  |  📅 {date}"):
                col_a, col_b = st.columns([3, 1])
                with col_a:
                    st.write(f"**رقم الشحنة:** {awb}")
                    st.write(f"**التاريخ:** {date}")
                with col_b:
                    if st.button("🗑️ حذف", key=f"del_{awb}_{idx}"):
                        if safe_delete(shipments_sheet, real_row_index):
                            st.cache_data.clear()
                            st.success("✅ تم الحذف")
                            st.rerun()
    else:
        st.info("لا توجد شحنات مسجلة بعد.")

st.markdown("---")
st.caption("📦 سكانر الشحنات | يتصل بـ Google Sheets تلقائياً")
