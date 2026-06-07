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

# ====== CSS + Scanner HTML ======
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
.date-text { font-size: 1rem; color: #aaa; display: block; margin-top: 4px; }
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
    font-size: 1.2rem !important; text-align: center !important; padding: 12px !important;
}
div[data-testid="metric-container"] {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(240,192,64,0.2);
    border-radius: 12px; padding: 16px;
}
#MainMenu {visibility: hidden;} footer {visibility: hidden;}
</style>

<!-- ZXing barcode scanner (best mobile support) -->
<script src="https://cdn.jsdelivr.net/npm/@zxing/library@0.19.1/umd/index.min.js"></script>

<div id="scannerModal" style="
    display:none; position:fixed; top:0; left:0; width:100%; height:100%;
    background:rgba(0,0,0,0.95); z-index:9999; flex-direction:column;
    align-items:center; justify-content:center; gap:16px; padding:16px; box-sizing:border-box;
">
    <div style="color:#f0c040; font-size:1.4rem; font-family:Cairo,sans-serif; font-weight:700;">
        📦 سكان الشحنة
    </div>
    <div style="position:relative; width:100%; max-width:400px; border-radius:16px; overflow:hidden; background:#000;">
        <video id="zxingVideo" style="width:100%; display:block;" autoplay muted playsinline></video>
        <div style="position:absolute; top:50%; left:50%; transform:translate(-50%,-50%);
            width:75%; height:35%; border:3px solid #f0c040; border-radius:10px;
            box-shadow: 0 0 0 3000px rgba(0,0,0,0.5);">
            <div style="position:absolute; top:-2px; left:-2px; width:20px; height:20px;
                border-top:4px solid #f0c040; border-left:4px solid #f0c040; border-radius:3px 0 0 0;"></div>
            <div style="position:absolute; top:-2px; right:-2px; width:20px; height:20px;
                border-top:4px solid #f0c040; border-right:4px solid #f0c040; border-radius:0 3px 0 0;"></div>
            <div style="position:absolute; bottom:-2px; left:-2px; width:20px; height:20px;
                border-bottom:4px solid #f0c040; border-left:4px solid #f0c040; border-radius:0 0 0 3px;"></div>
            <div style="position:absolute; bottom:-2px; right:-2px; width:20px; height:20px;
                border-bottom:4px solid #f0c040; border-right:4px solid #f0c040; border-radius:0 0 3px 0;"></div>
        </div>
    </div>
    <div id="scanStatus" style="color:#ccc; font-family:Cairo,sans-serif; font-size:0.95rem; text-align:center;">
        جار تحميل الكاميرا...
    </div>
    <button onclick="closeScanner()" style="
        background:#f0c040; color:#1a1a2e; border:none; border-radius:10px;
        padding:12px 36px; font-size:1rem; font-family:Cairo,sans-serif; font-weight:700; cursor:pointer;
    ">❌ إغلاق</button>
</div>

<script>
let codeReader = null;
let scannerActive = false;

function openScanner() {
    document.getElementById('scannerModal').style.display = 'flex';
    document.getElementById('scanStatus').textContent = 'جار تحميل الكاميرا...';

    try {
        codeReader = new ZXing.BrowserMultiFormatReader();
        scannerActive = true;

        codeReader.listVideoInputDevices().then(videoInputDevices => {
            // prefer back camera on mobile
            let deviceId = undefined;
            for (let d of videoInputDevices) {
                if (d.label.toLowerCase().includes('back') || d.label.toLowerCase().includes('environment')) {
                    deviceId = d.deviceId;
                    break;
                }
            }
            if (!deviceId && videoInputDevices.length > 0) {
                deviceId = videoInputDevices[videoInputDevices.length - 1].deviceId;
            }

            document.getElementById('scanStatus').textContent = '🎯 وجّه الكاميرا نحو الباركود';

            codeReader.decodeFromVideoDevice(deviceId, 'zxingVideo', (result, err) => {
                if (result && scannerActive) {
                    scannerActive = false;
                    const scannedText = result.getText();
                    document.getElementById('scanStatus').textContent = '✅ تم: ' + scannedText;

                    // inject into streamlit search input
                    setTimeout(() => {
                        const inputs = document.querySelectorAll('input[type="text"]');
                        for (let inp of inputs) {
                            if (inp.closest('[data-testid]') || inp.value !== undefined) {
                                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                                setter.call(inp, scannedText);
                                inp.dispatchEvent(new Event('input', { bubbles: true }));
                                inp.dispatchEvent(new Event('change', { bubbles: true }));
                                break;
                            }
                        }
                        setTimeout(() => closeScanner(), 600);
                    }, 400);
                }
            });
        }).catch(err => {
            document.getElementById('scanStatus').textContent = '❌ خطأ: ' + err.message;
        });
    } catch(e) {
        document.getElementById('scanStatus').textContent = '❌ ZXing غير متاح: ' + e.message;
    }
}

function closeScanner() {
    scannerActive = false;
    if (codeReader) {
        try { codeReader.reset(); } catch(e) {}
        codeReader = null;
    }
    document.getElementById('scannerModal').style.display = 'none';
}
</script>
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
        return shipments_sheet.get_all_values()
    except Exception:
        return []

# ====== الواجهة ======
st.markdown("<h1>📦 سكانر الشحنات</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center; color:#aaa; margin-top:-12px;'>تسجيل ومتابعة أرقام الشحنات الصادرة</p>", unsafe_allow_html=True)

# ====== زر السكانر ======
st.markdown("""
<div style="display:flex; justify-content:center; margin:20px 0;">
    <button onclick="openScanner()" style="
        background: linear-gradient(135deg,#f0c040,#d4a017);
        color:#1a1a2e; font-weight:800; font-size:1.3rem;
        border:none; border-radius:16px; padding:16px 48px;
        cursor:pointer; font-family:Cairo,sans-serif;
        box-shadow: 0 4px 24px rgba(240,192,64,0.5);
        letter-spacing:1px;
    ">📷 سكان باركود</button>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

# ====== بحث ======
st.markdown("### 🔍 بحث عن شحنة")
search_awb = st.text_input(
    "أدخل رقم الشحنة",
    key="search_box",
    placeholder="اكتب أو استخدم السكانر أعلاه...",
    label_visibility="collapsed"
)

if search_awb.strip():
    data = load_shipments()
    results = [row for row in data[1:] if len(row) > 0 and str(row[0]).strip() == search_awb.strip()]
    if results:
        for r in results:
            awb = r[0] if len(r) > 0 else ""
            date = r[1] if len(r) > 1 else ""
            st.markdown(f"""
            <div class="result-found">
                <span style="font-size:2.5rem;">✅</span>
                <span class="awb-number">{awb}</span>
                <span class="date-text">📅 تاريخ التسجيل: {date}</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="result-notfound">
            ⚠️ لم يتم العثور على الشحنة: <strong>{search_awb}</strong>
        </div>
        """, unsafe_allow_html=True)

st.markdown("---")

# ====== عرض جميع الشحنات ======
st.markdown("### 📋 جميع الشحنات المسجلة")

data = load_shipments()
if len(data) > 1:
    rows = data[1:]
    total = len(rows)
    st.metric("📦 إجمالي الشحنات", total)

    display_rows = list(reversed(rows))[:100]

    for idx, row in enumerate(display_rows):
        awb = row[0] if len(row) > 0 else ""
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
