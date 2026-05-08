import pandas as pd
import FinanceDataReader as fdr
import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime, timedelta
import os
import json

def send_telegram_msg(msg, show_button=False):
    token = os.environ.get('TELEGRAM_TOKEN', '').strip()
    chat_id = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {'chat_id': chat_id, 'text': msg}
        if show_button:
            reply_markup = {"inline_keyboard": [[{"text": "🔄 다시 분석하기", "callback_data": "run_analysis"}]]}
            payload['reply_markup'] = json.dumps(reply_markup)
        try:
            requests.post(url, json=payload, timeout=10)
        except: pass

def analyze_stock_logic(code):
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=50)).strftime('%Y-%m-%d')
    try:
        df = fdr.DataReader(code, start_date, end_date)
        if len(df) < 30: return None
        
        curr_price = df['Close'].iloc[-1]
        
        # 1. 이동평균선 분석 (5일선 방향 확인)
        ma5 = df['Close'].rolling(window=5).mean()
        ma20 = df['Close'].rolling(window=20).mean().iloc[-1]
        # 5일선이 어제보다 높아야 '상승 추세 전환'으로 인정
        is_trend_up = ma5.iloc[-1] > ma5.iloc[-2]
        
        # 2. 거래량 파워 (20일 평균 대비 오늘 거래량)
        avg_vol = df['Volume'].iloc[-20:-1].mean()
        curr_vol = df['Volume'].iloc[-1]
        vol_power = curr_vol / avg_vol
        
        # 3. RSI 심리 지표
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rsi = 100 - (100 / (1 + (gain / loss).iloc[-1]))

        # --- 삼성에스디에스(하락 칼날) 방지 로직 ---
        score = 0
        
        # 조건 A: 주가가 바닥권(RSI < 35)일 때
        if rsi < 35:
            if is_trend_up and vol_power > 1.2:
                score += 3.0  # 추세가 상승으로 꺾이고 거래량이 실릴 때만 '진짜 반등'
            else:
                score -= 4.0  # 5일선이 하락 중이면 "지하가 더 있음"으로 판단, 대폭 감점!

        # 조건 B: 주가가 과열권(RSI > 70)일 때
        if rsi > 70:
            score -= 2.5 # 추격 매수 방지

        # 조건 C: 거래량이 실린 상승 확인
        if is_trend_up and vol_power > 1.5:
            score += 1.5
            
        # 조건 D: 5일선이 20일선 위에 있는 정배열 상태
        if ma5.iloc[-1] > ma20:
            score += 1.0

        return {'price': int(curr_price), 'rsi': round(rsi, 1), 'score': score, 'vol_power': round(vol_power, 2)}
    except: return None

def get_news_score(name):
    query = f"{name} after:{(datetime.now()-timedelta(days=7)).strftime('%Y-%m-%d')}"
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    score = 0
    try:
        res = requests.get(url, timeout=7)
        soup = BeautifulSoup(res.content, 'xml')
        items = soup.find_all('item')
        pos = ['상승', '호재', '수주', '흑자', '최고', '상향']
        neg = ['하락', '악재', '매도', '적자', '하회', '우려']
        for item in items[:10]:
            t = item.title.text
            for p in pos: 
                if p in t: score += 0.5
            for n in neg: 
                if n in t: score -= 0.5
    except: pass
    return score

if __name__ == "__main__":
    print("🚀 [최종 보완판] 코스피 100 순위 분석 시작...")
    results = []
    top_100 = fdr.StockListing('KOSPI').head(100)
    
    for idx, row in top_100.iterrows():
        name, code = row['Name'], row['Code']
        tech = analyze_stock_logic(code)
        if not tech: continue
        
        news = get_news_score(name)
        # 기술적 추세 점수 비중을 높여서 '차트'가 안 좋으면 뉴스 좋아도 탈락시킴
        total = round((news * 0.3) + (tech['score'] * 0.7), 2)
        
        if total > 2.5: res_txt = "🔥 강력추천 (추세반전)"
        elif total > 1.0: res_txt = "✅ 매수검토"
        elif total < -1.0: res_txt = "⚠️ 매도주의 (하락지속)"
        else: res_txt = "👀 관망"

        results.append({
            '순위': 0, '종목명': name, '현재가': tech['price'], 'AI점수': total,
            '분석결과': res_txt, 'RSI': tech['rsi'], '거래량파워': tech['vol_power'], '뉴스점수': news
        })
        print(f"[{idx+1}/100] {name} 분석 완료")
        time.sleep(0.05)

    if results:
        # AI 점수 순으로 인기 차트 정렬
        df_final = pd.DataFrame(results).sort_values(by='AI점수', ascending=False).reset_index(drop=True)
        df_final['순위'] = df_final.index + 1
        
        save_file = 'AI_Market_Rank_Final.xlsx'
        df_final.to_excel(save_file, index=False)
        
        top5_msg = "🏆 AI 선정 오늘의 인기 종목 TOP 5\n"
        for i in range(min(5, len(df_final))):
            top5_msg += f"{i+1}위: {df_final['종목명'][i]} ({df_final['분석결과'][i]})\n"
        
        send_telegram_msg(top5_msg + "\n📊 상세 분석 결과는 엑셀을 확인하세요!", show_button=True)
        
        token = os.environ.get('TELEGRAM_TOKEN', '').strip()
        chat_id = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
        with open(save_file, 'rb') as f:
            requests.post(f"https://api.telegram.org/bot{token}/sendDocument", data={'chat_id': chat_id}, files={'document': f})
