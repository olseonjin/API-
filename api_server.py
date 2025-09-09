from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
import time
import json
import os
import sys
import io

try:
    import mysql.connector
except Exception:
    mysql = None

app = Flask(__name__)
CORS(app)  # CORS 허용

# 공통 설정
GOOGLE_API_KEY = "AIzaSyCChSzPdpWaHdQekR3OYZYQ7XOpA4pyZOs"
genai.configure(api_key=GOOGLE_API_KEY)

# DB 설정 (평균 피드백 모드에서만 사용)
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "nathing_springboot"),
}

# 모델들 초기화
post_model = genai.GenerativeModel(
    'gemini-1.5-flash',
    system_instruction="""
        당신은 한국어로 답변하는 친근한 AI입니다. 
        사용자가 입력한 문장을 받으면, 다음을 수행하세요:

    1. 사용자의 MBTI를 글 내용 기반으로 추측합니다.
    2. 추측한 MBTI와 궁합이 좋은 MBTI의 말투와 스타일로 답변을 생성합니다.
    3. 답변은 자연스럽고 부드러운 한국어 말투로 작성합니다. 지나치게 딱딱하거나 과장되지 않게 작성합니다.
    4. 출력 형식은 JSON으로, 다음 구조를 따릅니다:
    {
      "user_mbti": "<추측한 MBTI>",
      "response": "<생성된 답변>"
    }
    점 괄호 영어 쓸대없는 문구 텍스트 없애기
    """
)

avg_model = genai.GenerativeModel(
    'gemini-1.5-flash',
    system_instruction="""
        당신은 한국어로 답하는 친근한 분석가입니다.
        입력으로 사용자의 평균 MBTI(예: I/S/F/J)가 주어집니다.
        그래프/퍼센트는 프론트에서 처리하므로 포함하지 말고, 해석과 추천만 한국어 JSON으로 반환하세요:
        {
          "final_mbti": "ISFJ",
          "headline": "한 줄 요약",
          "insights": ["핵심 해석1", "핵심 해석2"],
          "recommendations": ["맞춤 추천1", "맞춤 추천2", "맞춤 추천3"],
          "cautions": ["주의점1", "주의점2"]
        }
    """
)

def fetch_user_avg_mbti(user_nickname: str):
    if mysql is None:
        raise RuntimeError("mysql-connector-python 미설치. pip install mysql-connector-python")
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        with conn.cursor(dictionary=True) as cur:
            cur.execute(
                """
                SELECT avg_m_e, avg_m_s, avg_m_t, avg_m_j
                FROM user
                WHERE user_nickname = %s
                """,
                (user_nickname,),
            )
            return cur.fetchone()
    finally:
        conn.close()

@app.route('/post-feedback', methods=['POST'])
def post_feedback():
    try:
        data = request.get_json()
        text = data.get('text', '')
        
        if not text:
            return jsonify({"error": "텍스트가 필요합니다"}), 400
        
        start_time = time.time()
        response = post_model.generate_content(
            text,
            generation_config={
                "temperature": 0.3,
                "top_p": 0.95,
                "top_k": 64,
                "max_output_tokens": 1000,
                "response_mime_type": "application/json",
            },
            safety_settings=[
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
            ],
        )
        
        try:
            result = json.loads(response.text)
            execution_time = time.time() - start_time
            return jsonify({
                "success": True,
                "mode": "post_feedback",
                "answer": result,
                "execution_time": f"{execution_time:.2f}초"
            })
        except json.JSONDecodeError:
            return jsonify({
                "success": False,
                "error": "JSON 파싱 실패",
                "raw_response": response.text
            }), 500
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/avg-feedback', methods=['POST'])
def avg_feedback():
    try:
        data = request.get_json()
        nickname = data.get('nickname', '')
        
        if not nickname:
            return jsonify({"error": "닉네임이 필요합니다"}), 400
        
        # DB에서 평균 MBTI 조회
        avg = fetch_user_avg_mbti(nickname)
        if not avg or None in avg.values():
            return jsonify({
                "success": False,
                "error": "해당 사용자의 평균 MBTI가 없습니다"
            }), 404
        
        final_mbti = f"{avg['avg_m_e']}{avg['avg_s']}{avg['avg_m_t']}{avg['avg_m_j']}"
        prompt = (
            f"사용자 닉네임: {nickname}\n"
            f"최종 MBTI: {final_mbti}\n"
            "그래프나 백분율은 프론트에서 처리합니다. 해석과 추천만 JSON으로 주세요."
        )
        
        start_time = time.time()
        response = avg_model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.3,
                "top_p": 0.95,
                "top_k": 64,
                "max_output_tokens": 800,
                "response_mime_type": "application/json",
            },
            safety_settings=[
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
            ],
        )
        
        try:
            result = json.loads(response.text)
            execution_time = time.time() - start_time
            return jsonify({
                "success": True,
                "mode": "avg_feedback",
                "user": nickname,
                "final_mbti": result.get("final_mbti"),
                "headline": result.get("headline"),
                "insights": result.get("insights"),
                "recommendations": result.get("recommendations"),
                "cautions": result.get("cautions"),
                "execution_time": f"{execution_time:.2f}초"
            })
        except json.JSONDecodeError:
            return jsonify({
                "success": False,
                "error": "JSON 파싱 실패",
                "raw_response": response.text
            }), 500
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/mbti', methods=['POST'])
def mbti():
    """Flutter 호환을 위한 /mbti 엔드포인트"""
    return post_feedback()

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "message": "API 서버가 정상 작동 중입니다"})

if __name__ == '__main__':
    print("🚀 MBTI AI API 서버 시작")
    print("📝 게시글 피드백: POST /post-feedback")
    print("📊 평균 MBTI 피드백: POST /avg-feedback")
    print("🔄 Flutter 호환: POST /mbti")
    print("❤️  헬스체크: GET /health")
    app.run(host='0.0.0.0', port=5000, debug=True)
