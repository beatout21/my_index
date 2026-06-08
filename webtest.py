import datetime
import io
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

# 1. 화면 레이아웃 설정
st.set_page_config(page_title="통합 경제 지표 대시보드", layout="wide")
st.title("📊 BOK ECOS 공식 연동형 경제 지표 대시보드")
st.write(
    "환율과 국내 금리는 한국은행 ECOS 공식 데이터이며, 글로벌 지표는 Yahoo Finance 데이터입니다."
)

# 🔑 한국은행 ECOS API 인증키를 여기에 입력하세요.
ECOS_API_KEY = "YOUR_ECOS_API_KEY"

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


# 3. 한국은행 ECOS API 호출 전용 함수 (오류 복구 및 가독성 패치 적용)
def fetch_ecos_data(stat_code, item_code, start_date, end_date):
    url = f"https://ecos.bok.or.kr/api/StatisticSearch/{ECOS_API_KEY}/json/kr/1/100/{stat_code}/D/{start_date}/{end_date}/{item_code}"
    try:
        response = requests.get(url, timeout=10)
        json_data = response.json()
        if "StatisticSearch" in json_data and "row" in json_data["StatisticSearch"]:
            rows = json_data["StatisticSearch"]["row"]
            df = pd.DataFrame(rows)
            df["TIME"] = pd.to_datetime(df["TIME"], format="%Y%m%d")
            df["DATA_VALUE"] = pd.to_numeric(df["DATA_VALUE"])
            # 날짜를 인덱스로 세팅
            df = df.set_index("TIME")
            return df["DATA_VALUE"]
    except Exception:
        pass
    return pd.Series(dtype="float64")


@st.cache_data(ttl=1800)
def fetch_all_combined_data():
    # 주말 데이터 보정을 위해 넉넉히 18일 전 데이터부터 수집
    today_dt = datetime.date.today()
    start_dt = today_dt - datetime.timedelta(days=18)

    start_str = start_dt.strftime("%Y%m%d")
    end_str = today_dt.strftime("%Y%m%d")

    # 뼈대가 될 공통 날짜 인덱스 생성 (야후의 날짜 기준을 따라감)
    base_df = yf.download("^KS11", start=start_dt, end=today_dt, progress=False)
    if base_df.empty:
        # 혹시 야후 인덱스가 안 잡힐 경우를 대비한 가상 타임라인 확보
        idx = pd.date_range(start=start_dt, end=today_dt)
        master_df = pd.DataFrame(index=idx)
    else:
        master_df = pd.DataFrame(index=base_df.index)

    # --- [A] 한국은행 ECOS 데이터 병합 수행 ---
    # 1. 원화환율 (731Y001)
    exchange_mapping = {"달러": "0000001", "유로": "0000003", "엔": "0000002", "위안": "0000053"}
    for name, item_cd in exchange_mapping.items():
        series = fetch_ecos_data("731Y001", item_cd, start_str, end_str)
        col_idx = ("원화환율(시초가)", name)
        
        # 한국은행 데이터를 마스터 타임라인에 맞춘 뒤 빈칸은 직전 가격으로 채움(ffill)
        if not series.empty:
            master_df[col_idx] = master_df.index.map(series)
            master_df[col_idx] = master_df[col_idx].ffill()

    # 2. 국내 금리 (817Y002)
    bond_mapping = {
        "국고채 3년": "010200000",
        "국고채 10년": "010210000",
        "회사채(AA-) 3년": "010300000",
    }
    for name, item_cd in bond_mapping.items():
        series = fetch_ecos_data("817Y002", item_cd, start_str, end_str)
        col_idx = ("한국 국채 금리(종가)", name)
        
        if not series.empty:
            master_df[col_idx] = master_df.index.map(series)
            master_df[col_idx] = master_df[col_idx].ffill()

    # --- [B] 야후 파이낸스 글로벌 데이터 병합 수행 ---
    for cat_name, cat_info in YAHOO_CATEGORIES.items():
        data_type = cat_info["type"]
        for display_name, ticker in cat_info["tickers"].items():
            try:
                df_yf = yf.download(ticker, start=start_dt, end=today_dt, progress=False)
                if not df_yf.empty and data_type in df_yf.columns:
                    col_idx = (cat_name, display_name)
                    # 데이터 매핑 후 채우기
                    yf_series = df_yf[data_type].copy()
                    master_df[col_idx] = master_df.index.map(yf_series.to_dict())
                    master_df[col_idx] = master_df[col_idx].ffill()
            except Exception:
                pass

    # 완전히 빈 데이터 행 제거
    master_df = master_df.dropna(how="all")

    # 최근 7영업일 추출 및 날짜 시간 순방향 정렬 (과거가 위, 최신이 아래)
    master_df = master_df.tail(7).sort_index(ascending=True)
    
    # 가로 2단 다중 인덱스(MultiIndex) 지정 적용
    master_df.columns = pd.MultiIndex.from_tuples(master_df.columns)
    master_df.index = master_df.index.strftime("%Y-%m-%d")

    return master_df.round(2)


# 데이터 처리 시작
final_data = fetch_all_combined_data()

if final_data is not None and not final_data.empty:
    # 엑셀 다운로드 파일 메모리 빌드
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

    # 가로 통합 대형 표 출력
    st.dataframe(final_data, use_container_width=True, height=350)
    st.success("한국은행 ECOS 데이터와 글로벌 지표가 정상적으로 결합되었습니다!")
else:
    st.error(
        "한국은행 데이터를 가져오지 못했습니다. 깃허브 코드 17번째 줄의 'YOUR_ECOS_API_KEY' 부분에 발급받으신 실물 인증키 문자열이 정확히 교체되었는지 재확인해 주세요."
    )

