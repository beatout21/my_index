import datetime
import pandas as pd
import streamlit as st
import yfinance as yf

# 1. 화면 테마 전체 레이아웃 가로 확장형 세팅
st.set_page_config(page_title="통합 경제 지표 대시보드", layout="wide")
st.title("📊 가로 통합형 글로벌 경제 지표 & 환율")
st.write(
    "모든 지표를 하나의 표로 결합했습니다. 우측으로 스크롤하여 전체 데이터를 확인하세요."
)

# 2. 카테고리 및 티커 구조 (순서 유지)
CATEGORIES = {
    "원화환율(시초가)": {
        "type": "Open",
        "tickers": {
            "달러": "KRW=X",
            "유로": "EURKRW=X",
            "엔": "JPYKRW=X",
            "위안": "CNYKRW=X",
        },
    },
    "한국 국채 금리(종가)": {
        "type": "Close",
        "tickers": {
            "국고채 3년 (대체)": "114260.KS",
            "국고채 10년 (대체)": "365780.KS",
            "회사채(AA-) 3년 (대체)": "273130.KS",
        },
    },
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


@st.cache_data(ttl=1800)
def fetch_total_flat_data():
    today = datetime.date.today()
    start_date = today - datetime.timedelta(days=12)  # 충분한 일수 확보

    all_columns = []

    for cat_name, cat_info in CATEGORIES.items():
        data_type = cat_info["type"]

        for display_name, ticker in cat_info["tickers"].items():
            try:
                df = yf.download(
                    ticker, start=start_date, end=today, progress=False
                )
                if not df.empty and data_type in df.columns:
                    col_data = df[data_type].copy()

                    # 핵심: [상위 카테고리, 개별 항목] 형태로 이름 구조 튜플 매칭
                    col_data.columns = pd.MultiIndex.from_tuples(
                        [(cat_name, display_name)]
                    )
                    all_columns.append(col_data)
            except Exception:
                pass

    if not all_columns:
        return None

    # 모든 데이터를 가로(axis=1)로 통짜 병합
    total_df = pd.concat(all_columns, axis=1)

    # 데이터가 아예 없는 주말/공휴일 행 삭제 및 최신날짜순 정렬
    total_df = total_df.dropna(how="all").sort_index(ascending=False)
    total_df = total_df.head(7)  # 최근 일주일(영업일 기준 7일) 데이터 유지

    # 날짜 인덱스 가독성 정리
    total_df.index = total_df.index.strftime("%Y-%m-%d")
    return total_df.round(2)


# 데이터 로드
flat_data = fetch_total_flat_data()

# 3. 단 하나의 거대한 가로형 표 렌더링
if flat_data is not None:
    st.markdown("### 🗓️ 날짜별 글로벌 지표 변동 현황 (최근 일주일)")

    # 대용량 표를 컨테이너 너비에 맞게 배치 (가로 스크롤 활성화)
    st.dataframe(flat_data, use_container_width=True, height=350)

    st.success("모든 카테고리가 단 하나의 가로형 표로 결합 완료되었습니다!")
else:
    st.error("데이터 수집 서버에 일시적인 문제가 생겼습니다.")
