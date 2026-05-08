import pandas as pd
import FinanceDataReader as fdr
import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime, timedelta
import os

# [추가] 수급 및 거래량 분석을 포함한 기술적 분석 함수
def analyze_stock_details(code, name):
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=40)).strftime('%Y-%m-%d')
    
    try:
        # 주가 데이터 가져오기
        df = fdr.DataReader(code, start_date, end_date)
        if len(df) < 25: return None
        
        curr_price = df['Close'].iloc[-1]
        prev_price = df['Close'].iloc[-2]
        
        # 1. 이동평균선 정배열 확인 (5일선 > 20일선)
        ma5 = df['Close'].rolling(window=5).mean().iloc[-1]
        ma20 = df['Close'].rolling(window=20).mean().iloc[-1]
        trend_score = 1.0 if ma5 > ma20 else -0.5
        
        # 2. 거래량 분석 (최근 5일 평균 대비 오늘 거래량이 터졌는가?)
        avg_volume = df['Volume'].iloc[-6:-1].mean()
        curr_volume = df['Volume'].iloc[-1]
        vol_score = 1.0 if curr_volume > avg_volume * 1.5 else 0
        
        # 3. RSI(심리도) - 과매수 구간(70 이상)이면 오히려 점수 깎기
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs.iloc[-1]))
        
        rsi_score = 0
        if rsi < 35: rsi_score = 2.0  # 과매도 (기회)
        if rsi > 70: rsi_score = -2.0 # 과매수 (위험) - SK스퀘어 같은 사례 방지
        
        return {
            'curr_price': int(curr_price),
            'rsi': round(rsi, 1),
            'tech_total': trend_score + vol_score + rsi_score,
            'vol_up': True if curr_volume > avg_volume * 1.2 else False
        }
    except:
        return None

def get_weekly_sentiment(name):
    # (기존 뉴스 분석 함수와 동일)
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

# 메인 실행부 (생략된 테마 정의 등은 기존과 동일)
# ... (THEMES 정의 부분) ...

if __name__ == "__main__":
    print("🔍 [개선된 AI 투자 분석] 수급 및 추세 분석을 시작합니다...")
    stock_results = []
    df_list = fdr.StockListing('KOSPI')
    
    for theme, stocks in THEMES.items():
        for name in stocks:
            target = df_list[df_list['Name'] == name]
            if target.empty: continue
            code = target['Code'].values[0]
            
            # 기술적 분석 + 뉴스 분석 결합
            tech_data = analyze_stock_details(code, name)
            if not tech_data: continue
            
            news_score = get_weekly_sentiment(name)
            
            # 최종 AI 점수 계산 (뉴스 40% + 기술/수급 60%)
            final_score = round((news_score * 0.4) + (tech_data['tech_total'] * 0.6), 2)
            
            # 필터링 강화: 점수가 아주 높거나 거래량이 동반된 경우만 추천
            prediction = "관망"
            if final_score > 2.0: prediction = "강력 매수"
            elif final_score > 0.8: prediction = "매수 우세"
            elif final_score < -0.5: prediction = "매도 주의"

            stock_results.append({
                '테마': theme, '종목명': name, '현재가': tech_data['curr_price'],
                'RSI': tech_data['rsi'], '뉴스점수': news_score, 
                '종합점수': final_score, '최종전망': prediction
            })
            print(f"✅ {name} 분석 완료 (점수: {final_score})")
            time.sleep(0.1)

    # 엑셀 저장 로직 (기존과 동일)
    if stock_results:
        pd.DataFrame(stock_results).to_excel('AI_predict_report.xlsx', index=False)
