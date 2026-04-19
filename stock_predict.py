import pandas as pd
import FinanceDataReader as fdr
import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime, timedelta
import os

def get_weekly_sentiment(name):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    query = f"{name} after:{start_date.strftime('%Y-%m-%d')}"
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    score = 0
    try:
        res = requests.get(url, timeout=10)
        soup = BeautifulSoup(res.content, 'xml')
        items = soup.find_all('item')
        pos_words = ['상승', '호재', '매수', '돌파', '성장', '흑자']
        neg_words = ['하락', '악재', '매도', '급락', '우려', '적자']
        for item in items[:10]:
            text = item.title.text
            for pw in pos_words: 
                if pw in text: score += 0.5
            for nw in neg_words: 
                if nw in text: score -= 0.5
    except: pass
    return score

def send_telegram(file_path):
    token = os.environ.get('TELEGRAM_TOKEN', '').strip()
    chat_id = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
    if token and chat_id:
        try:
            msg = "📢 [AI 투자 리포트] 분석이 완료되었습니다!"
            requests.get(f"https://api.telegram.org/bot{token}/sendMessage", 
                         params={'chat_id': chat_id, 'text': msg}, timeout=10)
            with open(file_path, 'rb') as f:
                requests.post(f"https://api.telegram.org/bot{token}/sendDocument", 
                              data={'chat_id': chat_id}, files={'document': f}, timeout=20)
            print("✅ 텔레그램 전송 완료")
        except Exception as e:
            print(f"❌ 전송 중 에러: {e}")

THEMES = {
    '반도체': ['삼성전자', 'SK하이닉스', '한미반도체'],
    '이차전지': ['에코프로', 'LG에너지솔루션', '포스코홀딩스'],
    '자동차': ['현대차', '기아'],
    '항공/우주': ['대한항공', '한국항공우주', '한화에어로스페이스'],
    '바이오': ['삼성바이오로직스', '셀트리온'],
    'AI/로봇': ['네이버', '두산로보틱스']
}

stock_results = []
try:
    df_list = fdr.StockListing('KOSPI')
    for theme, stocks in THEMES.items():
        for name in stocks:
            try:
                target = df_list[df_list['Name'] == name]
                if target.empty: continue
                code = target['Code'].values[0]
                df = fdr.DataReader(code, (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d'))
                curr_price = int(df['Close'].iloc[-1])
                score = get_weekly_sentiment(name)
                stock_results.append({'테마': theme, '종목명': name, '현재가': curr_price, '뉴스점수': score})
                print(f"✅ {name} 완료")
            except: continue

    if stock_results:
        save_name = 'AI_predict_report.xlsx'
        pd.DataFrame(stock_results).to_excel(save_name, index=False)
        send_telegram(save_name)
except Exception as e:
    print(f"🔥 에러 발생: {e}")
