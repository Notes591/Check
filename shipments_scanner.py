# -*- coding: utf-8 -*-
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import time
import gspread.exceptions

# ====== إعدادات الصفحة ======
st.set_page_config(
    page_title="📦 سكانر الشحنات",
    page_icon="📦",
    layout="centered"
)

# ====== CSS مخصص ======
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;900&display=swap');

* { font-family: 'Cairo', sans-serif !important; direction: rtl; }

.main { background: linear-gradient(135deg, #0f0c29, #302b63, #24243e); min-height: 100vh; }

.stApp { background: linear-gradient(135deg, #0f0c29, #302b63, #24243e); }

h1, h2, h3 {
    color: #f0c040 !important;
    text-align: center;
    text-shadow: 0 0 20px rgba(240,192,64,0.4);
}

.scan-box {
    background: rgba(255,255,255,0.05);
    border: 2px solid rgba(240,192,64,0.3);
    border-radius: 16px;
    padding: 24px;
    margin: 16px 0;
    backdrop-filter: blur(10px);
}

.result-card {
    background: linear-gradient(135deg, rgba(240,192,64,0.15), rgba(240,192,64,0.05));
    border: 1px solid rgba(240,192,64,0.5);
    border-radius: 12px;
    padding: 20px;
    margin: 12px 0;
    text-align: center;
}

.result-card .awb-number {
    font-size: 2rem;
    font-weight: 900;
    color: #f0c040;
    display: block;
}

.result-card .date-text {
    font-size: 1rem;
    color: #aaa;
    display: block;
    margin-top: 4px;
}

.stButton > button {
    background: linear-gradient(135deg, #f0c040, #d4a017) !important;
    color: #1a1a2e !important;
    font-weight: 700 !important;
    font-size: 1.1rem !important;
    border: none !important;
    border-radius: 12px !important;
    padding: 12px 28px !important;
    width: 100% !important;
    box-shadow: 0 4px 20px rgba(240,192,64,0.3) !important;
    transition: all 0.2s !important;
}

.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 28px rgba(240,192,64,0.5) !important;
}

.stTextInput > div > div > input {
    background: rgba(255,255,255,0.08) !important;
    border: 1px solid rgba(240,192,64,0.4) !important;
    border-radius: 10px !important;
    color: #fff !important;
    font-size: 1.2rem !important;
    text-align: center !important;
    padding: 12px !important;
}

.stDataFrame { border-radius: 12px; overflow: hidden; }

div[data-testid="metric-container"] {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(240,192,64,0.2);
    border-radius: 12px;
    padding: 16px;
}

.scanner-btn-wrapper {
    display: flex;
    justify-content: center;
    margin: 20px 0;
}

/* Hide streamlit branding */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
</style>

<script>
// ===== HTML5 QR/Barcode Scanner using jsQR =====
function initScanner() {
    const modal = document.getElementById('scannerModal');
    if (!modal) return;
    modal.style.display = 'flex';

    const video = document.getElementById('scanVideo');
    const canvas = document.getElementById('scanCanvas');
    const ctx = canvas.getContext('2d');
    const statusEl = document.getElementById('scanStatus');
    let stream = null;

    // Load jsQR
    if (!window.jsQR) {
        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.min.js';
        script.onload = () => startCamera();
        document.head.appendChild(script);
    } else {
        startCamera();
    }

    function startCamera() {
        navigator.mediaDevices.getUserMedia({
            video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } }
        }).then(s => {
            stream = s;
            video.srcObject = s;
            video.play();
            requestAnimationFrame(scanFrame);
            statusEl.textContent = '🎯 وجّه الكاميرا نحو الباركود';
        }).catch(err => {
            statusEl.textContent = '❌ تعذر فتح الكاميرا: ' + err.message;
        });
    }

    function scanFrame() {
        if (!stream) return;
        if (video.readyState === video.HAVE_ENOUGH_DATA) {
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            ctx.drawImage(video, 0, 0);
            const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
            const code = window.jsQR ? jsQR(imageData.data, canvas.width, canvas.height) : null;
            if (code) {
                stopCamera();
                const result = code.data;
                statusEl.textContent = '✅ تم الكشف: ' + result;
                // Send to streamlit via query param trick
                const input = document.querySelector('input[aria-label="AWB scan input"]');
                if (input) {
                    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    nativeInputValueSetter.call(input, result);
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                    setTimeout(() => closeScanner(), 800);
                } else {
                    setTimeout(() => closeScanner(), 1200);
                }
                return;
            }
        }
        requestAnimationFrame(scanFrame);
    }

    function stopCamera() {
        if (stream) {
            stream.getTracks().forEach(t => t.stop());
            stream = null;
        }
    }

    window._stopScannerCamera = stopCamera;
}

function closeScanner() {
    const modal = document.getElementById('scannerModal');
    if (modal) modal.style.display = 'none';
    if (window._stopScannerCamera) window._stopScannerCamera();
}
</script>

<!-- Scanner Modal -->
<div id="scannerModal" style="
    display:none; position:fixed; top:0; left:0; width:100%; height:100%;
    background:rgba(0,0,0,0.92); z-index:9999; flex-direction:column;
    align-items:center; justify-content:center; gap:16px;
">
    <div style="color:#f0c040; font-size:1.4rem; font-family:Cairo,sans-serif; font-weight:700;">
        📦 سكان الشحنة
    </div>
    <div style="position:relative; border-radius:16px; overflow:hidden; max-width:360px; width:90%;">
        <video id="scanVideo" style="width:100%; border-radius:16px; display:block;" autoplay muted playsinline></video>
        <canvas id="scanCanvas" style="display:none;"></canvas>
        <!-- Overlay crosshair -->
        <div style="position:absolute; top:50%; left:50%; transform:translate(-50%,-50%);
            width:200px; height:100px; border:2px solid #f0c040;
            border-radius:8px; box-shadow: 0 0 0 2000px rgba(0,0,0,0.4);">
        </div>
    </div>
    <div id="scanStatus" style="color:#ccc; font-family:Cairo,sans-serif; font-size:0.95rem; text-align:center; padding:0 20px;">
        جار تحميل الكاميرا...
    </div>
    <button onclick="closeScanner()" style="
        background:#f0c040; color:#1a1a2e; border:none; border-radius:10px;
        padding:10px 32px; font-size:1rem; font-family:Cairo,sans-serif;
        font-weight:700; cursor:pointer;
    ">❌ إغلاق</button>
</div>
""", unsafe_allow_html=True)

# ====== الاتصال بجوجل شيت ======
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
        except gspread.exceptions.APIError:
            time.sleep(delay)
        except Exception:
            time.sleep(delay)
    return False

def safe_delete(sheet, row_index, retries=5, delay=1):
    for _ in range(retries):
        try:
            sheet.delete_rows(row_index)
            return True
        except gspread.exceptions.APIError:
            time.sleep(delay)
        except Exception:
            time.sleep(delay)
    return False

@st.cache_data(ttl=30)
def load_shipments():
    try:
        data = shipments_sheet.get_all_values()
        return data
    except Exception:
        return []

# ====== الواجهة ======
st.markdown("<h1>📦 سكانر الشحنات</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center; color:#aaa; margin-top:-12px;'>تسجيل ومتابعة أرقام الشحنات الصادرة</p>", unsafe_allow_html=True)

# زر سكانر الكاميرا
st.markdown("""
<div class='scanner-btn-wrapper'>
    <button onclick="initScanner()" style="
        background: linear-gradient(135deg,#f0c040,#d4a017);
        color:#1a1a2e; font-weight:800; font-size:1.2rem;
        border:none; border-radius:14px; padding:14px 40px;
        cursor:pointer; font-family:Cairo,sans-serif;
        box-shadow: 0 4px 20px rgba(240,192,64,0.4);
    ">📷 سكان باركود</button>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

# ====== بحث ======
st.markdown("### 🔍 بحث عن شحنة")
search_awb = st.text_input("أدخل رقم الشحنة للبحث", key="search_box", placeholder="مثال: 123456789")

if search_awb.strip():
    data = load_shipments()
    results = [row for row in data[1:] if len(row) > 0 and str(row[0]).strip() == search_awb.strip()]
    if results:
        for r in results:
            awb = r[0] if len(r) > 0 else ""
            date = r[1] if len(r) > 1 else ""
            st.markdown(f"""
            <div class="result-card">
                <span class="awb-number">✅ {awb}</span>
                <span class="date-text">📅 تاريخ التسجيل: {date}</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="background:rgba(255,80,80,0.1); border:1px solid rgba(255,80,80,0.4);
            border-radius:12px; padding:16px; text-align:center; color:#ff6b6b;">
            ⚠️ لم يتم العثور على الشحنة: <strong>{search_awb}</strong>
        </div>
        """, unsafe_allow_html=True)

st.markdown("---")

# ====== إضافة شحنة يدوياً ======
st.markdown("### ➕ إضافة شحنة")
col1, col2 = st.columns([3, 1])
with col1:
    new_awb = st.text_input("رقم الشحنة", key="AWB scan input", placeholder="سكان أو اكتب يدوياً", label_visibility="collapsed")
with col2:
    add_btn = st.button("💾 إضافة")

if add_btn:
    if new_awb.strip():
        # فحص تكرار
        data = load_shipments()
        existing = [row[0] for row in data[1:] if len(row) > 0]
        if new_awb.strip() in existing:
            st.warning(f"⚠️ الشحنة {new_awb} مسجلة مسبقاً")
        else:
            date_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if safe_append(shipments_sheet, [new_awb.strip(), date_now]):
                st.cache_data.clear()
                st.success(f"✅ تم تسجيل الشحنة: {new_awb.strip()}")
                st.balloons()
            else:
                st.error("❌ فشل في التسجيل")
    else:
        st.error("⚠️ أدخل رقم الشحنة")

st.markdown("---")

# ====== عرض جميع الشحنات ======
st.markdown("### 📋 جميع الشحنات المسجلة")

data = load_shipments()
if len(data) > 1:
    rows = data[1:]
    total = len(rows)
    
    col1, col2 = st.columns(2)
    col1.metric("📦 إجمالي الشحنات", total)
    
    # عرض آخر 100 شحنة بترتيب عكسي
    display_rows = list(reversed(rows))[:100]
    
    if "delete_confirm" not in st.session_state:
        st.session_state.delete_confirm = None

    for idx, row in enumerate(display_rows):
        awb = row[0] if len(row) > 0 else ""
        date = row[1] if len(row) > 1 else ""
        
        # الصف الأصلي في الشيت (مقلوب)
        real_row_index = len(rows) - idx + 1  # +1 للهيدر
        
        with st.expander(f"📦 {awb}  |  📅 {date}"):
            col_a, col_b = st.columns(2)
            with col_a:
                st.write(f"**رقم الشحنة:** {awb}")
                st.write(f"**التاريخ:** {date}")
            with col_b:
                if st.button(f"🗑️ حذف", key=f"del_{awb}_{idx}"):
                    if safe_delete(shipments_sheet, real_row_index):
                        st.cache_data.clear()
                        st.success("✅ تم الحذف")
                        st.rerun()
else:
    st.info("لا توجد شحنات مسجلة بعد.")

st.markdown("---")
st.caption("📦 سكانر الشحنات | يتصل بـ Google Sheets تلقائياً")
