import datetime
import io
import xml.etree.ElementTree as ET
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

# 1. 화면 테마 전체 레이아웃 가로 확장형 세팅
st.set_page_config(page_title="종합 경제 지표 대시보드", layout="wide")
st.title("📊 글로벌 경제 지표 & 환율 대시보드 (분리형 안정판)")
st.write(
    "데이터 충돌과 에러를 방지하기 위해 상단은 네이버 금융 고시 데이터를, 하단은 Yahoo Finance 글로벌 데이터를 별도의 표로 분리했습니다."
)

# 2. [표 1] 네이버 전용 수집 구조 (환율 4종, 국내금리 3종)
NAVER_SYMBOLS = {
    "원화환율(시초가)": {
        "is_fx": True,
        "tickers": {"달러": "USDKRW", "유로": "EURKRW", "엔": "JPYKRW", "위안": "CNYKRW"}
    },
    "한국 국채 금리(종가)": {
        "is_fx": False,
        "tickers": {"국고채 3년": "IR_BOND_KR3Y", "국고채 10년": "IR_BOND_KR10Y", "회사채(AA-) 3년": "IR_BOND_CORP3Y_AA_MINUS"}
    }
}

# 3. [표 2] 야후 파이낸스 전용 글로벌 카테고리 정의 (안전 티커 기반)
YAHOO_CATEGORIES = {
    "미국 국채 금리(종가)": {
        "type": "Close",
        "tickers": {
            "미 국채 3년 수익률": "^SPBDUS3T",     
            "미 국채 10년 수익률": "^TNX",       
        },
    },
    "에너지(종가)": {
        "type": "Close",
        "tickers": {
            "두바이(선물)": "DF=F",             
            "브렌트(선물)": "BZ=F",
            "WTI(선물)": "CL=F",
            "천연가스(헨리허브, 선물)": "NG=F",
        },
    },
    "금속가격(종가)": {
        "type": "Close",
        "tickers": {
            "금(뉴욕거래소)": "GC=F",
            "은(뉴욕거래소)": "SI=F",
            "구리(LME)": "HG=F",
            "알루미늄(LME)": "ALI=F",
            "니켈(LME)": "JJN",
        },
    },
    "곡물가격(뉴욕, 종가)": {
        "type": "Close",
        "tickers": {
            "설탕": "SB=F",
            "소맥": "W=F",
            "대두유": "BO=F",
            "카카오": "CC=F",
            "커피": "KC=F",
        },
    },
    "물류(종가)": {
        "type": "Close",
        "tickers": {
            "SCFI (대체 ETF)": "BDRY",
            "BDI (대체 ETF)": "SEA",
        },
    },
    "주가지수 (종가)": {
        "type": "Close",
        "tickers": {
            "Kospi": "^KS11",
            "Kosdaq": "^KQ11",
            "다우존스": "^DJI",
            "나스닥": "^IXIC",
            "S&P500": "^GSPC",
            "니케이225": "^N225",
            "상해종합": "000001.SS",
            "심천종합": "399001.SZ",
        },
    },
    "롯데그룹 계열사 주가(종가)": {
        "type": "Close",
        "tickers": {
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
            "롯데이노베이트": "286940.KS",
        },
    },
}


# 네이버 차트 백엔드 XML 데이터 수집용 함수
def fetch_naver_chart_series(symbol, is_fx=False):
    url = f"https://naver.com{symbol}&timeframe=day&count=15&requestType=0"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            data_dict = {}
            for item in root.findall(".//item"):
                data_str = item.get("data")
                if data_str:
                    parts = data_str.split("|")
                    if len(parts) >= 5:
                        date_raw = parts
                        date_fmt = f"{date_raw[0:4]}-{date_raw[4:6]}-{date_raw[6:8]}"
                        price_val = float(parts) if is_fx else float(parts)
                        data_dict[date_fmt] = price_val
            return pd.Series(data_dict)
    except Exception:
        pass
    return pd.Series(dtype="float64")


# [표 1] 네이버 데이터 전용 가공 함수
@st.cache_data(ttl=1800)
def get_naver_only_table():
    all_columns = []
    for cat_name, cat_info in NAVER_SYMBOLS.items():
        is_fx_flag = cat_info["is_fx"]
        for display_name, symbol in cat_info["tickers"].items():
            series = fetch_naver_chart_series(symbol, is_fx=is_fx_flag)
            if not series.empty:
                col_df = series.to_frame()
                col_df.columns = pd.MultiIndex.from_tuples([(cat_name, display_name)])
                all_columns.append(col_df)
    if not all_columns:
        return None
    df = pd.concat(all_columns, axis=1).dropna(how="all").ffill()
    df = df.tail(7).sort_index(ascending=True)
    df.index = df.index.strftime("%Y-%m-%d")
    return df.round(2)


# [표 2] 야후 파이낸스 데이터 전용 가공 함수
@st.cache_data(ttl=1800)
def get_yahoo_only_table():
    today = datetime.date.today()
    start_date = today - datetime.timedelta(days=16)
    all_columns = []
    for cat_name, cat_info in YAHOO_CATEGORIES.items():
        data_type = cat_info["type"]
        for display_name, ticker in cat_info["tickers"].items():
            try:
                df = yf.download(ticker, start=start_date, end=today, progress=False)
                if not df.empty and data_type in df.columns:
                    col_data = df[data_type].to_frame()
                    col_data.columns = pd.MultiIndex.from_tuples([(cat_name, display_name)])
                    all_columns.append(col_data)
            except Exception:
                pass
    if not all_columns:
        return None
    df = pd.concat(all_columns, axis=1).dropna(how="all").ffill()
    df = df.tail(7).sort_index(ascending=True)
    df.index = df.index.strftime("%Y-%m-%d")
    return df.round(2)


# --- 🖥️ 화면 렌더링 구동 영역 ---

# 📌 1번 표: 네이버 (환율 & 국내금리)
st.subheader("📌 1. 국내 금융 고시 데이터 (원화환율 및 한국 국채금리)")
naver_table = get_naver_only_table()

if naver_table is not None:
    # 엑셀 다운로드 독립 생성
    buf1 = io.BytesIO()
    with pd.ExcelWriter(buf1, engine="xlsxwriter") as writer:
        naver_table.to_excel(writer, sheet_name="네이버_지표")
    st.download_button(
        label="📥 1. 환율/국내금리 엑셀 파일 다운로드",
        data=buf1.getvalue(),
        file_name=f"naver_economy_data_{datetime.date.today()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    st.dataframe(naver_table, use_container_width=True, height=260)
else:
    st.error("네이버 데이터를 가공하는 중 문제가 생겼습니다.")

st.markdown("---")

# 📌 2번 표: 야후 파이낸스 (글로벌 지표 & 롯데 주가)
st.subheader("📌 2. 글로벌 금융시장 데이터 (주가, 원자재, 미국 금리 등)")
yahoo_table = get_yahoo_only_table()

if yahoo_table is not None:
    # 엑셀 다운로드 독립 생성
    buf2 = io.BytesIO()
    with pd.ExcelWriter(buf2, engine="xlsxwriter") as writer:
        yahoo_table.to_excel(writer, sheet_name="야후_지표")
    st.download_button(
        label="📥 2. 글로벌/롯데주가 엑셀 파일 다운로드",
        data=buf2.getvalue(),
        file_name=f"yahoo_global_data_{datetime.date.today()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    st.dataframe(yahoo_table, use_container_width=True, height=280)
else:
    st.error("야후 글로벌 데이터를 수집하는 중 일시적인 지연이 발생했습니다.")
