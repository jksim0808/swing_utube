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
    .stock-name { font-size: 48px; font-weight: 900; color: #FFFFFF; margin-bottom: 8px; line-height: 1.1;
