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
        pos_words = ['상승', '호재', '매수', '돌파', '성장', '흑자', '최고', '상향']
        neg_words = ['하락', '악재', '매도', '급락', '우려', '적자', '최저', '하향']
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
        msg = f"📊 [{datetime.now().strftime('%m/%d %H:%M')}] KOSPI 100 실시간 테스트 분석 리포트"
        requests.get(f"https://api.telegram.org/bot{token}/sendMessage", params={'chat_id': chat_id, 'text': msg})
        with open(file_path, 'rb') as f:
            requests.post(f"https://api.telegram.org/bot{token}/sendDocument", data={'chat_id': chat_id}, files={'document': f})
        print("✅ 텔레그램 발송 완료")
    except: pass

# 분석 실행
try:
    print("🚀 데이터 분석 및 지표 계산 시작...")
    df_kospi = fdr.StockListing('KOSPI')
    top_100 = df_kospi.head(100)
    
    final_data = []
    # 충분한 데이터 확보를 위해 50일전부터 가져옴
    start_search = (datetime.now() - timedelta(days=50)).strftime('%Y-%m-%d')
    
    for idx, row in top_100.iterrows():
        name, code = row['Name'], row['Code']
        try:
            df = fdr.DataReader(code, start_search)
            if len(df) < 20: continue # 데이터 부족 시 패스
            
            curr_price = int(df['Close'].iloc[-1])
            ma20 = df['Close'].rolling(window=20).mean().iloc[-1]
            rsi_series = calculate_rsi(df)
            rsi = rsi_series.iloc[-1]
            news_score = get_weekly_sentiment(name)
            
            # 종합 점수 및 예측 로직
            tech_score = 0
            if curr_price > ma20: tech_score += 1.5
            if rsi < 35: tech_score += 2.0
            if rsi > 70: tech_score -= 1.5
            
            total_val = round((news_score * 0.4) + (tech_score * 0.6), 2)
            prediction = "강력 매수" if total_val > 2.0 else "매수 우세" if total_val > 0.5 else "관망" if total_val > -0.5 else "매도 주의"

            final_data.append({
                '순위': len(final_data) + 1,
                '종목명': name,
                '현재가': curr_price,
                '20일평균': int(ma20) if not np.isnan(ma20) else 0,
                'RSI(심리)': round(rsi, 1) if not np.isnan(rsi) else 50,
                '뉴스점수': news_score,
                'AI종합점수': total_val,
                '최종전망': prediction
            })
            print(f"✅ {name} 완료")
        except: continue

    if final_data:
        save_name = 'KOSPI100_Test_Report.xlsx'
        pd.DataFrame(final_data).to_excel(save_name, index=False)
        send_telegram(save_name)
except Exception as e:
    print(f"🔥 에러: {e}")
