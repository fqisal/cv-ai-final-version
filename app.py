from flask import Flask, request, jsonify
import requests
import PyPDF2
import io
from apscheduler.schedulers.background import BackgroundScheduler
import time
import os

app = Flask(__name__)

# إعدادات SharePoint - استبدل القيم إذا تحتاج
SHAREPOINT_CONFIG = {
    'tenant_id': os.getenv('TENANT_ID', 'aa8f14be-df21-409d-8ac3-aed9c521f126'),
    'client_id': os.getenv('CLIENT_ID', '056747fa-0c7e-4eb3-91ee-f6eef2b826a9'),
    'client_secret': os.getenv('CLIENT_SECRET', 'hBi8Q~YIoCffRaXW8zlgBqdfonf1sB4hPcIWlcyV'),
    'site_url': 'https://dcc961.sharepoint.com/sites/SmartHiringPortal',
    'list_name': 'AI Processing Queue'
}

def get_sharepoint_access_token():
    """الحصول على access token لـ SharePoint"""
    try:
        url = f"https://accounts.accesscontrol.windows.net/{SHAREPOINT_CONFIG['tenant_id']}/tokens/OAuth/2"
        
        data = {
            'grant_type': 'client_credentials',
            'client_id': f"{SHAREPOINT_CONFIG['client_id']}@{SHAREPOINT_CONFIG['tenant_id']}",
            'client_secret': SHAREPOINT_CONFIG['client_secret'],
            'resource': f"00000003-0000-0ff1-ce00-000000000000/dcc961.sharepoint.com@{SHAREPOINT_CONFIG['tenant_id']}"
        }
        
        response = requests.post(url, data=data)
        return response.json().get('access_token')
    except Exception as e:
        print(f"Error getting token: {e}")
        return None

def get_pending_applications():
    """جلب الطلبات الجديدة من SharePoint"""
    try:
        access_token = get_sharepoint_access_token()
        if not access_token:
            return []
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json;odata=verbose'
        }
        
        url = f"{SHAREPOINT_CONFIG['site_url']}/_api/web/lists/getbytitle('{SHAREPOINT_CONFIG['list_name']}')/items"
        url += "?$filter=Status eq 'Pending'"
        
        response = requests.get(url, headers=headers)
        return response.json().get('d', {}).get('results', [])
        
    except Exception as e:
        print(f"Error getting applications: {e}")
        return []

def update_application_status(item_id, results):
    """تحديث حالة الطلب في SharePoint"""
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
        
        url = f"{SHAREPOINT_CONFIG['site_url']}/_api/web/lists/getbytitle('{SHAREPOINT_CONFIG['list_name']}')/items({item_id})"
        
        data = {
            'Status': 'Completed',
            'Result': str(results)
        }
        
        response = requests.post(url, headers=headers, json=data)
        return response.status_code == 204
        
    except Exception as e:
        print(f"Error updating application: {e}")
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
    
    if score >= 80:
        priority = "High"
    elif score >= 60:
        priority = "Medium"
    else:
        priority = "Low"
    
    return {
        "matches": matches,
        "score": round(score, 2),
        "priority": priority,
        "matched_count": matched_count,
        "total_keywords": total_keywords
    }

def process_sharepoint_queue():
    """معالجة الطلبات الجديدة كل دقيقة"""
    print(f"{time.ctime()} - Checking SharePoint for new applications...")
    
    pending_apps = get_pending_applications()
    print(f"Found {len(pending_apps)} pending applications")
    
    for app in pending_apps:
        try:
            item_id = app['Id']
            pdf_url = app['PDFUrl']
            keywords_str = app.get('Keywords', '')
            keywords = [kw.strip() for kw in keywords_str.split(',')] if keywords_str else []
            
            print(f"Processing application {item_id}")
            
            # استخراج النص من PDF
            cv_text = extract_text_from_pdf(pdf_url)
            
            if cv_text.startswith("Error"):
                print(f"Error extracting PDF for {item_id}: {cv_text}")
                continue
            
            # تحليل النص
            result = analyze_cv(cv_text, keywords)
            
            # تحديث SharePoint بالنتائج
            success = update_application_status(item_id, result)
            
            if success:
                print(f"✅ Completed processing application {item_id}")
                print(f"Results: {result}")
            else:
                print(f"❌ Failed to update application {item_id}")
            
        except Exception as e:
            print(f"❌ Error processing application {item_id}: {e}")

# الجدولة التلقائية - تفحص كل دقيقة
scheduler = BackgroundScheduler()
scheduler.add_job(func=process_sharepoint_queue, trigger="interval", minutes=1)
scheduler.start()

@app.route('/test', methods=['GET'])
def test():
    return jsonify({"message": "CV AI Service with SharePoint is working! 🚀", "status": "active"})

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        data = request.json
        
        pdf_url = data.get('pdf_url', '')
        keywords = data.get('keywords', [])
        
        if not pdf_url or not keywords:
            return jsonify({"error": "Missing pdf_url or keywords"}), 400
        
        # استخراج النص من PDF
        cv_text = extract_text_from_pdf(pdf_url)
        
        if cv_text.startswith("Error"):
            return jsonify({"error": cv_text}), 400
        
        # تحليل النص
        result = analyze_cv(cv_text, keywords)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
