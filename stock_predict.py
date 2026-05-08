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

def analyze_stock_ultimate(code):
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
    try:
        df = fdr.DataReader(code, start_date, end_date)
        if len(df) < 30: return None
        
        curr_price = df['Close'].iloc[-1]
        prev_price = df['Close'].iloc[-2]
        
        # [추가] 실제 등락률 계산
        change_rate = round(((curr_price - prev_price) / prev_price) * 100, 2)
        
        # 1. 추세 분석 (5일선)
        ma5 = df['Close'].rolling(window=5).mean()
        is_trend_up = ma5.iloc[-1] > ma5.iloc[-2]
        
        # 2. 거래량의 질 (상승 시 거래량만 인정)
        avg_vol = df['Volume'].iloc[-20:-1].mean()
        curr_vol = df['Volume'].iloc[-1]
        vol_power = curr_vol / avg_vol
        
        vol_score = 0
        if change_rate > 0 and vol_power > 1.5:
            vol_score = 2.0  # 상승하며 거래량 터짐
        elif change_rate < 0 and vol_power > 1.5:
            vol_score = -3.0 # 하락하며 거래량 터짐 (매우 위험)

        # 3. RSI 심리도
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rsi = 100 - (100 / (1 + (gain / loss).iloc[-1]))

        # --- 점수 산정 (하락 종목 필터 강화) ---
        score = 0
        if not is_trend_up: score -= 3.5  # 하락 추세면 대폭 감점
        
        if rsi < 35:
            if is_trend_up: score += 2.5
            else: score -= 2.5 # 바닥 같아도 하락 중이면 감점
            
        score += vol_score
        
        return {
            'price': int(curr_price), 
            'change': change_rate, 
            'rsi': round(rsi, 1), 
            'score': score, 
            'vol_power': round(vol_power, 2)
        }
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
        neg = ['하락', '악재', '매도', '적자', '하회', '과징금', '리스크']
        for item in items[:10]:
            t = item.title.text
            for p in pos: 
                if p in t: score += 0.6
            for n in neg: 
                if n in t: score -= 0.8
    except: pass
    return score

if __name__ == "__main__":
    print("🚀 [실전 대조 모드] 코스피 100 분석 및 등락률 추출 시작...")
    results = []
    top_100 = fdr.StockListing('KOSPI').head(100)
    
    for idx, row in top_100.iterrows():
        name, code = row['Name'], row['Code']
        tech = analyze_stock_ultimate(code)
        if not tech: continue
        
        news = get_news_score(name)
        total = round((news * 0.3) + (tech['score'] * 0.7), 2)
        
        if total > 2.5: res_txt = "🔥 강력추천"
        elif total > 1.0: res_txt = "✅ 매수검토"
        elif total < -1.5: res_txt = "💀 매도주의"
        else: res_txt = "👀 관망"

        results.append({
            '순위': 0, '종목명': name, '현재가': tech['price'], 
            '등락률(%)': tech['change'],  # [핵심] 실제 상승/하락률 추가
            'AI점수': total, '분석결과': res_txt, 
            'RSI': tech['rsi'], '거래량파워': tech['vol_power'], '뉴스점수': news
        })
        print(f"[{idx+1}/100] {name} 분석 완료")
        time.sleep(0.05)

    if results:
        df_final = pd.DataFrame(results).sort_values(by='AI점수', ascending=False).reset_index(drop=True)
        df_final['순위'] = df_final.index + 1
        
        save_file = 'AI_Market_Verification_Report.xlsx'
        df_final.to_excel(save_file, index=False)
        
        # 텔레그램 메시지에 상위 종목의 등락률도 표시
        top5_msg = "🏆 AI 추천 종목 (오늘의 실제 등락률)\n"
        for i in range(min(5, len(df_final))):
            top5_msg += f"{i+1}위: {df_final['종목명'][i]} ({df_final['등락률(%)'][i]}%)\n"
        
        send_telegram_msg(top5_msg + "\n📊 상세 데이터(등락률 포함)는 엑셀을 확인하세요!", show_button=True)
        
        token = os.environ.get('TELEGRAM_TOKEN', '').strip()
        chat_id = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
        with open(save_file, 'rb') as f:
            requests.post(f"https://api.telegram.org/bot{token}/sendDocument", data={'chat_id': chat_id}, files={'document': f})
