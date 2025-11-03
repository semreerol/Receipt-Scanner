import os
import re
import uvicorn  
from fastapi import FastAPI, UploadFile, File, HTTPException  
from doctr.io import DocumentFile  
from doctr.models import ocr_predictor
import io 
from PIL import Image
import numpy as np

os.environ["USE_TF"] = "1" 

def classify_receipt(text):
   
    text_upper = text.upper()
    
    KEYWORDS = {
        "BENZİN": [
            ("PETROL OFİSİ", 3), ("OPET", 3), ("SHELL", 3), ("TOTAL", 3), ("BP", 3), 
            ("AKARYAKIT", 3), ("MOTORİN", 2), ("BENZİN", 2), ("LPG", 2), ("POMPA", 1), ("LİTRE", 1)
        ],
        "MARKET": [
            ("MİGROS", 3), ("CARREFOUR", 3), ("BİM", 3), ("A101", 3), ("ŞOK", 3), 
            ("MARKET", 1), ("GIDA", 1), ("SEBZE", 1), ("MEYVE", 1), ("KASİYER", 1), ("TOPKDV", 1), ("FİŞ NO", 1)
        ],
        "YEMEK": [
            ("RESTAURANT", 3), ("CAFE", 3), ("LOKANTA", 3), ("ADİSYON", 2), ("GARSON", 1), 
            ("YEMEK SEPETİ", 3), ("GETİR YEMEK", 3), ("KEBAP", 2), ("BURGER", 2), ("MENÜ", 1)
        ]
    }
    
    scores = {"BENZİN": 0, "MARKET": 0, "YEMEK": 0}
    
    for category, keywords_with_scores in KEYWORDS.items():
        for keyword, score in keywords_with_scores:
            if keyword in text_upper:
                scores[category] += score
                
    if all(score == 0 for score in scores.values()):
        return "DİĞER"
    
    best_category = max(scores, key=scores.get)
    return best_category

def find_pattern(text, patterns, default=None):

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            if match.groups():
                return match.group(1).strip()
            else:
                return match.group(0).strip()
    return default

def get_company_name(text):
    
    lines = text.strip().split('\n')
    if len(lines) == 0:
        return None
    
    firma_adi = lines[0] 
    if len(lines) > 1 and lines[1].strip(): 
        firma_adi += " " + lines[1].strip() 
    return firma_adi

def extract_line_items(text_lines):
    product_lines = []
    
    SUMMARY_KEYWORDS = [
        "TOPLAM", "TOPKDV", "ARA TOPLAM", "NAKİT", 
        "KREDİ KARTI", "BANKA", "ÖDEME", "FİŞ TOPLAMI",
        "MALİ BİLGİLER"
    ]
    
    start_processing = False
    START_KEYWORDS = ["TARİH", "SAAT", "FİŞ NO", "ÜRÜN ADI", "AÇIKLAMA", "ADİSYON"]

    for line in text_lines:
        line_upper = line.upper().strip()
        
        if not start_processing:
            if any(keyword in line_upper for keyword in START_KEYWORDS):
                start_processing = True
            continue 
        
        if any(keyword in line_upper for keyword in SUMMARY_KEYWORDS):
            break 
        
        match = re.search(r'(.+?)\s+[*F]?\s*([\d,.]+)$', line.strip())
        
        if match:
            product_name = match.group(1).strip()
            price = match.group(2).strip()
            
            product_name = re.sub(r'^\d+\s*[xX]\s*', '', product_name) 

            if len(product_name) > 2 and "KDV" not in product_name.upper() and "İNDİRİM" not in product_name.upper():
                product_lines.append(f"{product_name} | Fiyat: {price}")
                
    if not product_lines:
        return "Ürün listesi çıkarılamadı."
    return "\n".join(product_lines)

def extract_benzin_details(text):
    """Benzin fişi metninden bilgileri regex ile çıkarır."""
    details = {
        "Kategori": "Benzin Fişi",
        "Firma Adı": get_company_name(text),
        "Tarih": find_pattern(text, [
            r"TAR[İI]H\s*[:]?\s*(\d{2}[ -/]\d{2}[ -/]\d{4})",  
            r"^\s*(\d{2}[ -/]\d{2}[ -/]\d{4})\s*$"             
        ]),
        "FişNo": find_pattern(text, [r"F[İI]S NO:\s*(\S+)"]),
        "Plaka": find_pattern(text, [r"(\d{2}\s?[A-Z]{1,3}\s?\d{2,4})"]),
        "Alınan Yakıt Miktarı": find_pattern(text, [r"(\d+,\d{3})\s*(?:IT|LT)"]),
        "Toplam KDV": find_pattern(text, [r"TOPKDV\s*[\n\r]*\*?([\d.,]+)"]),
        "Toplam Tutar": find_pattern(text, [r"TOPLAM\s*[\n\r]*\*?([\d.,]+)"]),
        "Banka Adı": find_pattern(text, [r"(İ?S\s*BANKASI)", r"(GARANTİ)", r"(YAPI\s*KREDİ)", r"(AKBANK)"])
    }
    return details

