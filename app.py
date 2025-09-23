from flask import Flask, request, jsonify
import requests
import PyPDF2
import io

app = Flask(__name__)

def extract_text_from_pdf(pdf_url):
    """استخراج النص من PDF"""
    try:
        # تحميل ملف PDF من الرابط
        response = requests.get(pdf_url)
        pdf_file = io.BytesIO(response.content)
        
        # قراءة PDF
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
            
        return text
    except Exception as e:
        return f"Error: {str(e)}"

def analyze_cv(cv_text, required_keywords):
    """تحليل السيرة الذاتية"""
    # تحويل النص لكلمات صغيرة للمقارنة
    cv_text_lower = cv_text.lower()
    required_keywords_lower = [kw.lower() for kw in required_keywords]
    
    # البحث عن الكلمات المطابقة
    matches = []
    for keyword in required_keywords_lower:
        if keyword in cv_text_lower:
            matches.append(keyword)
    
    # حساب النسبة
    total_keywords = len(required_keywords)
    matched_count = len(matches)
    
    if total_keywords > 0:
        score = (matched_count / total_keywords) * 100
    else:
        score = 0
    
    # تحديد الأولوية
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

@app.route('/test', methods=['GET'])
def test():
    """اختبار أن الخدمة شغالة"""
    return jsonify({"message": "CV AI Service is working! 🚀", "status": "active"})

@app.route('/analyze', methods=['POST'])
def analyze():
    """تحليل السيرة الذاتية"""
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
