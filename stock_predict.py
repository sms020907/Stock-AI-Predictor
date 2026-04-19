import pandas as pd
import FinanceDataReader as fdr
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os
import numpy as np

# [수정] 뉴스 분석 함수: 정확히 7일치만 긁어오도록 쿼리 강화
def get_weekly_sentiment(name):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    
    # after와 before를 모두 사용하여 정확히 버튼 누른 시점 기준 일주일 고정
    query = f"{name} after:{start_date.strftime('%Y-%m-%d')} before:{end_date.strftime('%Y-%m-%d')}"
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    
    score = 0
    try:
        res = requests.get(url, timeout=10)
        soup = BeautifulSoup(res.content, 'xml')
        items = soup.find_all('item')
        
        # 긍정/부정 단어 확장 (강력매수 포착용)
        pos_words = ['상승', '호재', '매수', '돌파', '성장', '흑자', '최고', '상향', '강세', '급등']
        neg_words = ['하락', '악재', '매도', '급락', '우려', '적자', '최저', '하향', '약세', '하회']
        
        # 최근 뉴스 15개로 분석 범위 확대
        for item in items[:15]:
            text = item.title.text
            for pw in pos_words: 
                if pw in text: score += 0.5 # 가중치 조절
            for nw in neg_words: 
                if nw in text: score -= 0.5
    except: pass
    return round(score, 2)

# RSI 계산 함수 (기존과 동일)
def calculate_rsi(df, period=14):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1+rs))

if __name__ == "__main__":
    # ... (서버 시작 알림 부분 동일) ...

    try:
        df_kospi = fdr.StockListing('KOSPI')
        top_100 = df_kospi.head(100)
        final_data = []
        
        # 분석 기준일 설정 (버튼 누른 시점)
        today = datetime.now()
        start_search = (today - timedelta(days=50)).strftime('%Y-%m-%d')
        
        for idx, row in top_100.iterrows():
            name, code = row['Name'], row['Code']
            try:
                df = fdr.DataReader(code, start_search)
                if len(df) < 20: continue
                
                curr_price = int(df['Close'].iloc[-1])
                ma20 = df['Close'].rolling(window=20).mean().iloc[-1]
                rsi = calculate_rsi(df).iloc[-1]
                
                # 뉴스 점수 (정확히 버튼 누른 시점 기준 일주일)
                news_score = get_weekly_sentiment(name)
                
                # [수정] 기술적 점수 계산 로직
                tech_score = 0
                if curr_price > ma20: tech_score += 1.0  # 정배열 상태
                if rsi < 30: tech_score += 2.5          # 과매도 구간 (강력 찬스)
                elif rsi < 45: tech_score += 1.5        # 저점 매수 구간
                if rsi > 75: tech_score -= 2.0          # 과열 구간 주의
                
                # [수정] 종합 점수 산출 (뉴스 40% + 기술 60%)
                total_val = round((news_score * 0.4) + (tech_score * 0.6), 2)
                
                # [수정] 판정 기준 (강력 매수 진입장벽을 조금 높여 신뢰도 향상)
                if total_val > 2.5:
                    prediction = "🔥 강력 매수"
                elif total_val > 0.8:
                    prediction = "✅ 매수 우세"
                elif total_val > -0.5:
                    prediction = "👀 관망"
                else:
                    prediction = "⚠️ 매도 주의"

                final_data.append({
                    '순위': len(final_data) + 1, 
                    '종목명': name, 
                    '현재가': curr_price,
                    'RSI(심리)': round(rsi, 1) if not np.isnan(rsi) else 50,
                    '뉴스점수': news_score, 
                    'AI종합점수': total_val, 
                    '최종전망': prediction
                })
            except: continue

        # ... (엑셀 저장 및 텔레그램 전송 부분 동일) ...
