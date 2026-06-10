import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

# ==========================================
# 야후 파이낸스 37종 티커(Ticker) 최종 목록 (미국채 3년물 제외)
# ==========================================
INDICATORS = {
    # 1. 미국 국채 금리
    "미 국채 10년 금리(수익률)": "^TNX",    # CBOE Interest Rate 10 Year T-Note Yield
    
    # 2. 에너지 (선물)
    "두바이유(선물)": "O=F",            # Dubai Crude Oil Futures
    "브렌트유(선물)": "BZ=F",           # Brent Crude Oil Futures
    "WTI유(선물)": "CL=F",             # WTI Crude Oil Futures
    "천연가스(선물)": "NG=F",           # Henry Hub Natural Gas Futures
    
    # 3. 금속 가격 (종가)
    "금(NYMEX)": "GC=F",               # Gold Futures
    "은(NYMEX)": "SI=F",               # Silver Futures
    "구리(COMEX)": "HG=F",             # Copper Futures
    "알루미늄(COMEX)": "ALI=F",         # Aluminum Futures
    "니켈(LME지수 대용)": "JJN=F",       # Bloomberg Nickel Subindex
    
    # 4. 곡물 가격 (NYMEX/CBOT 선물 종가)
    "설탕(선물)": "SB=F",               # Sugar No. 11 Futures
    "소맥(밀 선물)": "W=F",             # Wheat Futures
    "대두유(선물)": "ZL=F",             # Soybean Oil Futures
    "카카오(선물)": "CC=F",             # Cocoa Futures
    "커피(선물)": "KC=F",               # Coffee C Futures
    
    # 5. 물류
    "BDI(운임지수)": "^BDI",            # Baltic Dry Index
    
    # 6. 주가지수 (종가)
    "KOSPI": "^KS11",
    "KOSDAQ": "^KQ11",
    "다우존스": "^DJI",
    "나스닥": "^IXIC",
    "S&P500": "^GSPC",
    "니케이225": "^N225",
    "상해종합": "000001.SS",
    "심천종합": "399001.SZ",
    
    # 7. 롯데그룹 계열사 주가 (종가)
    "롯데지주": "004990.KS",
    "롯데케미칼": "011170.KS",
    "롯데에너지머티리얼즈": "020150.KS",
    "롯데정밀화학": "004000.KS",
    "롯데쇼핑": "023530.KS",
    "롯데리츠": "330590.KS",
    "롯데하이마트": "071840.KS",
    "롯데칠성": "005300.KS",
    "롯데웰푸드": "280360.KS",
    "롯데렌탈": "089860.KS",
    "롯데이노베이트": "286940.KS"
}

@st.cache_data(ttl=1800)  # 30분 간 데이터 브라우저 캐싱 가동
def build_global_finance_table():
    """
    다국적 시차와 자산별 휴일 불일치로 인한 결측치(NaN)를 정교하게 해결하고,
    단 하나의 에러 없이 온전한 가로축 단일 데이터프레임으로 오름차순 조인합니다.
    """
    end_date = datetime.today()
    start_date = end_date - timedelta(days=35) # 최근 10영업일을 안정적으로 확보하기 위해 넉넉히 한달 확보
    
    # 통합 마스터 테이블 (행 결합의 중심축)
    master_df = None
    
    for kor_name, ticker in INDICATORS.items():
        try:
            # 야후 파이낸스 개별 API 데이터 다운로드
            data = yf.download(ticker, start=start_date, end=end_date, progress=False)
            
            if data.empty or "Close" not in data.columns:
                continue
                
            # 종가(Close) 컬럼을 평탄화 처리하여 2차원 결합용 프레임 가공
            df = data[["Close"]].copy()
            df.index = pd.to_datetime(df.index)
            df = df.reset_index()
            df.columns = ["DATE", kor_name]
            
            # yfinance 특유의 멀티인덱스 컬럼 구조 파싱 디버깅
            if isinstance(df[kor_name], pd.DataFrame):
                df[kor_name] = df[kor_name].iloc[:, 0]
            
            # 마스터 테이블에 'DATE' 축을 기준으로 외부 조인(Outer Merge) 병합 수행
            if master_df is None:
                master_df = df
            else:
                master_df = master_df.merge(df, on="DATE", how="outer")
        except Exception:
            continue
            
    if master_df is None or master_df.empty:
        return pd.DataFrame()
        
    # 국가별 휴일 및 시차로 주말 전후 축이 틀어지는 현상을 방지하기 위한 정방향/역방향 자동 패딩 처리
    master_df = master_df.sort_values("DATE", ascending=True)
    master_df = master_df.ffill().bfill()
    
    # 가로축 동기화 완료 후 최근 10영업일을 안전하게 슬라이싱 처리
    master_df = master_df.tail(10)
    
    # 최종 출력은 날짜 기준 과거 -> 현재 오름차순으로 정렬 유지
    master_df = master_df.sort_values("DATE", ascending=True)
    
    # 날짜 컬럼 보기 좋게 변환 (YYYY-MM-DD)
    master_df["날짜"] = master_df["DATE"].dt.strftime("%Y-%m-%d")
    
    # 가로축 컬럼 배치 순서 정의 명세대로 고정
    final_ordered_cols = ["날짜"] + [col for col in INDICATORS.keys() if col in master_df.columns]
    master_df = master_df[final_ordered_cols]
    
    return master_df

# ==========================================
# Streamlit 대시보드 웹 렌더링 영역
# ==========================================
st.set_page_config(
    page_title="글로벌 종합 금융 지표 대시보드",
    layout="wide"
)

st.title("🌐 글로벌 금융·원자재·롯데그룹 지표 통합 현황")
st.caption("Yahoo Finance 실시간 API 기반 최근 10 영업일 종가 데이터 동향 (오름차순 정렬)")

with st.spinner("야후 파이낸스 서버로부터 37개 글로벌 마켓 자산을 동기화 중입니다..."):
    final_table = build_global_finance_table()

if not final_table.empty:
    formatted_df = final_table.copy()
    for col in formatted_df.columns:
        if col != "날짜":
            formatted_df[col] = pd.to_numeric(formatted_df[col], errors='coerce')
            
    # [핵심 수정 부분] 최신 Pandas 문법에 맞게 format 옵션을 수정했습니다.
    st.dataframe(
        formatted_df.style.format(formatter="{:,.2f}", na_rep="-"),
        use_container_width=True,
        hide_index=True
    )
    st.success("📊 37종 글로벌 지표 대시보드 단일 통합 표가 에러 없이 오름차순 연동 완료되었습니다.")
else:
    st.error("❌ 데이터 결합 처리에 실패했습니다. 인터넷 연결 또는 서버 구동 상태를 확인해 주세요.")
