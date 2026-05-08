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
        
        # [예측력 강화 1] 5일 이동평균선의 방향 (추세 반전 확인)
        ma5 = df['Close'].rolling(window=5).mean()
        is_ma5_up = ma5.iloc[-1] > ma5.iloc[-2] # 5일선이 고개를 들었는가?
        
        # [예측력 강화 2] 거래량 필터 (평균 대비 거래량이 터져야 신뢰도 상승)
        avg_vol = df['Volume'].iloc[-20:-1].mean()
        curr_vol = df['Volume'].iloc[-1]
        vol_power = curr_vol / avg_vol
        
        # [예측력 강화 3] RSI 심리 지표
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rsi = 100 - (100 / (1 + (gain / loss).iloc[-1]))

        # --- AI 점수 산정 로직 (삼성SDS 필터링 적용) ---
        score = 0
        
        # RSI가 낮아도(과매도) 5일선이 하락 중이면 가점을 주지 않음 (떨어지는 칼날 방지)
        if rsi < 35:
            if is_ma5_up: score += 2.5  # 바닥 찍고 반등 시작
            else: score -= 1.0         # 아직 바닥 안 나옴 (감점)
            
        # RSI가 너무 높으면(과열) 무조건 감점
        if rsi > 70: score -= 2.0
        
        # 거래량이 평소보다 1.5배 이상 터지면 신뢰도 가점
        if vol_power > 1.5: score += 1.5
        
        # 단기 정배열 (5일 > 20일)
        ma20 = df['Close'].rolling(window=20).mean().iloc[-1]
        if ma5.iloc[-1] > ma20: score += 1.0

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
        pos = ['상승', '호재', '수주', '흑자', '목표주가 상향', '최대실적']
        neg = ['하락', '악재', '매도', '적자', '하회', '논란']
        for item in items[:10]:
            t = item.title.text
            for p in pos: 
                if p in t: score += 0.6
            for n in neg: 
                if n in t: score -= 0.6
    except: pass
    return score

if __name__ == "__main__":
    print("🏆 [전체 시장 인기 랭킹] AI 분석 가동...")
    results = []
    top_100 = fdr.StockListing('KOSPI').head(100)
    
    for idx, row in top_100.iterrows():
        name, code = row['Name'], row['Code']
        tech = analyze_stock_logic(code)
        if not tech: continue
        
        news = get_news_score(name)
        total = round((news * 0.3) + (tech['score'] * 0.7), 2)
        
        if total > 2.5: res_txt = "🔥 강력추천 (지금 사야 함)"
        elif total > 1.0: res_txt = "✅ 매수검토 (반등 시작)"
        elif total < -1.0: res_txt = "⚠️ 주의 (더 떨어짐)"
        else: res_txt = "👀 관망"

        results.append({
            '순위': 0, '종목명': name, '현재가': tech['price'], 'AI점수': total,
            '분석결과': res_txt, 'RSI': tech['rsi'], '거래량파워': tech['vol_power'], '뉴스점수': news
        })
        print(f"[{idx+1}/100] {name} 분석 완료")
        time.sleep(0.05)

    if results:
        df_final = pd.DataFrame(results).sort_values(by='AI점수', ascending=False).reset_index(drop=True)
        df_final['순위'] = df_final.index + 1
        
        save_file = 'AI_Market_Report.xlsx'
        df_final.to_excel(save_file, index=False)
        
        top5_msg = "🏆 AI 선정 오늘의 인기 종목 TOP 5\n"
        for i in range(5):
            top5_msg += f"{i+1}위: {df_final['종목명'][i]} ({df_final['분석결과'][i]})\n"
        
        send_telegram_msg(top5_msg + "\n📊 상세 순위는 엑셀 파일을 확인하세요!", show_button=True)
        
        token = os.environ.get('TELEGRAM_TOKEN', '').strip()
        chat_id = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
        with open(save_file, 'rb') as f:
            requests.post(f"https://api.telegram.org/bot{token}/sendDocument", data={'chat_id': chat_id}, files={'document': f})
