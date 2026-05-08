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

def get_market_condition():
    """코스피 지수 자체가 하락장인지 확인 (시장 가중치)"""
    try:
        kospi = fdr.DataReader('KS11', (datetime.now() - timedelta(days=20)).strftime('%Y-%m-%d'))
        ma5 = kospi['Close'].rolling(window=5).mean()
        return 1.0 if ma5.iloc[-1] > ma5.iloc[-2] else 0.7 # 하락장이면 점수 30% 삭감
    except: return 1.0

def analyze_stock_ultimate(code, name):
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
    try:
        df = fdr.DataReader(code, start_date, end_date)
        if len(df) < 30: return None
        
        curr_price = df['Close'].iloc[-1]
        prev_price = df['Close'].iloc[-2]
        
        # 1. 수급 분석 (외국인/기관 순매수 확인)
        # FinanceDataReader의 종목별 투자자 데이터는 실시간성이 떨어질 수 있어 거래량과 가격변화로 대체 보완
        ma5 = df['Close'].rolling(window=5).mean()
        is_trend_up = ma5.iloc[-1] > ma5.iloc[-2]
        
        # 2. 거래량의 질 (상승 시 터진 거래량만 인정)
        avg_vol = df['Volume'].iloc[-20:-1].mean()
        curr_vol = df['Volume'].iloc[-1]
        vol_power = curr_vol / avg_vol
        
        vol_score = 0
        if curr_price > prev_price and vol_power > 1.5:
            vol_score = 2.0  # 상승하며 거래량 터짐 (세력 개입)
        elif curr_price < prev_price and vol_power > 1.5:
            vol_score = -2.5 # 하락하며 거래량 터짐 (패닉 셀 - 매우 위험)

        # 3. RSI 심리도 (과매도 반등 확인)
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rsi = 100 - (100 / (1 + (gain / loss).iloc[-1]))

        # --- 통합 점수 계산 (삼성SDS 같은 사례 완전 차단) ---
        score = 0
        
        # 하락 추세(5일선 하향)면 기본적으로 큰 감점
        if not is_trend_up:
            score -= 3.0
        
        # 바닥권(RSI < 35) 전략
        if rsi < 35:
            if is_trend_up: score += 2.0 # 반등 시작 시 가점
            else: score -= 2.0           # 하락 지속 시 추가 감점
            
        # 과열권(RSI > 75) 전략
        if rsi > 75: score -= 3.0 # 추격매수 방지
        
        score += vol_score # 거래량 점수 합산
        
        # 4. 정배열 보너스
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
        pos = ['상승', '호재', '수주', '흑자', '목표주가 상향', '최고 실적', '계약']
        neg = ['하락', '악재', '매도', '적자', '전망 하회', '논란', '과징금']
        for item in items[:12]:
            t = item.title.text
            for p in pos: 
                if p in t: score += 0.7
            for n in neg: 
                if n in t: score -= 0.8 # 악재에 더 민감하게 반응
    except: pass
    return score

if __name__ == "__main__":
    print("🎯 [AI 프로 트레이딩 모드] 분석을 시작합니다...")
    market_multiplier = get_market_condition() # 시장 지수 상태 가져오기
    results = []
    
    # 코스피 상위 100개 종목 스캔
    top_100 = fdr.StockListing('KOSPI').head(100)
    
    for idx, row in top_100.iterrows():
        name, code = row['Name'], row['Code']
        tech = analyze_stock_ultimate(code, name)
        if not tech: continue
        
        news = get_news_score(name)
        # 최종 점수 = (뉴스 30% + 기술 70%) * 시장 지수 가중치
        total = round(((news * 0.3) + (tech['score'] * 0.7)) * market_multiplier, 2)
        
        if total > 2.8: res_txt = "🚀 강력 매수 (세력 포착)"
        elif total > 1.2: res_txt = "✅ 매수 검토"
        elif total < -1.5: res_txt = "💀 매도 주의 (급락 위험)"
        else: res_txt = "👀 관망"

        results.append({
            '순위': 0, '종목명': name, '현재가': tech['price'], 'AI 점수': total,
            '분석결과': res_txt, '추세강도': tech['score'], 'RSI': tech['rsi'], 
            '거래량파워': tech['vol_power'], '뉴스점수': news
        })
        print(f"[{idx+1}/100] {name} 분석 완료 (지수 가중치 적용)")
        time.sleep(0.05)

    if results:
        df_final = pd.DataFrame(results).sort_values(by='AI 점수', ascending=False).reset_index(drop=True)
        df_final['순위'] = df_final.index + 1
        
        save_file = 'AI_Pro_Stock_Report.xlsx'
        df_final.to_excel(save_file, index=False)
        
        top5_msg = f"🏆 [AI 프로] 오늘의 인기 종목 TOP 5\n(시장 지수 가중치: {market_multiplier})\n\n"
        for i in range(min(5, len(df_final))):
            top5_msg += f"{i+1}위: {df_final['종목명'][i]} ({df_final['분석결과'][i]})\n"
        
        send_telegram_msg(top5_msg + "\n📊 상세 분석은 엑셀을 확인하세요!", show_button=True)
        
        token = os.environ.get('TELEGRAM_TOKEN', '').strip()
        chat_id = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
        with open(save_file, 'rb') as f:
            requests.post(f"https://api.telegram.org/bot{token}/sendDocument", data={'chat_id': chat_id}, files={'document': f})
