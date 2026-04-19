import pandas as pd
import FinanceDataReader as fdr
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os

def send_telegram(file_path):
    # GitHub Secrets에 저장된 값을 안전하게 가져옵니다.
    token = os.environ.get('TELEGRAM_TOKEN', '').strip()
    chat_id = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
    
    if not token or not chat_id:
        print("❌ 에러: GitHub Secrets에서 토큰이나 ID를 읽어오지 못했습니다.")
        return

    try:
        # 1. 메시지 전송
        msg_url = f"https://api.telegram.org/bot{token}/sendMessage"
        params = {'chat_id': chat_id, 'text': "📢 [AI 투자 리포트] 분석이 완료되어 리포트를 전송합니다. 🚀"}
        requests.get(msg_url, params=params, timeout=10)
        
        # 2. 파일 전송
        file_url = f"https://api.telegram.org/bot{token}/sendDocument"
        with open(file_path, 'rb') as f:
            res = requests.post(file_url, data={'chat_id': chat_id}, files={'document': f}, timeout=20)
            
        if res.status_code == 200:
            print("✅ 텔레그램 전송 완료!")
        else:
            print(f"❌ 전송 실패: {res.status_code}, {res.text}")
    except Exception as e:
        print(f"❌ 시스템 에러: {e}")

# 분석 대상 테마 (항공/우주 포함 확장 버전)
THEMES = {
    '항공/우주': ['대한항공', '한국항공우주', '한화에어로스페이스', '현대로템'],
    '반도체': ['삼성전자', 'SK하이닉스', '한미반도체'],
    '이차전지': ['에코프로', 'LG에너지솔루션', '포스코홀딩스'],
    '자동차': ['현대차', '기아'],
    '바이오': ['삼성바이오로직스', '셀트리온'],
    'AI/로봇': ['네이버', '레인보우로보틱스', '두산로보틱스']
}

print("🔍 데이터 분석 중...")
results = []
try:
    df_list = fdr.StockListing('KOSPI')
    for theme, stocks in THEMES.items():
        for name in stocks:
            try:
                target = df_list[df_list['Name'] == name]
                if target.empty: continue
                code = target['Code'].values[0]
                # 최근 7일 데이터
                df = fdr.DataReader(code, (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))
                if not df.empty:
                    curr_price = int(df['Close'].iloc[-1])
                    prev_price = int(df['Close'].iloc[-2])
                    results.append({
                        '테마': theme, 
                        '종목명': name, 
                        '현재가': curr_price,
                        '전일대비': curr_price - prev_price,
                        '분석시간': datetime.now().strftime('%Y-%m-%d %H:%M')
                    })
                    print(f"✅ {name} 완료")
            except: continue

    if results:
        save_name = 'AI_Daily_Report.xlsx'
        pd.DataFrame(results).to_excel(save_name, index=False)
        send_telegram(save_name)
except Exception as e:
    print(f"🔥 분석 중 에러: {e}")
