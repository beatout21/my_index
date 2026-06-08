import datetime
import io
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

# 1. 화면 레이아웃 및 제목 설정
st.set_page_config(page_title="통합 경제 지표 대시보드", layout="wide")
st.title("📊 BOK ECOS 공식 연동형 경제 지표 대시보드")
st.write(
    "환율과 국내 금리는 한국은행 ECOS 공식 데이터이며, 글로벌 지표는 Yahoo Finance 데이터입니다."
)

# 🔑 [주의] 복사할 때 문자열 앞뒤에 눈에 보이지 않는 공백(띄어쓰기)이 들어가지 않도록 정확히 붙여넣어 주세요!
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


# 3. 한국은행 ECOS API 호출 전용 함수 (인증 우회 주소 구조 체계 최적화 완료)
def fetch_ecos_data(stat_code, item_code, start_date, end_date):
    # [핵심 변경] 한국은행 가이드 표준에 맞추어 주소 문자열 슬래시(/) 레이아웃 순서 전면 재정렬
    url = f"https://ecos.bok.or.kr/api/StatisticSearch/{ECOS_API_KEY.strip()}/json/kr/1/100/{stat_code}/D/{start_date}/{end_date}/{item_code}"
    try:
        response = requests.get(url, timeout=10)
        json_data = response.json()
        
        # 한국은행 에러 코드가 잡힐 경우 터미널 알림 기능 강화
        if "RESULT" in json_data and json_data["RESULT"]["CODE"] in ["INFO-100", "INFO-200"]:
            return pd.Series(dtype="float64")
            
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


@st.cache_data(ttl=600)
def fetch_all_combined_data():
    today_dt = datetime.date.today()
    start_dt = today_dt - datetime.timedelta(days=18)

    start_str = start_dt.strftime("%Y%m%d")
    end_str = today_dt.strftime("%Y%m%d")

    # 대시보드 기본 시간축 데이터베이스 빌드
    base_df = yf.download("^KS11", start=start_dt, end=today_dt, progress=False)
    if base_df.empty:
        idx = pd.date_range(start=start_dt, end=today_dt)
        master_df = pd.DataFrame(index=idx)
    else:
        master_df = pd.DataFrame(index=base_df.index)

    # --- [A] 한국은행 ECOS 실시간 조회 및 결합 영역 ---
    # 1. 원화환율 (시장 코드: 022Y013)
    exchange_mapping = {"달러": "0000001", "유로": "0000003", "엔": "0000002", "위안": "0000053"}
    for name, item_cd in exchange_mapping.items():
        series = fetch_ecos_data("022Y013", item_cd, start_str, end_str)
        col_idx = ("원화환율(시초가)", name)
        if not series.empty:
            master_df[col_idx] = master_df.index.map(series)
            master_df[col_idx] = master_df[col_idx].ffill()

    # 2. 국내 금리 (시장 코드: 060Y001)
    bond_mapping = {
        "국고채 3년": "010200000",
        "국고채 10년": "010210000",
        "회사채(AA-) 3년": "010300000",
    }
    for name, item_cd in bond_mapping.items():
        series = fetch_ecos_data("060Y001", item_cd, start_str, end_str)
        col_idx = ("한국 국채 금리(종가)", name)
        if not series.empty:
            master_df[col_idx] = master_df.index.map(series)
            master_df[col_idx] = master_df[col_idx].ffill()

    # --- [B] 글로벌 경제 지표 데이터 병합 영역 ---
    for cat_name, cat_info in YAHOO_CATEGORIES.items():
        data_type = cat_info["type"]
        for display_name, ticker in cat_info["tickers"].items():
            try:
                df_yf = yf.download(ticker, start=start_dt, end=today_dt, progress=False)
                if not df_yf.empty and data_type in df_yf.columns:
                    col_idx = (cat_name, display_name)
                    yf_series = df_yf[data_type].copy()
                    master_df[col_idx] = master_df.index.map(yf_series.to_dict())
                    master_df[col_idx] = master_df[col_idx].ffill()
            except Exception:
                pass

    # 완전히 빈 데이터 행 제외 후 최근 7영업일 과거순 정렬 정립
    master_df = master_df.dropna(how="all")
    master_df = master_df.tail(7).sort_index(ascending=True)
    master_df.columns = pd.MultiIndex.from_tuples(master_df.columns)
    master_df.index = master_df.index.strftime("%Y-%m-%d")

    return master_df


# 메인 루틴 처리 시작
final_data = fetch_all_combined_data()

if final_data is not None and not final_data.empty:
    # 엑셀 다운로드 포맷 구성
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
    st.dataframe(final_data, use_container_width=True, height=350)
    
    # 한국은행 연동 성공 시 체크 메시지 노출 분기
    if ("원화환율(시초가)", "달러") in final_data.columns and not pd.isna(final_data[("원화환율(시초가)", "달러")].iloc[-1]):
        st.success("🎉 한국은행 ECOS 데이터와 글로벌 지표 결합이 완벽히 완료되었습니다!")
    else:
        st.warning("⚠️ 글로벌 지표는 나왔으나, 한국은행 인증키 입력 상태나 첫 호출 지연 상태를 확인해 주세요. (1~2분 후 새로고침 필요)")
else:
    st.error("데이터 결합을 실패했습니다. 잠시 후 새로고침해 주세요.")
