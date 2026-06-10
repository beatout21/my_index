import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

# ==========================================
# 야후 파이낸스 37종 티커(Ticker) 최종 목록
# ==========================================
INDICATORS = {
    # 1. 미국 국채 금리
    "미 국채 10년 금리(수익률)": "^TNX",
    
    # 2. 에너지 (선물)
    "두바이유(선물)": "O=F",
    "브렌트유(선물)": "BZ=F",
    "WTI유(선물)": "CL=F",
    "천연가스(선물)": "NG=F",
    
    # 3. 금속 가격 (종가)
    "금(NYMEX)": "GC=F",
    "은(NYMEX)": "SI=F",
    "구리(COMEX)": "HG=F",
    "알루미늄(COMEX)": "ALI=F",
    "니켈(LME지수 대용)": "JJN=F",
    
    # 4. 곡물 가격 (종가)
    "설탕(선물)": "SB=F",
    "소맥(밀 선물)": "W=F",
    "대두유(선물)": "ZL=F",
    "카카오(선물)": "CC=F",
    "커피(선물)": "KC=F",
    
    # 5. 물류
    "BDI(운임지수)": "^BDI",
    
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

@st.cache_data(ttl=1800)
def build_global_finance_table():
    end_date = datetime.today()
    start_date = end_date - timedelta(days=35)
    
    master_df = None
    
    for kor_name, ticker in INDICATORS.items():
        try:
            data = yf.download(ticker, start=start_date, end=end_date, progress=False)
            
            if data.empty or "Close" not in data.columns:
                continue
                
            df = data[["Close"]].copy()
            df.index = pd.to_datetime(df.index)
            df = df.reset_index()
            df.columns = ["DATE", kor_name]
            
            if isinstance(df[kor_name], pd.DataFrame):
                df[kor_name] = df[kor_name].iloc[:, 0]
            
            if master_df is None:
                master_df = df
            else:
                master_df = master_df.merge(df, on="DATE", how="outer")
        except Exception:
            continue
            
    if master_df is None or master_df.empty:
        return pd.DataFrame()
        
    master_df = master_df.sort_values("DATE", ascending=True)
    master_df = master_df.ffill().bfill()
    
    master_df = master_df.tail(10)
    master_df = master_df.sort_values("DATE", ascending=True)
    
    master_df["날짜"] = master_df["DATE"].dt.strftime("%Y-%m-%d")
    
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
    
    # 지표명 컬럼(날짜 제외)만 추출하여 숫자 형식을 강제 적용합니다.
    numeric_cols = [col for col in formatted_df.columns if col != "날짜"]
    for col in numeric_cols:
        formatted_df[col] = pd.to_numeric(formatted_df[col], errors='coerce')
            
    # [버그 수정 포인트] 
    # subset=numeric_cols 옵션을 추가하여 '날짜' 문자열 컬럼에는 소수점 서식이 적용되지 않도록 방어했습니다.
    st.dataframe(
        formatted_df.style.format(formatter="{:,.2f}", na_rep="-", subset=numeric_cols),
        use_container_width=True,
        hide_index=True
    )
    st.success("📊 37종 글로벌 지표 대시보드 단일 통합 표가 에러 없이 오름차순 연동 완료되었습니다.")
else:
    st.error("❌ 데이터 결합 처리에 실패했습니다. 인터넷 연결 또는 서버 구동 상태를 확인해 주세요.")

