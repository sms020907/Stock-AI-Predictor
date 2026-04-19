import pandas as pd
import FinanceDataReader as fdr
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os

def send_telegram(file_path):
    # GitHub Secrets에서 가져온 값을 변수에 할당
    token = os.environ.get('TELEGRAM_TOKEN', '').strip()
    chat_id = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
    
    print(f"DEBUG: Token 존재 여부 = {bool(token)}")
    print(f"DEBUG: Chat ID 존재 여부 = {bool(chat_id)}")
    
    if not token or not chat_id:
        print("❌ 에러: GitHub Secrets에 토큰이나 ID가 설정되지 않았습니다.")
        return

    try:
        # 1. 메시지 전송 테스트
        msg_url = f"https://api.telegram.org/bot{token}/sendMessage"
        res = requests.get(msg_url, params={'chat_id': chat_id, 'text': "🚀 분석 완료! 파일을 전송합니다."}, timeout=10)
        print(f"DEBUG: 메시지 전송 결과 = {res.status_code}")
        
        # 2. 파일 전송
        file_url = f"https://api.telegram.org/bot{token}/sendDocument"
        with open(file_path, 'rb') as f:
            res_f = requests.post(file_url, data={'chat_id': chat_id}, files={'document': f}, timeout=20)
            print(f"DEBUG: 파일 전송 결과 = {res_f.status_code}")
            
        if res_f.status_code == 200:
            print("✅ 텔레그램으로 파일이 발송되었습니다!")
    except Exception as e:
        print(f"❌ 전송 중 시스템 에러 발생: {e}")

# 분석 로직 (항공주 포함)
THEMES = {'항공/우주': ['대한항공', '한국항공우주'], '반도체': ['삼성전자', 'SK하이닉스']}
results = []
try:
    df_list = fdr.StockListing('KOSPI')
    for theme, stocks in THEMES.items():
        for name in stocks:
            target = df_list[df_list['Name'] == name]
            if not target.empty:
                code = target['Code'].values[0]
                df = fdr.DataReader(code, (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))
                results.append({'테마': theme, '종목': name, '현재가': int(df['Close'].iloc[-1])})
                print(f"✅ {name} 분석 완료")

    if results:
        save_name = 'AI_report.xlsx'
        pd.DataFrame(results).to_excel(save_name, index=False)
        send_telegram(save_name)
except Exception as e:
    print(f"🔥 분석 중 에러: {e}")
