import pandas as pd
import FinanceDataReader as fdr
import requests
from bs4 import BeautifulSoup
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
        pos_words = ['상승', '호재', '매수', '돌파', '성장', '흑자', '최고']
        neg_words = ['하락', '악재', '매도', '급락', '우려', '적자', '최저']
        for item in items[:10]:
            text = item.title.text
            for pw in pos_words: 
                if pw in text: score += 0.8
            for nw in neg_words: 
                if nw in text: score -= 0.8
    except: pass
    return round(score, 2)

def send_telegram(file_path):
    token = os.environ.get('TELEGRAM_TOKEN', '').strip()
    chat_id = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
    if not token or not chat_id: return

    try:
        msg = f"📊 [{datetime.now().strftime('%m/%d')}] KOSPI TOP 100 AI 분석 리포트가 완료되었습니다."
        requests.get(f"https://api.telegram.org/bot{token}/sendMessage", params={'chat_id': chat_id, 'text': msg})
        with open(file_path, 'rb') as f:
            requests.post(f"https://api.telegram.org/bot{token}/sendDocument", data={'chat_id': chat_id}, files={'document': f})
        print("✅ 텔레그램 발송 완료")
    except Exception as e:
        print(f"❌ 전송 실패: {e}")

# 메인 로직 시작
try:
    print("🚀 KOSPI 상위 100개 종목 수집 중...")
    df_kospi = fdr.StockListing('KOSPI')
    # 시가총액 순 정렬 후 상위 100개 추출 (FinanceDataReader 버전에 따라 'MarCap' 또는 'Stocks' 기준)
    top_100 = df_kospi.head(100)
    
    final_data = []
    for idx, row in top_100.iterrows():
        name = row['Name']
        code = row['Code']
        try:
            # 주가 데이터 수집
            df = fdr.DataReader(code, (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d'))
            curr_price = int(df['Close'].iloc[-1])
            prev_price = int(df['Close'].iloc[-2])
            change_percent = round(((curr_price - prev_price) / prev_price) * 100, 2)
            
            # 뉴스 분석 점수
            sentiment_score = get_weekly_sentiment(name)
            
            # 예측 로직 (단순 AI 모델 예시: 전일 변동성과 뉴스 점수 결합)
            # 뉴스 점수가 높고 최근 기세가 좋으면 '상승 예상'
            prediction_val = round((change_percent * 0.3) + (sentiment_score * 0.7), 2)
            prediction = "상승 우세" if prediction_val > 0.5 else "하락 우세" if prediction_val < -0.5 else "보합 예상"

            final_data.append({
                '순위': len(final_data) + 1,
                '종목명': name,
                '현재가': curr_price,
                '전일대비(%)': change_percent,
                '뉴스점수': sentiment_score,
                'AI예측점수': prediction_val,
                '다음날전망': prediction
            })
            print(f"[{len(final_data)}/100] {name} 분석 완료")
        except:
            continue

    if final_data:
        save_name = 'KOSPI_TOP100_AI_Report.xlsx'
        pd.DataFrame(final_data).to_excel(save_name, index=False)
        send_telegram(save_name)
        
except Exception as e:
    print(f"🔥 치명적 에러: {e}")
