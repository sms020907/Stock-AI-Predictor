import pandas as pd
import FinanceDataReader as fdr
import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime, timedelta
import os

# 1. 테마 정의
THEMES = {
    '반도체': ['삼성전자', 'SK하이닉스', '한미반도체', 'DB하이텍', '리노공업'],
    '이차전지': ['에코프로', '에코프로비엠', 'LG에너지솔루션', '포스코홀딩스', '삼성SDI'],
    '자동차': ['현대차', '기아', '현대모비스', '한온시스템'],
    '전력/구리': ['대한전선', 'LS', 'LS Electric', '효성중공업', 'HD현대일렉트릭'],
    '바이오': ['삼성바이오로직스', '셀트리온', '알테오젠', 'HLB']
}

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
        pos_words = ['상승', '호재', '매수', '돌파', '성장', '흑자', '수주', '긍정']
        neg_words = ['하락', '악재', '매도', '급락', '우려', '손실', '적자', '부정']
        for item in items[:10]:
            text = item.title.text
            for pw in pos_words: 
                if pw in text: score += 0.5
            for nw in neg_words: 
                if nw in text: score -= 0.5
    except: pass
    return score

# 2. 메인 분석 실행
print("🔍 [AI 투자 대시보드] 분석 시작...")
stock_results = []
try:
    df_list = fdr.StockListing('KOSPI')
    for theme, stocks in THEMES.items():
        for name in stocks:
            try:
                target = df_list[df_list['Name'] == name]
                if target.empty: continue
                code = target['Code'].values[0]
                df = fdr.DataReader(code, (datetime.now() - timedelta(days=20)).strftime('%Y-%m-%d'))
                curr_price = float(df['Close'].iloc[-1])
                daily_vol = df['Close'].pct_change().std() * 100 
                score = get_weekly_sentiment(name)
                expected_return = daily_vol * (score * 0.2)
                stock_results.append({
                    '테마': theme, '종목명': name, '현재가': int(curr_price),
                    '뉴스점수': score, '예상수익률': expected_return
                })
                print(f"✅ {name} 분석 완료")
            except: continue
            time.sleep(0.1)
except Exception as e:
    print(f"❌ 오류: {e}")

# 3. 저장 (GitHub 서버 경로에 직접 저장)
if stock_results:
    final_df = pd.DataFrame(stock_results)
    save_name = 'AI_predict_report.xlsx'
    # 절대 경로를 사용하지 않고 현재 작업 디렉토리에 바로 저장합니다.
    final_df.to_excel(save_name, index=False)
    print(f"\n✅ 리포트 생성 완료: {os.path.abspath(save_name)}")
else:
    print("\n❌ 결과가 없습니다.")
