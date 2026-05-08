import pandas as pd
import FinanceDataReader as fdr
import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime, timedelta
import os
import json

# 텔레그램 전송 함수
def send_telegram_msg(msg, show_button=False):
    token = os.environ.get('TELEGRAM_TOKEN', '').strip()
    chat_id = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {'chat_id': chat_id, 'text': msg}
        if show_button:
            reply_markup = {"inline_keyboard": [[{"text": "🔄 지금 다시 분석하기", "callback_data": "run_analysis"}]]}
            payload['reply_markup'] = json.dumps(reply_markup)
        try:
            requests.post(url, json=payload, timeout=10)
        except: pass

# 수급/기술 지표 분석 함수
def analyze_stock_details(code):
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=40)).strftime('%Y-%m-%d')
    try:
        df = fdr.DataReader(code, start_date, end_date)
        if len(df) < 25: return None
        curr_price = df['Close'].iloc[-1]
        
        # 5일/20일 이평선 정배열
        ma5 = df['Close'].rolling(window=5).mean().iloc[-1]
        ma20 = df['Close'].rolling(window=20).mean().iloc[-1]
        trend_score = 1.0 if ma5 > ma20 else -0.5
        
        # 거래량 증가 확인
        avg_volume = df['Volume'].iloc[-6:-1].mean()
        curr_volume = df['Volume'].iloc[-1]
        vol_score = 1.2 if curr_volume > avg_volume * 1.5 else 0
        
        # RSI 과열 방지 (70 이상 감점)
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs.iloc[-1]))
        
        rsi_score = 0
        if rsi < 35: rsi_score = 2.0
        if rsi > 70: rsi_score = -2.5 # SK스퀘어 같은 고점 낙폭 방지
        
        return {'curr_price': int(curr_price), 'rsi': round(rsi, 1), 'tech_total': trend_score + vol_score + rsi_score}
    except: return None

# 뉴스 점수 함수
def get_weekly_sentiment(name):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    query = f"{name} after:{start_date.strftime('%Y-%m-%d')}"
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    score = 0
    try:
        res = requests.get(url, timeout=7)
        soup = BeautifulSoup(res.content, 'xml')
        items = soup.find_all('item')
        pos_words = ['상승', '호재', '매수', '수주', '흑자', '공급계약', '양산', '신고가']
        neg_words = ['하락', '악재', '매도', '우려', '적자', '유상증자', '리콜', '하회']
        for item in items[:10]:
            text = item.title.text
            for pw in pos_words: 
                if pw in text: score += 0.5
            for nw in neg_words: 
                if nw in text: score -= 0.5
    except: pass
    return score

if __name__ == "__main__":
    print("🚀 [전체 시장 AI 랭킹] 코스피 상위 100대 기업 분석 시작...")
    stock_results = []
    
    # [핵심 변경] 코스피 전체 리스트에서 상위 100개만 슬라이싱
    df_kospi = fdr.StockListing('KOSPI')
    top_100 = df_kospi.head(100) # 시가총액 순서대로 상위 100개 추출
    
    for idx, row in top_100.iterrows():
        name, code = row['Name'], row['Code']
        
        tech_data = analyze_stock_details(code)
        if not tech_data: continue
        
        news_score = get_weekly_sentiment(name)
        final_score = round((news_score * 0.4) + (tech_data['tech_total'] * 0.6), 2)
        
        if final_score > 2.2: prediction = "🔥 강력추천"
        elif final_score > 0.8: prediction = "✅ 매수검토"
        elif final_score < -0.8: prediction = "⚠️ 주의"
        else: prediction = "👀 관망"

        stock_results.append({
            '종목명': name, '현재가': tech_data['curr_price'], 'AI 점수': final_score,
            '분석 결과': prediction, '심리도(RSI)': tech_data['rsi'], '뉴스 점수': news_score
        })
        print(f"✅ {name} 분석 중... ({idx+1}/100)")
        time.sleep(0.05)

    if stock_results:
        # 점수 높은 순으로 정렬 (토스 스타일 인기 순위)
        final_df = pd.DataFrame(stock_results)
        final_df = final_df.sort_values(by='AI 점수', ascending=False).reset_index(drop=True)
        final_df.insert(0, '순위', final_df.index + 1)
        
        save_name = 'Market_Top100_Ranking.xlsx'
        final_df.to_excel(save_name, index=False)
        
        # 상위 5위 브리핑
        top_msg = "🏆 코스피 상위 100대 기업 AI 랭킹\n"
        for i in range(5):
            top_msg += f"{i+1}위: {final_df['종목명'][i]} ({final_df['분석 결과'][i]})\n"
        
        send_telegram_msg(top_msg + "\n📊 전체 순위는 엑셀 파일을 확인하세요!", show_button=True)
        
        token = os.environ.get('TELEGRAM_TOKEN', '').strip()
        chat_id = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
        with open(save_name, 'rb') as f:
            requests.post(f"https://api.telegram.org/bot{token}/sendDocument", data={'chat_id': chat_id}, files={'document': f})
