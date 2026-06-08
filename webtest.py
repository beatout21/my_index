import datetime
import io
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

# 1. 화면 레이아웃 설정
st.set_page_config(page_title="통합 경제 지표 대시보드", layout="wide")
st.title("📊 경제 지표 대시보드")
st.write(
    "환율과 국내 금리는 한국은행 ECOS 공식 데이터이며, 글로벌 지표는 Yahoo Finance 데이터입니다."
)

# 🔑 한국은행 ECOS API 인증키를 여기에 입력하세요.
ECOS_API_KEY = "ZXBH7LM5BB9NFLDW0DEA"

# 2. 야후 파이낸스로 가져올 나머지 글로벌 지표 정의
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


# 3. 한국은행 ECOS API 호출 전용 함수 정의
def fetch_ecos_data(stat_code, item_code, start_date, end_date, column_name):
    url = f"https://ecos.bok.or.kr/api/StatisticSearch/{ECOS_API_KEY}/json/kr/1/100/{stat_code}/D/{start_date}/{end_date}/{item_code}"
    try:
        response = requests.get(url, timeout=10)
        json_data = response.json()
        if "StatisticSearch" in json_data:
            rows = json_data["StatisticSearch"]["row"]
            # 날짜와 값 추출하여 데이터프레임 빌드
            df = pd.DataFrame(rows)
            df["TIME"] = pd.to_datetime(df["TIME"], format="%Y%m%d")
            df["DATA_VALUE"] = pd.to_numeric(df["DATA_VALUE"])
            df = df.set_index("TIME")[["DATA_VALUE"]]
            df.columns = column_name
            return df
    except Exception:
        pass
    return pd.DataFrame()


@st.cache_data(ttl=1800)
def fetch_all_combined_data():
    # 날짜 범위 확보 (주말 포함 데이터 정합성을 위해 충분한 14일 확보)
    today_dt = datetime.date.today()
    start_dt = today_dt - datetime.timedelta(days=14)

    start_str = start_dt.strftime("%Y%m%d")
    end_str = today_dt.strftime("%Y%m%d")

    all_dfs = []

    # --- [A] 한국은행 ECOS 데이터 수집 영역 ---
    # 1. 원화환율 (시초가 - ECOS상 당일 최초 고시 환율 기준 매핑)
    exchange_mapping = {"달러": "0000001", "유로": "0000003", "엔": "0000002", "위안": "0000053"}
    for name, item_cd in exchange_mapping.items():
        # 통계표 731Y001 : 주요국 통화의 대원화환율
        col_idx = pd.MultiIndex.from_tuples([("원화환율(시초가)", name)])
        df_ecos = fetch_ecos_data("731Y001", item_cd, start_str, end_str, col_idx)
        if not df_ecos.empty:
            all_dfs.append(df_ecos)

    # 2. 국내 금리 (종가 - 당일 최종 고시 금리)
    bond_mapping = {
        "국고채 3년": "010200000",
        "국고채 10년": "010210000",
        "회사채(AA-) 3년": "010300000",
    }  #
    for name, item_cd in bond_mapping.items():
        # 통계표 817Y002 : 시장금리(일별)
        if "국고채" in name:
            col_idx = pd.MultiIndex.from_tuples([("한국 국채 금리(종가)", name)])
        else:
            col_idx = pd.MultiIndex.from_tuples([("한국 국채 금리(종가)", name)])
        df_ecos = fetch_ecos_data("817Y002", item_cd, start_str, end_str, col_idx)
        if not df_ecos.empty:
            all_dfs.append(df_ecos)

    # --- [B] 야후 파이낸스 글로벌 데이터 수집 영역 ---
    for cat_name, cat_info in YAHOO_CATEGORIES.items():
        data_type = cat_info["type"]
        for display_name, ticker in cat_info["tickers"].items():
            try:
                df_yf = yf.download(ticker, start=start_dt, end=today_dt, progress=False)
                if not df_yf.empty and data_type in df_yf.columns:
                    col_data = df_yf[data_type].copy()
                    col_data.columns = pd.MultiIndex.from_tuples([(cat_name, display_name)])
                    all_dfs.append(col_data)
            except Exception:
                pass

    if not all_dfs:
        return None

    # 모든 소스의 데이터를 날짜 가로축 기준(axis=1)으로 결합
    total_df = pd.concat(all_dfs, axis=1)
    total_df = total_df.dropna(how="all")

    # 최근 7영업일 슬라이싱 및 최근 날짜가 맨 아래로 가도록 오름차순 정렬
    total_df = total_df.tail(7).sort_index(ascending=True)
    total_df.index = total_df.index.strftime("%Y-%m-%d")

    return total_df.round(2)


# 데이터 결합 처리
final_data = fetch_all_combined_data()

if final_data is not None:
    # 4. 서식 없는 순수 데이터용 엑셀 다운로드 버튼 배치
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        final_data.to_excel(writer, sheet_name="종합경제지표")

    st.download_button(
        label="📥 서식 없이 엑셀 파일로 바로 다운로드",
        data=buffer.getvalue(),
        file_name=f"ecos_economy_data_{datetime.date.today()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.markdown("### 🗓️ 날짜별 글로벌 지표 변동 현황 (최근 일주일)")

    # 5. 가로 스크롤 대형 표 출력
    st.dataframe(final_data, use_container_width=True, height=350)
    st.success("한국은행 ECOS 데이터와 글로벌 지표가 하나의 가로형 표로 결합되었습니다!")
else:
    st.error(
        "데이터를 로드하지 못했습니다. ECOS API 키가 정확한지 깃허브 코드를 확인해 주세요."
    )

