import pandas as pd
import FinanceDataReader as fdr
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os
import numpy as np
import time # 시간 지연용 추가

# [보완] 텔레그램 전송 함수 (에러 로깅 강화)
def send_telegram_msg(msg):
    token = os.environ.get('TELEGRAM_TOKEN', '').strip()
    chat_id = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        try:
            requests.get(url, params={'chat_id': chat_id, 'text': msg}, timeout=10)
        except Exception as e:
            print(f"텔레그램 전송 실패: {e}")

# [보완] RSI 계산 (NaN 방어 로직 추가)
def calculate_rsi(df, period=14):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1+rs))
    return rsi.fillna(50) # 데이터 부족 시 50으로 채움

# [보완] 뉴스 분석 (날짜 필터 및 키워드 강화)
def get_weekly_sentiment(name):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    query = f"{name} after:{start_date.strftime('%Y-%m-%d')} before:{end_date.strftime('%Y-%m-%d')}"
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    score = 0
    try:
        res = requests.get(url, timeout=10)
        soup = BeautifulSoup(res.content, 'xml')
        items = soup.find_all('item')
        pos_words = ['상승', '호재', '매수', '돌파', '성장', '흑자', '최고', '상향', '강세', '급등']
        neg_words = ['하락', '악재', '매도', '급락', '우려', '적자', '최저', '하향', '약세', '하회']
        for item in items[:15]:
            text = item.title.text
            for pw in pos_words: 
                if pw in text: score += 0.5
            for nw in neg_words: 
                if nw in text: score -= 0.5
    except: pass
    return round(score, 2)

if __name__ == "__main__":
    send_telegram_msg("🚀 [민성 Stock-AI] 분석 서버 가동! 코스피 100대 기업의 '최근 일주일' 트렌드를 분석합니다.")

    try:
        df_kospi = fdr.StockListing('KOSPI')
        top_100 = df_kospi.head(100)
        final_data = []
        strong_buy_count = 0 # 강력매수 개수 카운트용
        
        start_search = (datetime.now() - timedelta(days=50)).strftime('%Y-%m-%d')
        
        for idx, row in top_100.iterrows():
            name, code = row['Name'], row['Code']
            try:
                df = fdr.DataReader(code, start_search)
                if len(df) < 20: continue
                
                curr_price = int(df['Close'].iloc[-1])
                ma20 = df['Close'].rolling(window=20).mean().iloc[-1]
                rsi = calculate_rsi(df).iloc[-1]
                news_score = get_weekly_sentiment(name)
                
                tech_score = 0
                if curr_price > ma20: tech_score += 1.0
                if rsi < 35: tech_score += 2.0
                if rsi > 70: tech_score -= 1.5
                
                total_val = round((news_score * 0.4) + (tech_score * 0.6), 2)
                
                # 판정 로직
                if total_val > 2.2:
                    prediction = "강력 매수"
                    strong_buy_count += 1
                elif total_val > 0.7:
                    prediction = "매수 우세"
                elif total_val > -0.5:
                    prediction = "관망"
                else:
                    prediction = "매도 주의"

                final_data.append({
                    '순위': len(final_data) + 1, '종목명': name, '현재가': curr_price,
                    'RSI(심리)': round(rsi, 1), '뉴스점수': news_score, 
                    'AI종합점수': total_val, '최종전망': prediction
                })
                time.sleep(0.05) # 서버 과부하 방지용 미세 지연
            except: continue

        if final_data:
            save_name = 'Stock_Weekly_Report.xlsx'
            pd.DataFrame(final_data).to_excel(save_name, index=False)
            
            # [보완] 분석 결과 요약 메시지 전송
            summary = f"📊 분석 완료!\n- 분석 종목: {len(final_data)}개\n- 🔥 강력 매수: {strong_buy_count}개 발견\n\n상세 리포트(엑셀)를 확인하세요!"
            send_telegram_msg(summary)
            
            token = os.environ.get('TELEGRAM_TOKEN', '').strip()
            chat_id = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
            with open(save_name, 'rb') as f:
                requests.post(f"https://api.telegram.org/bot{token}/sendDocument", data={'chat_id': chat_id}, files={'document': f})

    except Exception as e:
        send_telegram_msg(f"🔥 에러 발생: {e}")
