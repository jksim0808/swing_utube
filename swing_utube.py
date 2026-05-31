import streamlit as st
import pandas as pd
import requests
import io
from datetime import datetime, timedelta, timezone
import FinanceDataReader as fdr
from bs4 import BeautifulSoup

# =============================================================================
# [설정] 기본 셋팅 (쇼츠 세로 화면)
# =============================================================================
st.set_page_config(layout="centered", page_title="오늘의 핫스윙 Top 10")

# 📱 10개 꽉 차는 랭킹 보드용 커스텀 CSS
st.markdown("""
<style>
    /* 전체 배경을 어둡게 설정 */
    .stApp { background-color: #0E1117; }
    
    /* 요소들 간격 좁히기 */
    .block-container { padding-top: 2rem; padding-bottom: 0rem; max-width: 900px; }
    
    /* 타이틀 스타일 */
    .shorts-title { font-size: 65px; font-weight: 900; color: #FF4B4B; text-align: center; margin-bottom: 10px; line-height: 1.2; }
    .shorts-subtitle { font-size: 35px; color: #AAAAAA; text-align: center; margin-bottom: 40px; }
    
    /* Top 10 리스트 행(Row) 스타일 */
    .stock-row { 
        display: flex; align-items: center; justify-content: space-between; 
        background-color: #1A1C23; padding: 25px 30px; margin-bottom: 15px; 
        border-radius: 15px; border-left: 10px solid #FF4B4B; 
    }
    
    .rank-text { font-size: 50px; font-weight: 900; color: #FF4B4B; width: 80px; }
    
    /* 종목명 & 상태 묶음 */
    .info-group { flex-grow: 1; display: flex; flex-direction: column; justify-content: center; }
    .stock-name { font-size: 45px; font-weight: 900; color: #FFFFFF; margin-bottom: 5px; line-height: 1.1; }
    .status-badge { font-size: 26px; color: #FF9900; font-weight: bold; }
    
    /* 수익률 텍스트 */
    .yield-text { font-size: 45px; font-weight: 900; color: #00FF00; text-align: right; }
    
    /* AI 성우 대본 영역 */
    .script-box { 
        background-color: #1E1E1E; padding: 30px; border-radius: 15px; 
        margin-top: 40px; font-size: 32px; color: #E0E0E0; line-height: 1.6; border: 2px dashed #555;
    }
</style>
""", unsafe_allow_html=True)

KST = timezone(timedelta(hours=9))

# =============================================================================
# 1 & 2 & 3. 데이터 수집 및 분석 알고리즘 (기존 로직 완벽 동일)
# =============================================================================
@st.cache_data(ttl=3600*12)
def get_krx_info():
    df = fdr.StockListing('KRX')
    return df[['Name', 'Code', 'Marcap']].set_index('Name')

@st.cache_data(ttl=300)
def get_naver_top_universe():
    headers = {'User-Agent': 'Mozilla/5.0'}
    krx_info = get_krx_info()
    df_list = []
    for sosok in [0, 1]:
        url = f"https://finance.naver.com/sise/sise_quant.naver?sosok={sosok}"
        try:
            res = requests.get(url, headers=headers, timeout=5)
            res.encoding = 'euc-kr'
            dfs = pd.read_html(io.StringIO(res.text))
            df = dfs[1].dropna(how='all') 
            df = df[['종목명', '현재가', '전일비', '등락률', '거래량', '거래대금']]
            df_list.append(df)
        except: continue
    if not df_list: return pd.DataFrame()
    full_df = pd.concat(df_list, ignore_index=True)
    for col in ['현재가', '거래량', '거래대금']:
        full_df[col] = pd.to_numeric(full_df[col].astype(str).str.replace(',', ''), errors='coerce')
    full_df['등락률'] = pd.to_numeric(full_df['등락률'].astype(str).str.replace('%', ''), errors='coerce')
    pattern = '|'.join(['KODEX', 'TIGER', 'KBSTAR', 'ACE', 'ARIRANG', 'HANARO', 'KOSEF', 'SOL', 'TIMEFOLIO', 'WOORI', '스팩', 'ETN', '제\d+호', '우$'])
    full_df = full_df[~full_df['종목명'].str.contains(pattern, case=False, regex=True)]
    full_df = full_df[full_df['현재가'] >= 10000]
    full_df['종목코드'] = full_df['종목명'].map(krx_info['Code'])
    full_df['시가총액'] = full_df['종목명'].map(krx_info['Marcap'])
    full_df = full_df.dropna(subset=['종목코드', '시가총액'])
    full_df = full_df[full_df['시가총액'] >= 100000000000]
    return full_df.sort_values(by='거래대금', ascending=False).head(100).reset_index(drop=True)

