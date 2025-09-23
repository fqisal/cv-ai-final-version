from flask import Flask, request, jsonify
import requests
import PyPDF2
import io
import os

app = Flask(__name__)

# إعدادات SharePoint
SHAREPOINT_CONFIG = {
    'tenant_id': 'aa8f14be-df21-409d-8ac3-aed9c521f126',
    'client_id': '056747fa-0c7e-4eb3-91ee-f6eef2b826a9',
    'client_secret': 'hBi8Q~YIoCffRaXW8zlgBqdfonf1sB4hPcIWlcyV',
    'site_url': 'https://dcc961.sharepoint.com/sites/SmartHiringPortal'
}

def get_sharepoint_access_token():
    """الحصول على access token لـ SharePoint"""
    try:
        url = f"https://accounts.accesscontrol.windows.net/{SHAREPOINT_CONFIG['tenant_id']}/tokens/OAuth/2"
        
        data = {
            'grant_type': 'client_credentials',
            'client_id': f"{SHAREPOINT_CONFIG['client_id']}@{SHAREPOINT_CONFIG['tenant_id']}",
            'client_secret': SHAREPOINT_CONFIG['client_secret'],
            'resource': '00000003-0000-0ff1-ceode-000000000000/dcc961.sharepoint.com@{SHAREPOINT_CONFIG["tenant_id"]}'
        }
        
        response = requests.post(url, data=data)
        return response.json().get('access_token')
    except Exception as e:
        print(f"Error getting token: {e}")
        return None

def update_sharepoint_item(item_id, results):
    """تحديث عنصر في SharePoint بالنتائج"""
    try:
        access_token = get_sharepoint_access_token()
        if not access_token:
            return False
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json;odata=verbose',
            'Content-Type': 'application/json;odata=verbose',
            'X-HTTP-Method': 'MERGE',
            'IF-MATCH': '*'
        }
        
        # تحديث قائمة Job Applications مباشرة
        url = f"{SHAREPOINT_CONFIG['site_url']}/_api/web/lists/getbytitle('Job Applications')/items({item_id})"
        
        data = {
            'VettingScore': results['score'],
            'MatchedKeywords': ', '.join(results['matches']),
            'ApplicationStatus': results['status'],
            'Priority': results['priority']
        }
        
        response = requests.post(url, headers=headers, json=data)
        return response.status_code == 204
        
    except Exception as e:
        print(f"Error updating SharePoint: {e}")
        return False

def extract_text_from_pdf(pdf_url):
    """استخراج النص من PDF"""
    try:
        response = requests.get(pdf_url)
        pdf_file = io.BytesIO(response.content)
        
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
            
        return text
    except Exception as e:
        return f"Error: {str(e)}"

def analyze_cv(cv_text, required_keywords):
    """تحليل السيرة الذاتية"""
    cv_text_lower = cv_text.lower()
    required_keywords_lower = [kw.lower().strip() for kw in required_keywords]
    
    matches = []
    for keyword in required_keywords_lower:
        if keyword in cv_text_lower:
            matches.append(keyword)
    
    total_keywords = len(required_keywords)
    matched_count = len(matches)
    
    if total_keywords > 0:
        score = (matched_count / total_keywords) * 100
    else:
        score = 0
    
    # تحديد الحالة والأولوية
    if score >= 70:
        status = "Interview"
        priority = "High"
    elif score >= 50:
        status = "Under Review" 
        priority = "Medium"
    else:
        status = "Rejected"
        priority = "Low"
    
    return {
        "matches": matches,
        "score": round(score, 2),
        "status": status,
        "priority": priority,
        "matched_count": matched_count,
        "total_keywords": total_keywords
    }

@app.route('/test', methods=['GET'])
def test():
    """اختبار أن الخدمة شغالة"""
    return jsonify({"message": "🎯 CV AI Service - Instant Processing 🚀", "status": "active"})

@app.route('/analyze-instant', methods=['POST'])
def analyze_instant():
    """تحليل فوري - يعيد النتائج مباشرة"""
    try:
        data = request.json
        
        pdf_url = data.get('pdf_url', '')
        keywords = data.get('keywords', [])
        item_id = data.get('item_id', '')
        
        if not pdf_url or not keywords:
            return jsonify({"error": "Missing pdf_url or keywords"}), 400
        
        print(f"🔍 معالجة طلب {item_id}...")
        
        # 1. استخراج النص من PDF
        cv_text = extract_text_from_pdf(pdf_url)
        
        if cv_text.startswith("Error"):
            return jsonify({"error": cv_text}), 400
        
        # 2. تحليل النص فوراً
        result = analyze_cv(cv_text, keywords)
        
        # 3. إذا وجد item_id، تحديث SharePoint مباشرة
        if item_id:
            update_success = update_sharepoint_item(item_id, result)
            result['sharepoint_updated'] = update_success
        
        print(f"✅ تم معالجة طلب {item_id} - النتيجة: {result['score']}%")
        
        return jsonify(result)
        
    except Exception as e:
        print(f"❌ خطأ في معالجة طلب {item_id}: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
