import datetime
import io
import pandas as pd
import streamlit as st
import yfinance as yf

# 1. 화면 테마 전체 레이아웃 가로 확장형 세팅
st.set_page_config(page_title="통합 경제 지표 대시보드", layout="wide")
st.title("📊 가로 통합형 글로벌 경제 지표 & 환율")
st.write(
    "모든 지표를 하나의 표로 결합했습니다. 우측으로 스크롤하여 전체 데이터를 확인하세요."
)

# 2. 카테고리 및 티커 구조 (야후 파이낸스 공인 안정형 티커 전면 재배치)
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
            "미 국채 중단기(5년) 수익률": "^FVX",     # [💡 완벽교체] 에러 유발 코드(^SPBDUS3T) 대신 야후 공인 국채 금리 지수 탑재
            "미 국채 10년 수익률": "^TNX",       # 미국 10년 국채 금리(%) 지수
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
    start_date = today - datetime.timedelta(days=14)

    all_columns = []

    for cat_name, cat_info in CATEGORIES.items():
        data_type = cat_info["type"]

        for display_name, ticker in cat_info["tickers"].items():
            try:
                df = yf.download(ticker, start=start_date, end=today, progress=False)
                if not df.empty and data_type in df.columns:
                    col_data = df[data_type].to_frame()
                    col_data.columns = pd.MultiIndex.from_tuples(
                        [(cat_name, display_name)]
                    )
                    all_columns.append(col_data)
            except Exception:
                pass

    if not all_columns:
        return None

    # 모든 자산 가로 병합 후 결측치 정제
    total_df = pd.concat(all_columns, axis=1)
    total_df = total_df.dropna(how="all").ffill()

    # 최근 7영업일 슬라이싱 및 오름차순(과거 위, 최신 아래) 정렬 고정
    total_df = total_df.tail(7).sort_index(ascending=True)

    # 날짜 인덱스 포맷 정리
    total_df.index = total_df.index.strftime("%Y-%m-%d")
    return total_df.round(2)


# 데이터 구동
flat_data = fetch_total_flat_data()

if flat_data is not None and not flat_data.empty:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        flat_data.to_excel(writer, sheet_name="경제지표")

    st.download_button(
        label="📥 서식 없이 엑셀 파일로 바로 다운로드",
        data=buffer.getvalue(),
        file_name=f"economy_data_{datetime.date.today()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.markdown("### 🗓️ 날짜별 글로벌 지표 변동 현황 (최근 일주일)")

    # 단 하나의 거대한 가로형 통합 표 인쇄 (가로 스크롤 활성화)
    st.dataframe(flat_data, use_container_width=True, height=350)
    st.success("모든 카테고리가 날짜 순방향(최근 날짜가 아래로)으로 결합 완료되었습니다!")
else:
    st.error("데이터 수집 서버와 일시적 연결 지연이 발생했습니다. 1~2분 후 새로고침해 주세요.")

