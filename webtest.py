import datetime
import pandas as pd
import streamlit as st
import yfinance as yf

# 1. 스트림릿 화면 및 테마 설정
st.set_page_config(page_title="종합 경제 지표 대시보드", layout="wide")
st.title("📊 맞춤형 글로벌 경제 지표 & 환율 대시보드")
st.write(f"최근 일주일간의 지표별 현황 (조회 기준 시각: {datetime.date.today()})")

# 2. 요청 순서 및 티커 목록 상세 정의
CATEGORIES = {
    "원화환율(시초가)": {
        "type": "Open",
        "tickers": {
            "달러/원 (USD)": "KRW=X",
            "유로/원 (EUR)": "EURKRW=X",
            "엔/원 (100JPY)": "JPYKRW=X",
            "위안/원 (CNY)": "CNYKRW=X",
        },
    },
    "한국 국채 금리(종가)": {
        "type": "Close",
        "tickers": {
            "국고채 3년 (대체:인버스채권)": "114260.KS",
            "국고채 10년 (대체:KINDEX 10Y)": "365780.KS",
            "회사채 (AA-) 3년 (대체:종합채권)": "273130.KS",
        },
    },
    "미국 국채 금리(종가)": {
        "type": "Close",
        "tickers": {
            "미 국채 3년 (대체:SHY 1-3Y)": "SHY",
            "미 국채 10년 수익률": "^TNX",
        },
    },
    "에너지(종가)": {
        "type": "Close",
        "tickers": {
            "두바이유 (대체:NEXT NOTES)": "2039.T",
            "브렌트유 선물": "BZ=F",
            "WTI유 선물": "CL=F",
            "천연가스(헨리허브 선물)": "NG=F",
        },
    },
    "금속가격(종가)": {
        "type": "Close",
        "tickers": {
            "금 (뉴욕거래소)": "GC=F",
            "은 (뉴욕거래소)": "SI=F",
            "구리 (HG 선물)": "HG=F",
            "알루미늄 (대체:ALI=F)": "ALI=F",
            "니켈 (대체:JJN)": "JJN",
        },
    },
    "곡물가격(뉴욕거래소, 종가)": {
        "type": "Close",
        "tickers": {
            "설탕 선물": "SB=F",
            "소맥(밀) 선물": "W=F",
            "대두유 선물": "BO=F",
            "카카오 선물": "CC=F",
            "커피 선물": "KC=F",
        },
    },
    "물류(종가)": {
        "type": "Close",
        "tickers": {
            "SCFI 해운지수 (대체:BDRY)": "BDRY",
            "BDI 발틱운임지수 (대체:SEA)": "SEA",
        },
    },
    "주가지수(종가)": {
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


@st.cache_data(ttl=1800)  # 30분 동안 캐싱 유지
def fetch_all_data():
    today = datetime.date.today()
    start_date = today - datetime.timedelta(days=10)  # 주말 공백 감안하여 10일 확보

    results = {}

    for cat_name, cat_info in CATEGORIES.items():
        data_type = cat_info["type"]
        cat_df_list = []

        for display_name, ticker in cat_info["tickers"].items():
            try:
                # 야후 파이낸스 대량 수집
                df = yf.download(
                    ticker, start=start_date, end=today, progress=False
                )
                if not df.empty and data_type in df.columns:
                    col_data = df[data_type].copy()
                    col_data.columns = [display_name]
                    cat_df_list.append(col_data)
            except Exception:
                pass

        if cat_df_list:
            merged_df = pd.concat(cat_df_list, axis=1)
            # 주말 공백 제거 및 최근 날짜순 정렬
            merged_df = merged_df.dropna(how="all").sort_index(ascending=False)
            # 최근 7행만 슬라이싱하여 일주일 기간 유지
            merged_df = merged_df.head(7)
            merged_df.index = merged_df.index.strftime("%Y-%m-%d")
            results[cat_name] = merged_df.round(2)

    return results


# 데이터 로드 실행
all_data = fetch_all_data()

# 3. 화면 UI 배치 (요청한 대분류 순서 고정 출력)
for cat_name in CATEGORIES.keys():
    st.subheader(f"📌 {cat_name}")

    if cat_name in all_data and not all_data[cat_name].empty:
        # 스마트폰 화면 너비에 꽉 차게 조절 가능한 렌더링 방식
        st.dataframe(all_data[cat_name], use_container_width=True)
    else:
        st.info("현재 수집 가능한 데이터가 없거나 휴장일입니다.")
    st.markdown("---")

st.success("모든 카테고리 업데이트 완료!")

