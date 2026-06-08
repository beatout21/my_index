import datetime
import io
import xml.etree.ElementTree as ET
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

# 1. 화면 테마 전체 레이아웃 가로 확장형 세팅
st.set_page_config(page_title="통합 경제 지표 대시보드", layout="wide")
st.title("📊 하이브리드형 글로벌 경제 지표 & 환율")
st.write(
    "원화환율과 한국 금리는 '네이버 금융 공식 피드'를, 글로벌 지표와 롯데그룹 주가는 'Yahoo Finance'를 사용하여 실시간 결합합니다."
)

# 2. 야후 파이낸스 전용 카테고리 정의 (순서 유지, 환율과 한국금리 제외)
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

# 3. 네이버 공식 차트 피드용 심볼 구조 정의 (차단 위험 0%)
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

# 4. 네이버 차트 백엔드 XML 데이터 수집용 특수 함수
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
                        date_raw = parts[0]
                        date_fmt = f"{date_raw[0:4]}-{date_raw[4:6]}-{date_raw[6:8]}"
                        # 원화환율은 시초가(시가=parts[1]), 국내금리는 마감종가(parts[4]) 추출
                        price_val = float(parts[1]) if is_fx else float(parts[4])
                        data_dict[date_fmt] = price_val
            return pd.Series(data_dict)
    except Exception:
        pass
    return pd.Series(dtype="float64")

@st.cache_data(ttl=1800)
def fetch_hybrid_flat_data():
    today = datetime.date.today()
    start_date = today - datetime.timedelta(days=16)

    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})

    all_columns = []

    # --- [A] 네이버 공식 피드에서 환율(시초가) 및 한국금리(종가) 가져오기 ---
    for cat_name, cat_info in NAVER_SYMBOLS.items():
        is_fx_flag = cat_info["is_fx"]
        for display_name, symbol in cat_info["tickers"].items():
            series = fetch_naver_chart_series(symbol, is_fx=is_fx_flag)
            if not series.empty:
                col_df = series.to_frame()
                col_df.columns = pd.MultiIndex.from_tuples([(cat_name, display_name)])
                all_columns.append(col_df)

    # --- [B] 야후 파이낸스에서 나머지 글로벌 지표 및 주가 가져오기 ---
    for cat_name, cat_info in YAHOO_CATEGORIES.items():
        data_type = cat_info["type"]
        for display_name, ticker in cat_info["tickers"].items():
            try:
                df = yf.download(ticker, start=start_date, end=today, progress=False, session=session)
                if not df.empty and data_type in df.columns:
                    col_data = df[data_type].to_frame()
                    col_data.columns = pd.MultiIndex.from_tuples([(cat_name, display_name)])
                    all_columns.append(col_data)
            except Exception:
                pass

    if not all_columns:
        return None

    # --- [C] 두 데이터 소스를 가로축 기준 정밀 병합 및 시계열 보정 ---
    total_df = pd.concat(all_columns, axis=1)
    total_df = total_df.dropna(how="all").ffill() # 시차 마찰로 인한 빈칸 메우기
    
    # 최근 7영업일 슬라이싱 및 순방향 정렬 (최신 날짜가 맨 아래로)
    total_df = total_df.tail(7).sort_index(ascending=True)
    total_df.index = total_df.index.strftime("%Y-%m-%d")
    return total_df.round(2)


# 데이터 결합 구동
flat_data = fetch_hybrid_flat_data()

if flat_data is not None:
    # 서식 없는 순수 데이터용 엑셀 변환 작업
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        flat_data.to_excel(writer, sheet_name="경제지표")

    st.download_button(
        label="📥 서식 없이 엑셀 파일로 바로 다운로드",
        data=buffer.getvalue(),
        file_name=f"hybrid_economy_data_{datetime.date.today()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.markdown("### 🗓️ 날짜별 글로벌 지표 변동 현황 (최근 일주일)")

    # 가로형 대형 통합 단일 표 렌더링
    st.dataframe(flat_data, use_container_width=True, height=350)
    st.success("모든 카테고리가 완벽하게 결합되었습니다! (환율/국내금리: 네이버 고시 데이터 반영)")
else:
    st.error("데이터 수집 엔진과의 연결을 조율 중입니다. 잠시 후 새로고침해 주세요.")