def get_fundamentals_and_news(code):
    headers = {'User-Agent': 'Mozilla/5.0'}
    target_price, news_status = "N/A", "☁️ 보통"
    try:
        url_main = f"https://finance.naver.com/item/main.naver?code={code}"
        res_main = requests.get(url_main, headers=headers, timeout=5)
        soup_main = BeautifulSoup(res_main.text, 'html.parser')
        cns_eps = soup_main.select_one('#_step_bank_cns')
        if cns_eps: target_price = cns_eps.text.strip().replace(',', '')
        url_news = f"https://finance.naver.com/item/news_news.naver?code={code}&page=1"
        res_news = requests.get(url_news, headers=headers, timeout=5)
        soup_news = BeautifulSoup(res_news.content.decode('euc-kr', 'replace'), 'html.parser')
        titles = soup_news.select('.title a')
        pos_words = ['상승', '급등', '수주', '흑자', '돌파', '호실적', '성장', '최대', 'MOU', '계약', '기대', '강세', '수혜']
        neg_words = ['하락', '급락', '적자', '우려', '매도', '악재', '위기', '감소', '부진', '소송', '폭락', '약세', '쇼크']
        score = 0
        for title in titles[:10]:
            text = title.text
            if any(word in text for word in pos_words): score += 1
            if any(word in text for word in neg_words): score -= 1
        if score >= 2: news_status = "🔥 호재 우세"
        elif score <= -2: news_status = "❄️ 악재 우세"
        else: news_status = "☁️ 특징 없음"
    except: pass
    return target_price, news_status

