import pandas as pd
import finance_datareader as fdr  # 라이브러리명을 소문자로 수정하여 에러 방지
import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime, timedelta
import os

# 1. 테마 정의 (필요시 종목 추가/수정 가능)
THEMES = {
    '반도체': ['삼성전자', 'SK하이닉스', '한미반도체', 'DB하이텍', '리노공업'],
    '이차전지': ['에코프로', '에코프로비엠', 'LG에너지솔루션', '포스코홀딩스', '삼성SDI'],
    '자동차': ['현대차', '기아', '현대모비스', '한온시스템'],
    '전력/구리': ['대한전선', 'LS', 'LS Electric', '효성중공업', 'HD현대일렉트릭'],
    '바이오': ['삼성바이오로직스', '셀트리온', '알테오젠', 'HLB']
}

def get_weekly_sentiment(name):
    """최근 7일간의 뉴스 긍정/부정 점수 분석"""
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

def send_telegram_msg(file_path):
    """분석 완료 메시지와 엑셀 파일을 텔레그램으로 전송"""
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    
    if token and chat_id:
        try:
            # 1. 메시지 전송
            msg = "📢 [AI 투자 대시보드] 분석이 완료되었습니다!\n상세 내용은 첨부된 엑셀 리포트를 확인하세요. 🚀"
            requests.get(f"https://api.telegram.org/bot{token}/sendMessage?chat_id={chat_id}&text={msg}")
            
            # 2. 파일 전송
            with open(file_path, 'rb') as f:
                requests.post(f"https://api.telegram.org/bot{token}/sendDocument", 
                              data={'chat_id': chat_id}, files={'document': f})
            print("✅ 텔레그램 전송 성공!")
        except Exception as e:
            print(f"❌ 텔레그램 전송 중 오류 발생: {e}")
    else:
        print("⚠️ 텔레그램 설정(Token/ID)을 찾을 수 없어 전송을 건너뜁니다.")

# 2. 메인 분석 실행
print("🔍 [AI 투자 대시보드] 분석 시작...")
stock_results = []

try:
    # 코스피 종목 리스트 가져오기
    df_list = fdr.StockListing('KOSPI')
    
    for theme, stocks in THEMES.items():
        for name in stocks:
            try:
                target = df_list[df_list['Name'] == name]
                if target.empty: continue
                code = target['Code'].values[0]
                
                # 주가 데이터 수집 (최근 20일)
                df = fdr.DataReader(code, (datetime.now() - timedelta(days=20)).strftime('%Y-%m-%d'))
                curr_price = float(df['Close'].iloc[-1])
                daily_vol = df['Close'].pct_change().std() * 100 
                
                # 뉴스 분석 점수
                score = get_weekly_sentiment(name)
                
                # 예상 수익률 계산 (단순 로직)
                expected_return = daily_vol * (score * 0.2)
                
                stock_results.append({
                    '테마': theme,
                    '종목명': name,
                    '현재가': int(curr_price),
                    '뉴스점수': score,
                    '예상수익률': expected_return
                })
                print(f"✅ {name} 분석 완료")
            except: continue
            time.sleep(0.1)

    # 3. 데이터 저장 및 전송
    if stock_results:
        final_df = pd.DataFrame(stock_results)
        save_name = 'AI_predict_report.xlsx'
        
        # 엑셀 저장
        final_df.to_excel(save_name, index=False)
        print(f"\n✅ 리포트 생성 완료: {os.path.abspath(save_name)}")
        
        # 텔레그램 전송 호출
        send_telegram_msg(save_name)
    else:
        print("\n❌ 분석 결과가 없어 리포트를 생성하지 못했습니다.")

except Exception as e:
    print(f"\n❌ 실행 중 치명적 에러 발생: {e}")
