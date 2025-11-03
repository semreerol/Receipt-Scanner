import os

os.environ["USE_TF"] = "1" 

from doctr.io import DocumentFile
from doctr.models import ocr_predictor

import tkinter as tk
from tkinter import filedialog

import re

def classify_receipt(text):
    """
    OCR'dan gelen metni analiz ederek fişin kategorisini tahmin eder.
    """
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
    
    print("\n--- Kategori Analizi ---")
    for category, keywords_with_scores in KEYWORDS.items():
        for keyword, score in keywords_with_scores: 
            if keyword in text_upper:
                print(f"Bulunan anahtar kelime: '{keyword}' -> Kategori: {category} (Puan: +{score})")
                scores[category] += score 
                
    print(f"Kategori Puanları: {scores}")
    
    if all(score == 0 for score in scores.values()):
        return "DİĞER"
    
    best_category = max(scores, key=scores.get)
    print(f"En Yüksek Puan: {best_category}")
    return best_category

# --- BİLGİ ÇIKARIM FONKSİYONLARI ---

def find_pattern(text, patterns, default=None):
    """
    Metin içinde bir dizi regex kalıbını arar. Bulduğu ilk sonucu döndürür.
    """
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            if match.groups():
                return match.group(1).strip()
            else:
                return match.group(0).strip()
    return default

def get_company_name(text):
    """Metnin ilk iki satırını firma adı olarak alır."""
    lines = text.strip().split('\n')
    if len(lines) == 0:
        return None
    
    firma_adi = lines[0] 
    if len(lines) > 1 and lines[1].strip(): 
        firma_adi += " " + lines[1].strip() 
    return firma_adi

def extract_line_items(text_lines):
    """
    Metin satırlarını analiz ederek ürün listesini çıkarmaya çalışır.
    """
    product_lines = []
    
    SUMMARY_KEYWORDS = [
        "TOPLAM", "TOPKDV", "ARA TOPLAM", "NAKİT", 
        "KREDİ KARTI", "BANKA", "ÖDEME", "FİŞ TOPLAMI",
        "MALİ BİLGİLER"
    ]
    
    start_processing = False
    START_KEYWORDS = ["TARİH", "SAAT", "FİŞ NO", "ÜRÜN ADI", "AÇIKLAMA", "ADİSYON"]

    print("\n--- Ürün Analizi Başlatılıyor ---")
    for line in text_lines:
        line_upper = line.upper().strip()
        
        if not start_processing:
            if any(keyword in line_upper for keyword in START_KEYWORDS):
                print(f"Başlangıç sinyali bulundu (Satır: {line_upper}). Ürünler taranıyor...")
                start_processing = True
            continue 
        
        if any(keyword in line_upper for keyword in SUMMARY_KEYWORDS):
            print(f"Bitiş sinyali bulundu (Satır: {line_upper}). Ürün taraması bitti.")
            break 
        
        match = re.search(r'(.+?)\s+[*F]?\s*([\d,.]+)$', line.strip())
        
        if match:
            product_name = match.group(1).strip()
            price = match.group(2).strip()
            product_name = re.sub(r'^\d+\s*[xX]\s*', '', product_name) 

            if len(product_name) > 2 and "KDV" not in product_name.upper() and "İNDİRİM" not in product_name.upper():
                product_lines.append(f"  * {product_name} | Fiyat: {price}")
                print(f"  -> Bulunan Ürün: {product_name} | Fiyat: {price}")
                
    if not product_lines:
        return "Sipariş kalemleri çıkarılamadı (veya fişte ürün yok)."
    
    return "\n" + "\n".join(product_lines)


def extract_benzin_details(text):
    """Benzin fişi metninden bilgileri regex ile çıkarır."""
    
    details = {
        "Kategori": "Benzin Fişi",
        "Firma Adı": get_company_name(text),
        "Tarih": find_pattern(text, [r"(\d{2}[ -/]\d{2}[ -/]\d{4})"]),
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
        "Tarih": find_pattern(text, [r"(\d{2}[ -/]\d{2}[ -/]\d{4})"]), 
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
        "Tarih": find_pattern(text, [r"(\d{2}[ -/]\d{2}[ -/]\d{4})"]),
        "Alınan Ürünler": extract_line_items(text_lines), 
        "Toplam KDV": find_pattern(text, [r"TOPKDV\s*[\n\r]*\*?([\d.,]+)"]),
        "Toplam Tutar": find_pattern(text, [r"TOPLAM\s*[\n\r]*\*?([\d.,]+)"]),
        "Banka Adı": find_pattern(text, [r"(İ?S\s*BANKASI)", r"(GARANTİ)", r"(YAPI\s*KREDİ)", r"(AKBANK)"])
    }
    return details


# --- ANA İŞLEYİŞ ---


root = tk.Tk()
root.withdraw()

print("Lütfen işlenecek bir fiş/belge dosyası seçin...")
file_path = filedialog.askopenfilename(
    title="Fiş veya Belge Seçin",
    filetypes=[
        ("Görüntü Dosyaları", "*.jpg *.jpeg *.png *.bmp *.tiff"),
        ("PDF Dosyaları", "*.pdf"),
        ("Tüm Dosyalar", "*.*")
    ]
)

if not file_path:
    print("Hiçbir dosya seçilmedi. Program sonlandırılıyor.")
    exit()

print(f"Seçilen dosya: {file_path}")

print("OCR modeli yükleniyor...")
predictor = ocr_predictor(pretrained=True)

doc = None
try:
    if file_path.lower().endswith('.pdf'):
        doc = DocumentFile.from_pdf(file_path)
    else:
        doc = DocumentFile.from_images([file_path])
except Exception as e:
    print(f"Dosya yüklenirken bir hata oluştu: {e}")
    exit()

print("OCR işlemi gerçekleştiriliyor...")
result = predictor(doc)

# --- SONUÇLARI İŞLEME ---
if result.pages:
    full_text = result.pages[0].render()
    
    print("\n--- TANINAN HAM METİN ---")
    print(full_text)
    print("-------------------------\n")
    
    category = classify_receipt(full_text)
    
    extracted_data = None
    if category == "BENZİN":
        extracted_data = extract_benzin_details(full_text)
    elif category == "YEMEK":
        extracted_data = extract_yemek_details(full_text) 
    elif category == "MARKET":
        extracted_data = extract_market_details(full_text)
    else:
        print(f"Kategori '{category}' için özel bir bilgi çıkarıcı bulunmuyor.")

    if extracted_data:
        print("\n************************************")
        print(f"*** {extracted_data.get('Kategori', 'Fiş Detayları')} ***")
        print("************************************")
        for key, value in extracted_data.items():
            display_value = value if value is not None else "Bulunamadı"
            print(f"- {key}: {display_value}")
        print("************************************\n")
    
else:
    print("Görüntüde hiç sayfa bulunamadı.")

print("İşlem tamamlandı.")