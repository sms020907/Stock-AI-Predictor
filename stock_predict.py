import pandas as pd
import FinanceDataReader as fdr
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os
import numpy as np
import time
import json

# [수정] 텔레그램 전송 함수 (버튼 기능 추가)
def send_telegram_msg(msg, show_button=False):
    token = os.environ.get('TELEGRAM_TOKEN', '').strip()
    chat_id = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
    github_token = os.environ.get('GH_TOKEN') # 깃허브 신호를 보내기 위한 토큰

    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {'chat_id': chat_id, 'text': msg}
        
        # 분석 완료 메시지일 때만 '다시 분석하기' 버튼 추가
        if show_button:
            reply_markup = {
                "inline_keyboard": [[
                    {"text": "🔄 지금 다시 분석하기", "callback_data": "run_analysis"}
                ]]
            }
            payload['reply_markup'] = json.dumps(reply_markup)
            
        try:
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"텔레그램 전송 실패: {e}")

# RSI 계산 함수
def calculate_rsi(df, period=14):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1+rs))
    return rsi.fillna(50)

# 뉴스 분석 함수
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
    send_telegram_msg("🚀 [민성 Stock-AI] 분석 서버 가동! 코스피 100대 기업 트렌드를 분석합니다.")

    try:
        df_kospi = fdr.StockListing('KOSPI')
        top_100 = df_kospi.head(100)
        final_data = []
        strong_buy_count = 0
        
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
                time.sleep(0.05)
            except: continue

        if final_data:
            save_name = 'Stock_Weekly_Report.xlsx'
            pd.DataFrame(final_data).to_excel(save_name, index=False)
            
            summary = f"📊 분석 완료!\n- 분석 종목: {len(final_data)}개\n- 🔥 강력 매수: {strong_buy_count}개 발견\n\n원하실 때 아래 버튼을 누르면 다시 분석합니다!"
            # [수정] 버튼 표시 옵션 활성화
            send_telegram_msg(summary, show_button=True)
            
            token = os.environ.get('TELEGRAM_TOKEN', '').strip()
            chat_id = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
            with open(save_name, 'rb') as f:
                requests.post(f"https://api.telegram.org/bot{token}/sendDocument", data={'chat_id': chat_id}, files={'document': f})

    except Exception as e:
        send_telegram_msg(f"🔥 에러 발생: {e}")
