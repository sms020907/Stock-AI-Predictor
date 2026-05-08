import pandas as pd
import FinanceDataReader as fdr
import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime, timedelta
import os
import json

# 1. 테마 및 분석 종목 정의 
THEMES = {
    '반도체': ['삼성전자', 'SK하이닉스', '한미반도체', 'DB하이텍', '리노공업'],
    '이차전지': ['에코프로', '에코프로비엠', 'LG에너지솔루션', '포스코홀딩스', '삼성SDI'],
    '자동차': ['현대차', '기아', '현대모비스', '한온시스템'],
    '전력/구리': ['대한전선', 'LS', 'LS Electric', '효성중공업', 'HD현대일렉트릭'],
    '바이오': ['삼성바이오로직스', '셀트리온', '알테오젠', 'HLB']
}

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

def analyze_stock_details(code):
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=40)).strftime('%Y-%m-%d')
    try:
        df = fdr.DataReader(code, start_date, end_date)
        if len(df) < 25: return None
        curr_price = df['Close'].iloc[-1]
        
        # 이동평균선 정배열 (단기 추세 확인)
        ma5 = df['Close'].rolling(window=5).mean().iloc[-1]
        ma20 = df['Close'].rolling(window=20).mean().iloc[-1]
        trend_score = 1.0 if ma5 > ma20 else -0.5
        
        # 거래량 분석 (최근 5일 평균 대비 1.5배 터졌는가?)
        avg_volume = df['Volume'].iloc[-6:-1].mean()
        curr_volume = df['Volume'].iloc[-1]
        vol_score = 1.2 if curr_volume > avg_volume * 1.5 else 0
        
        # RSI (과매수 구간에서 점수 감점 로직 적용)
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs.iloc[-1]))
        
        rsi_score = 0
        if rsi < 35: rsi_score = 2.0  # 바닥권
        if rsi > 70: rsi_score = -2.5 # 과열권 (SK스퀘어 같은 급락 방지)
        
        return {'curr_price': int(curr_price), 'rsi': round(rsi, 1), 'tech_total': trend_score + vol_score + rsi_score}
    except: return None

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
        for item in items[:15]:
            text = item.title.text
            for pw in pos_words: 
                if pw in text: score += 0.5
            for nw in neg_words: 
                if nw in text: score -= 0.5
    except: pass
    return score

if __name__ == "__main__":
    print("🔍 [AI 인기 종목 차트] 분석 및 순위 산정을 시작합니다...")
    stock_results = []
    df_list = fdr.StockListing('KOSPI')
    
    for theme, stocks in THEMES.items():
        for name in stocks:
            target = df_list[df_list['Name'] == name]
            if target.empty: continue
            code = target['Code'].values[0]
            
            tech_data = analyze_stock_details(code)
            if not tech_data: continue
            
            news_score = get_weekly_sentiment(name)
            # 뉴스(40%) + 기술/수급(60%) 반영
            final_score = round((news_score * 0.4) + (tech_data['tech_total'] * 0.6), 2)
            
            # 토스 스타일 결과 문구
            if final_score > 2.2: prediction = "🔥 강력추천"
            elif final_score > 0.8: prediction = "✅ 매수검토"
            elif final_score < -0.8: prediction = "⚠️ 주의"
            else: prediction = "👀 관망"

            stock_results.append({
                '종목명': name, '현재가': tech_data['curr_price'], 'AI 종합점수': final_score,
                '분석 결과': prediction, '심리도(RSI)': tech_data['rsi'], '뉴스 호재성': news_score, '테마': theme
            })
            time.sleep(0.05)

    if stock_results:
        # 2. [토스 스타일 핵심] 점수 높은 순으로 정렬 
        final_df = pd.DataFrame(stock_results)
        final_df = final_df.sort_values(by='AI 종합점수', ascending=False).reset_index(drop=True)
        final_df.insert(0, '순위', final_df.index + 1)
        
        save_name = 'AI_Popular_Stock_Ranking.xlsx'
        final_df.to_excel(save_name, index=False)
        
        # 3. 텔레그램 인기 차트 브리핑
        top_msg = "🏆 실시간 AI 인기 종목 TOP 5\n"
        for i in range(min(5, len(final_df))):
            top_msg += f"{i+1}위: {final_df['종목명'][i]} ({final_df['분석 결과'][i]})\n"
        
        top_msg += "\n📊 상세 분석 리포트를 확인해 보세요!"
        send_telegram_msg(top_msg, show_button=True)
        
        # 엑셀 파일 전송
        token = os.environ.get('TELEGRAM_TOKEN', '').strip()
        chat_id = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
        with open(save_name, 'rb') as f:
            requests.post(f"https://api.telegram.org/bot{token}/sendDocument", data={'chat_id': chat_id}, files={'document': f})
