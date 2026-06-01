import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
import io
from datetime import datetime, timedelta, timezone
import FinanceDataReader as fdr
import concurrent.futures  # 🚀 (추가) 일꾼 복제 마법 도구

# =============================================================================
# [설정] 기본 셋팅
# =============================================================================
st.set_page_config(layout="centered", page_title="오늘의 핫스윙 Top 10")

# 📱 시선을 사로잡는 네온 테마 CSS
st.markdown("""
<style>
    /* 배경은 완전한 다크톤으로 눌러주고 컨텐츠를 돋보이게 */
    .stApp { background-color: #080A10; }
    .block-container { padding-top: 2rem; padding-bottom: 0rem; max-width: 900px; }
    
    /* 최상단 타이틀 (그라데이션 효과) */
    .shorts-title { 
        font-size: 75px; font-weight: 900; 
        background: linear-gradient(90deg, #FF416C 0%, #FF4B2B 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center; margin-bottom: 15px; line-height: 1.2; 
    }
    
    /* 🔥 오늘 날짜 강조 뱃지 */
    .date-badge-container { text-align: center; margin-bottom: 30px; }
    .date-badge { 
        background-color: #E2FF00; color: #000000; 
        font-size: 38px; font-weight: 900; 
        padding: 10px 40px; border-radius: 50px; 
        display: inline-block;
        box-shadow: 0 0 20px rgba(226, 255, 0, 0.4);
    }
    
    /* Top 10 리스트 행(Row) 입체감 부여 */
    .stock-row { 
        display: flex; align-items: center; justify-content: space-between; 
        background: linear-gradient(145deg, #1A1D24 0%, #111318 100%);
        padding: 20px 25px; margin-bottom: 18px; 
        border-radius: 20px; 
        border: 1px solid #2A2D35;
        box-shadow: 0 10px 20px rgba(0,0,0,0.5);
    }
    
    /* 순위 동그라미 뱃지 (네온 글로우 효과) */
    .rank-circle { 
        background: linear-gradient(135deg, #FF416C, #FF4B2B);
        color: white; 
        min-width: 75px; height: 75px; 
        border-radius: 50%; 
        display: flex; justify-content: center; align-items: center;
        font-size: 45px; font-weight: 900; 
        margin-right: 25px;
        box-shadow: 0 0 15px rgba(255, 75, 43, 0.6);
    }
    
    .info-group { flex-grow: 1; display: flex; flex-direction: column; justify-content: center; }
    .stock-name { font-size: 48px; font-weight: 900; color: #FFFFFF; margin-bottom: 8px; line-height: 1.1; }
    .status-badge { font-size: 26px; color: #00E5FF; font-weight: bold; }
    
    /* 수익률 텍스트 */
    .yield-text { font-size: 38px; font-weight: 900; color: #00FF00; text-align: right; text-shadow: 0 0 10px rgba(0,255,0,0.3); }
    .yield-label { font-size: 20px; color: #999999; display: block; margin-bottom: 5px; }
    
    .script-box { 
        background-color: #12141A; padding: 30px; border-radius: 15px; 
        margin-top: 40px; font-size: 32px; color: #888888; line-height: 1.6; border: 2px dashed #333;
    }
</style>
""", unsafe_allow_html=True)

KST = timezone(timedelta(hours=9))

# =============================================================================
# 1 & 2 & 3. 데이터 수집 및 분석 알고리즘
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

    # 💡 일꾼 1명이 1개 종목을 분석하는 전용 작업 지시서
    def process_stock(row):
        code, name = row['종목코드'], row['종목명']
        marcap_100m = int(row['시가총액'] / 100000000)
        score, status, _, high_price, target_yield = analyze_swing_probability(code,
                                                                               is_mega_cap=(marcap_100m >= 100000))

        if score > 0:
            return {
                "상태": status, "점수": score, "종목명": name,
                "현재가": row['현재가'], "등락률": row['등락률'],
                "전고점 기대수익(%)": target_yield
            }
        return None

    # 🚀 일꾼 15명을 동시에 투입해서 초고속으로 차트를 분석합니다!
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        # 모든 종목(100개)을 15명의 일꾼에게 나눠서 던져줌
        futures = [executor.submit(process_stock, row) for i, row in universe_df.iterrows()]

        # 분석이 끝나는 대로 순서대로 수거해서 리스트에 담음
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res:
                results.append(res)

    return results

# =============================================================================
# 4. 메인 화면 렌더링 (🔥 네온 테마 및 날짜/시간 추가)
# =============================================================================
universe_df = get_naver_top_universe()

if not universe_df.empty:
    with st.spinner("🔄 데이터 분석 중... (약 20초 소요)"):
        results = get_fully_analyzed_data(universe_df)
    
    if results:
        top_10_df = pd.DataFrame(results).sort_values(by="점수", ascending=False).head(10)
        
        # 🔥 오늘 날짜 및 시간 계산
        now_time = datetime.now(KST)
        badge_str = now_time.strftime('%Y년 %m월 %d일 %H:%M')    # 화면 뱃지용 (예: 2024년 5월 12일 15:20)
        script_str = now_time.strftime('%Y년 %m월 %d일 %H시 %M분') # 대본 읽기용 (예: 2024년 5월 12일 15시 20분)
        
        st.markdown(f'<div class="shorts-title">AI 스윙 타점 TOP 10</div>', unsafe_allow_html=True)
        # 날짜+시간 뱃지 렌더링
        st.markdown(f'<div class="date-badge-container"><span class="date-badge">⚡ {badge_str} 기준</span></div>', unsafe_allow_html=True)
        
        top_10_names = [] 

        for i, row in top_10_df.reset_index(drop=True).iterrows():
            rank = i + 1
            t_name = row['종목명']
            t_status = row['상태']
            t_yield = row['전고점 기대수익(%)']
            t_change = row['등락률']
            
            top_10_names.append(t_name)
            
            # 상승은 빨강/핑크계열, 하락은 파랑/시안계열로 변경하여 네온 테마에 어울리게 맞춤
            change_color = "#FF416C" if t_change > 0 else ("#00E5FF" if t_change < 0 else "#FFFFFF")
            change_sign = "+" if t_change > 0 else ""
            
            st.markdown(f'''
            <div class="stock-row">
                <div class="rank-circle">{rank}</div>
                <div class="info-group">
                    <div class="stock-name">
                        {t_name} <span style="font-size: 32px; color: {change_color}; font-weight: bold; margin-left: 10px;">({change_sign}{t_change}%)</span>
                    </div>
                    <div class="status-badge">{t_status}</div>
                </div>
                <div style="text-align: right;">
                    <span class="yield-label">기대수익</span>
                    <div class="yield-text">+{t_yield:.1f}%</div>
                </div>
            </div>
            ''', unsafe_allow_html=True)

        names_str = ", ".join(top_10_names)
        
        # 대본에도 시간까지 자연스럽게 추가하여 AI 성우가 읽어주도록 세팅
        script_content = f"""
        {script_str}, AI가 분석한 오늘의 스윙 타점 탑텐입니다! 
        1위부터 10위까지 빠르게 불러드립니다. 
        {names_str} 입니다. 
        화면을 멈추고 오늘 얼마나 올랐는지, 단기 목표 수익률은 얼마인지 바로 확인해 보세요!
        """
        st.markdown(f'<div class="script-box" id="tts_script">{script_content}</div>', unsafe_allow_html=True)

else:
    st.error("데이터를 수집하지 못했습니다. 연결 상태를 확인해주세요.")
