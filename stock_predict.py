import pandas as pd
import FinanceDataReader as fdr
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os
import numpy as np

def get_weekly_sentiment(name):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    query = f"{name} after:{start_date.strftime('%Y-%m-%d')}"
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    score = 0
    try:
        res = requests.get(url, timeout=10)
        soup = BeautifulSoup(res.content, 'xml')
        items = soup.find_all('item')
        pos_words = ['상승', '호재', '매수', '돌파', '성장', '흑자', '최고']
        neg_words = ['하락', '악재', '매도', '급락', '우려', '적자', '최저']
        for item in items[:10]:
            text = item.title.text
            for pw in pos_words: 
                if pw in text: score += 0.8
            for nw in neg_words: 
                if nw in text: score -= 0.8
    except: pass
    return round(score, 2)

def calculate_rsi(df, period=14):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1+rs))

def send_telegram(file_path):
    token = os.environ.get('TELEGRAM_TOKEN', '').strip()
    chat_id = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
    if not token or not chat_id: return
    try:
        msg = f"📊 [{datetime.now().strftime('%m/%d')}] KOSPI 100 AI 기술적 분석 리포트 완료"
        requests.get(f"https://api.telegram.org/bot{token}/sendMessage", params={'chat_id': chat_id, 'text': msg})
        with open(file_path, 'rb') as f:
            requests.post(f"https://api.telegram.org/bot{token}/sendDocument", data={'chat_id': chat_id}, files={'document': f})
    except: pass

try:
    print("🚀 KOSPI 100 기술적 지표 분석 시작...")
    df_kospi = fdr.StockListing('KOSPI')
    top_100 = df_kospi.head(100)
    
    final_data = []
    for idx, row in top_100.iterrows():
        name, code = row['Name'], row['Code']
        try:
            # 1. 데이터 수집 (지표 계산을 위해 30일치)
            df = fdr.DataReader(code, (datetime.now() - timedelta(days=40)).strftime('%Y-%m-%d'))
            curr_price = int(df['Close'].iloc[-1])
            
            # 2. 기술적 지표 계산
            ma20 = df['Close'].rolling(window=20).mean().iloc[-1] # 20일 이동평균선
            rsi = calculate_rsi(df).iloc[-1] # RSI (과매수/과매도 지표)
            
            # 3. 뉴스 점수
            news_score = get_weekly_sentiment(name)
            
            # 4. 종합 예측 점수 (뉴스 40% + 기술적 지표 60%)
            # - 주가가 20일선 위에 있으면 +, RSI가 30 미만(과매도)이면 + 점수 부여
            tech_score = 0
            if curr_price > ma20: tech_score += 1.5
            if rsi < 35: tech_score += 2.0  # 저평가 매수 기회
            if rsi > 70: tech_score -= 1.5  # 고평가 위험
            
            total_val = round((news_score * 0.4) + (tech_score * 0.6), 2)
            prediction = "강력 매수" if total_val > 2.0 else "매수 우세" if total_val > 0.5 else "관망" if total_val > -0.5 else "매도 주의"

            final_data.append({
                '순위': len(final_data) + 1,
                '종목명': name,
                '현재가': curr_price,
                '20일평균': int(ma20),
                'RSI(심리도)': round(rsi, 1),
                '뉴스점수': news_score,
                'AI종합점수': total_val,
                '최종전망': prediction
            })
            print(f"✅ {name} 분석 완료 (RSI: {round(rsi,1)})")
        except: continue

    if final_data:
        save_name = 'KOSPI100_Advanced_Report.xlsx'
        pd.DataFrame(final_data).to_excel(save_name, index=False)
        send_telegram(save_name)
except Exception as e:
    print(f"🔥 에러: {e}")