def extract_yemek_details(text):
    """Yemek fişi metninden bilgileri regex ile çıkarır."""
    text_lines = text.strip().split('\n')
    details = {
        "Kategori": "Yemek Fişi",
        "Restoran İsmi": get_company_name(text),
        "Tarih": find_pattern(text, [
            r"TAR[İI]H\s*[:]?\s*(\d{2}[ -/]\d{2}[ -/]\d{4})", 
            r"^\s*(\d{2}[ -/]\d{2}[ -/]\d{4})\s*$"             
        ]),
        "Fiş Numarası": find_pattern(text, [r"F[İI]S NO:\s*(\S+)", r"AD[İI]SYON NO:\s*(\S+)"]),
        "Sipariş Kalemleri": extract_line_items(text_lines), 
        "Toplam KDV": find_pattern(text, [r"TOPKDV\s*[\n\r]*\*?([\d.,]+)", r"ARA TOPLAM\s*[\n\r]*\*?([\d.,]+)"]),
        "Toplam Tutar": find_pattern(text, [r"TOPLAM\s*[\n\r]*\*?([\d.,]+)"]),
        "Banka İsmi": find_pattern(text, [r"(İ?S\s*BANKASI)", r"(GARANTİ)", r"(YAPI\s*KREDİ)", r"(AKBANK)"])
    }
    return details
    
def extract_market_details(text):
    """Market fişi metninden bilgileri regex ile çıkarır."""
    text_lines = text.strip().split('\n')
    details = {
        "Kategori": "Market Fişi",
        "Market Adı": get_company_name(text),
        "Tarih": find_pattern(text, [
            r"TAR[İI]H\s*[:]?\s*(\d{2}[ -/]\d{2}[ -/]\d{4})",  
            r"^\s*(\d{2}[ -/]\d{2}[ -/]\d{4})\s*$"             
        ]),
        "Alınan Ürünler": extract_line_items(text_lines), 
        "Toplam KDV": find_pattern(text, [r"TOPKDV\s*[\n\r]*\*?([\d.,]+)"]),
        "Toplam Tutar": find_pattern(text, [r"TOPLAM\s*[\n\r]*\*?([\d.,]+)"]),
        "Banka Adı": find_pattern(text, [r"(İ?S\s*BANKASI)", r"(GARANTİ)", r"(YAPI\s*KREDİ)", r"(AKBANK)"])
    }
    return details

# --- API SUNUCUSU ---
print("API Başlatılıyor: OCR modeli yükleniyor... (Bu işlem biraz sürebilir)")
try:
    predictor = ocr_predictor(pretrained=True)
    print("OCR Modeli Yüklendi. Sunucu hazır.")
except Exception as e:
    print(f"HATA: OCR modeli yüklenemedi. {e}")
    print("TensorFlow veya PyTorch kurulumunuzu kontrol edin.")
    predictor = None 

app = FastAPI()

try:
    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
except Exception:
    pass

@app.get("/")
def read_root():
    return {"message": "OCR Sunucusu Aktif. Lütfen /process_receipt/ adresine POST isteği atın."}

@app.post("/process_receipt/")
async def process_receipt(file: UploadFile = File(...)):
    if predictor is None:
        raise HTTPException(status_code=500, detail="Sunucu hatası: OCR Modeli yüklenemedi.")

    try:
        image_data = await file.read()
        if not image_data:
            raise HTTPException(status_code=400, detail="Boş dosya yüklendi.")

        doc = DocumentFile.from_images([image_data])
        result = predictor(doc)
        
        if not result.pages:
            raise HTTPException(status_code=400, detail="Görüntüde metin bulunamadı.")
        
        full_text = result.pages[0].render()
        category = classify_receipt(full_text)
        
        extracted_data = None
        if category == "BENZİN":
            extracted_data = extract_benzin_details(full_text)
        elif category == "YEMEK":
            extracted_data = extract_market_details(full_text) 
        elif category == "MARKET":
            extracted_data = extract_market_details(full_text)
        else:
            extracted_data = {"Kategori": "DİĞER", "Ham Metin": full_text}
            
        for key, value in extracted_data.items():
            if value is None:
                extracted_data[key] = "Bulunamadı" 
        return extracted_data

    except Exception as e:
        print(f"HATA OLUŞTU: {e}")
        raise HTTPException(status_code=500, detail=f"Sunucu tarafında bir hata oluştu: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)