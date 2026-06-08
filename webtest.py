import datetime
import io
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

# 1. 화면 레이아웃 및 제목 설정
st.set_page_config(page_title="종합 경제 지표 대시보드", layout="wide")
st.title("📊 글로벌 경제 지표 & 환율 대시보드 (분리형)")
st.write("상단은 한국은행 ECOS 공식 데이터이며, 하단은 Yahoo Finance 글로벌 데이터입니다.")

# 🔑 한국은행 ECOS API 인증키를 여기에 입력하세요.
ECOS_API_KEY = "ZXBH7LM5BB9NFLDW0DEA"

# 2. 야후 파이낸스로 가져올 글로벌 지표 정의
YAHOO_CATEGORIES = {
    "미국 국채 금리(종가)": {
        "type": "Close",
        "tickers": {
            "미 국채 3년 (대체)": "SHY",
            "미 국채 10년 수익률": "^TNX",
        },
    },
    "에너지(종가)": {
        "type": "Close",
        "tickers": {
            "두바이(현물, 대체)": "2039.T",
            "브렌트(선물)": "BZ=F",
            "WTI(선물)": "CL=F",
            "천연가스(선물)": "NG=F",
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
            "SCFI (대체)": "BDRY",
            "BDI (대체)": "SEA",
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


# 3. 한국은행 ECOS API 호출 전용 함수
def fetch_ecos_data(stat_code, item_code, start_date, end_date):
    url = f"https://bok.or.kr{ECOS_API_KEY.strip()}/json/kr/1/100/{stat_code}/D/{start_date}/{end_date}/{item_code}"
    try:
        response = requests.get(url, timeout=10)
        json_data = response.json()
        if "StatisticSearch" in json_data and "row" in json_data["StatisticSearch"]:
            rows = json_data["StatisticSearch"]["row"]
            df = pd.DataFrame(rows)
            df.columns = [col.lower() for col in df.columns]
            df["time"] = pd.to_datetime(df["time"], format="%Y%m%d")
            df["data_value"] = pd.to_numeric(df["data_value"])
            df = df.set_index("time")
            return df["data_value"]
    except Exception:
        pass
    return pd.Series(dtype="float64")


# 4. [표 1] 한국은행 전용 데이터 수집 함수
@st.cache_data(ttl=600)
def get_ecos_dataframe():
    today_dt = datetime.date.today()
    start_dt = today_dt - datetime.timedelta(days=15)
    start_str = start_dt.strftime("%Y%m%d")
    end_str = today_dt.strftime("%Y%m%d")

    ecos_dfs = []

    # 1) 원화환율 (022Y013)
    exchange_mapping = {"달러": "0000001", "유로": "0000003", "엔": "0000002", "위안": "0000053"}
    for name, item_cd in exchange_mapping.items():
        series = fetch_ecos_data("022Y013", item_cd, start_str, end_str)
        if not series.empty:
            df = series.to_frame()
            df.columns = pd.MultiIndex.from_tuples([("원화환율(시초가)", name)])
            ecos_dfs.append(df)

    # 2) 국내 금리 (060Y001)
    bond_mapping = {
        "국고채 3년": "010200000",
        "국고채 10년": "010210000",
        "회사채(AA-) 3년": "010300000",
    }
    for name, item_cd in bond_mapping.items():
        series = fetch_ecos_data("060Y001", item_cd, start_str, end_str)
        if not series.empty:
            df = series.to_frame()
            df.columns = pd.MultiIndex.from_tuples([("한국 국채 금리(종가)", name)])
            ecos_dfs.append(df)

    if not ecos_dfs:
        return None

    ecos_master = pd.concat(ecos_dfs, axis=1)
    ecos_master = ecos_master.dropna(how="all").ffill()
    ecos_master = ecos_master.tail(7).sort_index(ascending=True)
    ecos_master.index = ecos_master.index.strftime("%Y-%m-%d")
    return ecos_master.round(2)


# 5. [표 2] 야후 파이낸스 전용 데이터 수집 함수
@st.cache_data(ttl=600)
def get_yahoo_dataframe():
    today_dt = datetime.date.today()
    start_dt = today_dt - datetime.timedelta(days=15)

    yahoo_dfs = []

    for cat_name, cat_info in YAHOO_CATEGORIES.items():
        data_type = cat_info["type"]
        for display_name, ticker in cat_info["tickers"].items():
            try:
                df_yf = yf.download(ticker, start=start_dt, end=today_dt, progress=False)
                if not df_yf.empty and data_type in df_yf.columns:
                    col_data = df_yf[data_type].to_frame()
                    col_data.columns = pd.MultiIndex.from_tuples([(cat_name, display_name)])
                    yahoo_dfs.append(col_data)
            except Exception:
                pass

    if not yahoo_dfs:
        return None

    yahoo_master = pd.concat(yahoo_dfs, axis=1)
    yahoo_master = yahoo_master.dropna(how="all").ffill()
    yahoo_master = yahoo_master.tail(7).sort_index(ascending=True)
    yahoo_master.index = yahoo_master.index.strftime("%Y-%m-%d")
    return yahoo_master.round(2)


# --- 화면 렌더링 영역 ---

# 🛑 [1번 표] 한국은행 데이터 렌더링
st.subheader("📌 1. 한국은행 고시 데이터 (환율 & 국내금리)")
ecos_df = get_ecos_dataframe()

if ecos_df is not None and not ecos_df.empty:
    # 엑셀 다운로드 파일 메모리 빌드
    buf1 = io.BytesIO()
    with pd.ExcelWriter(buf1, engine="xlsxwriter") as writer:
        ecos_df.to_excel(writer, sheet_name="한국은행_지표")
    st.download_button(
        label="📥 한국은행 데이터 엑셀 다운로드",
        data=buf1.getvalue(),
        file_name=f"BOK_data_{datetime.date.today()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    st.dataframe(ecos_df, use_container_width=True, height=260)
else:
    st.info("💡 한국은행 API를 불러오는 중입니다. 키 값이 정확한데도 이 문구가 지속된다면 오늘이 한국은행 시스템 점검일이거나 신규 인증키 승인 대기 상태일 수 있습니다.")

st.markdown("---")

# 🛑 [2번 표] 야후 파이낸스 글로벌 데이터 렌더링
st.subheader("📌 2. 글로벌 금융시장 데이터 (주가, 원자재, 물류 등)")
yahoo_df = get_yahoo_dataframe()

if yahoo_df is not None and not yahoo_df.empty:
    # 엑셀 다운로드 파일 메모리 빌드
    buf2 = io.BytesIO()
    with pd.ExcelWriter(buf2, engine="xlsxwriter") as writer:
        yahoo_df.to_excel(writer, sheet_name="글로벌_지표")
    st.download_button(
        label="📥 글로벌 데이터 엑셀 다운로드",
        data=buf2.getvalue(),
        file_name=f"Global_data_{datetime.date.today()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    st.dataframe(yahoo_df, use_container_width=True, height=280)
else:
    st.error("야후 파이낸스 데이터를 가져오는 데 실패했습니다.")
