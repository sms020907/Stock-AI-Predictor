import pandas as pd
import FinanceDataReader as fdr
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os

def send_telegram(file_path):
    # ⚠️ 여기에 민성님의 정보를 직접 입력하세요 (따옴표 유지)
    token = "8623742071:AAF4Y8mYSfH6a8J-AGCVHPIyrZOtOCbK5uE" 
    chat_id = "7244434577"
    
    # 만약 Secrets를 계속 쓰고 싶다면 아래 두 줄의 주석을 푸세요
    # token = os.environ.get('TELEGRAM_TOKEN', '').strip()
    # chat_id = os.environ.get('TELEGRAM_CHAT_ID', '').strip()

    if not token or not chat_id:
        print("❌ 에러: 토큰이나 ID가 비어있습니다.")
        return

    try:
        # 1. 메시지 전송
        msg_url = f"https://api.telegram.org/bot{token}/sendMessage"
        params = {'chat_id': chat_id, 'text': "📢 [AI 투자 리포트] 분석이 완료되었습니다!"}
        res_msg = requests.get(msg_url, params=params, timeout=10)
        print(f"DEBUG: 메시지 전송 결과 = {res_msg.status_code}")
        
        # 2. 파일 전송
        file_url = f"https://api.telegram.org/bot{token}/sendDocument"
        with open(file_path, 'rb') as f:
            res_file = requests.post(file_url, data={'chat_id': chat_id}, files={'document': f}, timeout=20)
            print(f"DEBUG: 파일 전송 결과 = {res_file.status_code}")
            
        if res_file.status_code == 200:
            print("✅ 텔레그램 전송 대성공!")
        else:
            print(f"❌ 전송 실패 (에러코드: {res_file.status_code})")
            print(f"상세 에러 내용: {res_file.text}") # 401일 경우 왜 틀렸는지 나옵니다.
    except Exception as e:
        print(f"❌ 시스템 에러: {e}")

# 3. 분석 테마 (민성님 전공 및 관심 종목)
THEMES = {
    '항공/우주': ['대한항공', '한국항공우주', '한화에어로스페이스'],
    '반도체': ['삼성전자', 'SK하이닉스', '한미반도체'],
    '이차전지': ['에코프로', 'LG에너지솔루션'],
    'AI/로봇': ['네이버', '두산로보틱스']
}

print("🔍 분석 시작...")
results = []
try:
    df_list = fdr.StockListing('KOSPI')
    for theme, stocks in THEMES.items():
        for name in stocks:
            target = df_list[df_list['Name'] == name]
            if not target.empty:
                code = target['Code'].values[0]
                df = fdr.DataReader(code, (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))
                if not df.empty:
                    results.append({
                        '테마': theme, 
                        '종목명': name, 
                        '현재가': int(df['Close'].iloc[-1]),
                        '변동폭': int(df['Close'].iloc[-1] - df['Close'].iloc[-2])
                    })
                    print(f"✅ {name} 분석 완료")

    if results:
        save_name = 'AI_Daily_Report.xlsx'
        pd.DataFrame(results).to_excel(save_name, index=False)
        send_telegram(save_name)
except Exception as e:
    print(f"🔥 분석 중 에러: {e}")