def analyze_swing_probability(ticker, is_mega_cap=False, days=60):
    end_date = datetime.now(KST)
    start_date = end_date - timedelta(days=days)
    try:
        df = fdr.DataReader(ticker, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
        if len(df) < 20: return 0, "데이터 부족", pd.DataFrame(), 0, 0
        df = df.reset_index()
        df.rename(columns={'Date': '날짜', 'Open': '시가', 'High': '고가', 'Low': '저가', 'Close': '종가', 'Volume': '거래량'}, inplace=True)
        df['MA5'] = df['종가'].rolling(window=5).mean()
        df['MA20'] = df['종가'].rolling(window=20).mean()
        df['Vol_MA5'] = df['거래량'].rolling(window=5).mean()
        current_price = df['종가'].iloc[-1]
        current_vol = df['거래량'].iloc[-1]
        ma20 = df['MA20'].iloc[-1]
        highest_price = df['고가'].max()
        target_yield = ((highest_price - current_price) / current_price) * 100
        score = 40 
        status = "▪️ 관망"
        surge_ratio = 1.03 if is_mega_cap else 1.05
        vol_ratio = 2.0 if is_mega_cap else 3.0
        df['is_bull'] = (df['종가'] > df['시가'] * surge_ratio) & (df['거래량'] > df['Vol_MA5'].shift(1) * vol_ratio)
        recent_bull = df.iloc[-20:][df.iloc[-20:]['is_bull'] == True]
        
        if not recent_bull.empty:
            score += 25 
            if ma20 * 0.98 <= current_price <= ma20 * 1.05:
                score += 15
                status = "🟡 지지선 근접"
                if current_vol < df['Vol_MA5'].iloc[-2] * 0.6:
                    score += 20
                    status = "🎯 S급 눌림목"
            elif current_price > ma20 * 1.10:
                score += 5
                status = "🔥 급등 진행형"
        else:
            if current_price < ma20:
                score -= 20
                status = "📉 추세 이탈"
        return min(99, score), status, df, highest_price, target_yield
    except:
        return 0, "에러", pd.DataFrame(), 0, 0

@st.cache_data(ttl=300, show_spinner=False)
def get_fully_analyzed_data(universe_df):
    results = []
    for i, row in universe_df.iterrows():
        code, name = row['종목코드'], row['종목명']
        marcap_100m = int(row['시가총액'] / 100000000)
        score, status, _, high_price, target_yield = analyze_swing_probability(code, is_mega_cap=(marcap_100m >= 100000))
        if score > 0:
            results.append({
                "상태": status, "점수": score, "종목명": name, 
                "현재가": row['현재가'], "전고점 기대수익(%)": target_yield
            })
    return results


# =============================================================================
# 4. 메인 화면 렌더링 (🔥 Top 10 랭킹 보드 UI)
# =============================================================================
universe_df = get_naver_top_universe()

if not universe_df.empty:
    with st.spinner("🔄 데이터 분석 중... (약 20초 소요)"):
        results = get_fully_analyzed_data(universe_df)
    
    if results:
        # 점수가 가장 높은 10개 종목 추출
        top_10_df = pd.DataFrame(results).sort_values(by="점수", ascending=False).head(10)
        
        # ---------------------------------------------------------
        # [화면 상단] 어그로 타이틀
        # ---------------------------------------------------------
        st.markdown(f'<div class="shorts-title">🚨 AI 포착 스윙 TOP 10</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="shorts-subtitle">거래대금 상위 100종목 알고리즘 분석 완료</div>', unsafe_allow_html=True)
        
        # ---------------------------------------------------------
        # [화면 중단] 10개 종목 리스트 렌더링 (차트 제거됨)
        # ---------------------------------------------------------
        top_10_names = [] # 대본 생성을 위해 이름 모아두기

        for i, row in top_10_df.reset_index(drop=True).iterrows():
            rank = i + 1
            t_name = row['종목명']
            t_status = row['상태']
            t_yield = row['전고점 기대수익(%)']
            
            top_10_names.append(t_name)
            
            # 각각의 종목을 하나의 깔끔한 바(Bar) 형태로 렌더링
            st.markdown(f'''
            <div class="stock-row">
                <div class="rank-text">{rank}</div>
                <div class="info-group">
                    <div class="stock-name">{t_name}</div>
                    <div class="status-badge">{t_status}</div>
                </div>
                <div class="yield-text">+{t_yield:.1f}%</div>
            </div>
            ''', unsafe_allow_html=True)

        # ---------------------------------------------------------
        # [화면 하단] 🎙️ Playwright가 긁어갈 AI 대본 (TTS용)
        # ---------------------------------------------------------
        # 60초 쇼츠에 맞춰 10개 종목을 다 읽어주면 시간이 오버될 수 있으므로
        # 속도감 있게 10개 종목 이름만 빠르게 읽어주도록 대본을 구성합니다.
        names_str = ", ".join(top_10_names)
        
        script_content = f"""
        AI가 분석한 오늘의 스윙 타점 탑텐입니다! 
        1위부터 10위까지 빠르게 불러드립니다. 
        {names_str} 입니다. 
        화면을 멈추고 현재 상태와 기대 수익률을 확인해 보세요! 단기 스윙 타점, 지금 바로 저장하세요!
        """
        
        st.markdown(f'<div class="script-box" id="tts_script">{script_content}</div>', unsafe_allow_html=True)

else:
    st.error("데이터를 수집하지 못했습니다. 연결 상태를 확인해주세요.")
