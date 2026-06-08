import datetime
import io
import xml.etree.ElementTree as ET
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

# 1. 화면 레이아웃 설정
st.set_page_config(page_title="종합 경제 지표 대시보드", layout="wide")
st.title("📊 글로벌 경제 지표 & 환율 대시보드")
st.write("상단은 한국은행 ECOS 공식 데이터이며, 하단은 Yahoo Finance (보안 우회형) 글로벌 데이터입니다.")

# 🔑 한국은행 ECOS API 인증키를 여기에 입력하세요.
ECOS_API_KEY = "ZXBH7LM5BB9NFLDW0DEA"

# 2. 야후 파이낸스 글로벌 지표 정의 (기존 약속된 순서 및 규격 복구)
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


# 3. 한국은행 XML 정밀 파싱 함수 (주소 오염 방지 고정형 원천 설계)
def fetch_ecos_xml_data(stat_code, item_code, start_date, end_date):
    clean_key = str(ECOS_API_KEY).strip()
    # 주소 문자열 훼손을 막기 위해 전체 도메인 주소를 완벽하게 고정
    url = f"https://bok.or.kr{clean_key}/xml/kr/1/100/{stat_code}/D/{start_date}/{end_date}/{item_code}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            
            # 인증키 문제 발생 시 한국은행에서 주는 한글 에러 그대로 표기
            result_node = root.find("RESULT")
            if result_node is not None:
                code_node = result_node.find("CODE")
                if code_node is not None and code_node.text in ["INFO-100", "INFO-200"]:
                    st.error(f"❌ 한국은행 공지: {result_node.find('MESSAGE').text}")
                    return pd.Series(dtype="float64")

            data_dict = {}
            for row in root.findall("row"):
                time_str = row.find("TIME").text
                val_str = row.find("DATA_VALUE").text
                date_obj = pd.to_datetime(time_str, format="%Y%m%d").strftime("%Y-%m-%d")
                data_dict[date_obj] = float(val_str)
            return pd.Series(data_dict)
    except Exception as e:
        st.error(f"한국은행 통신 장애 원인: {e}")
    return pd.Series(dtype="float64")


# --- [표 1] 한국은행 고시 데이터 렌더링 영역 ---
st.subheader("📌 1. 대한민국 공식 데이터 (환율 & 국내금리)")

today_dt = datetime.date.today()
dates_range = [(today_dt - datetime.timedelta(days=i)).strftime("%Y-%m-%d") for i in range(16)]
ecos_master_df = pd.DataFrame(index=sorted(dates_range))

start_str = (today_dt - datetime.timedelta(days=20)).strftime("%Y%m%d")
end_str = today_dt.strftime("%Y%m%d")

ecos_items = {
    ("원화환율(시초가)", "달러"): ("022Y013", "0000001"),
    ("원화환율(시초가)", "유로"): ("022Y013", "0000003"),
    ("원화환율(시초가)", "엔"): ("022Y013", "0000002"),
    ("원화환율(시초가)", "위안"): ("022Y013", "0000053"),
    ("한국 국채 금리(종가)", "국고채 3년"): ("060Y001", "010200000"),
    ("한국 국채 금리(종가)", "국고채 10년"): ("060Y001", "010210000"),
    ("한국 국채 금리(종가)", "회사채(AA-) 3년"): ("060Y001", "010300000"),
}

has_ecos_data = False
for col_idx, codes in ecos_items.items():
    # 튜플로 매핑되어 있던 변수를 각각의 파라미터로 명확히 분리
    s_code, i_code = codes
    series = fetch_ecos_xml_data(s_code, i_code, start_str, end_str)
    if not series.empty:
        ecos_master_df[col_idx] = ecos_master_df.index.map(series)
        has_ecos_data = True

if has_ecos_data:
    ecos_master_df = ecos_master_df.dropna(how="all").ffill().tail(7)
    ecos_master_df.columns = pd.MultiIndex.from_tuples(ecos_master_df.columns)

    buf1 = io.BytesIO()
    with pd.ExcelWriter(buf1, engine="xlsxwriter") as writer:
        ecos_master_df.to_excel(writer, sheet_name="국내_지표")
    st.download_button(
        label="📥 한국은행 데이터 엑셀 다운로드",
        data=buf1.getvalue(),
        file_name=f"BOK_data_{today_dt}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    st.dataframe(ecos_master_df, use_container_width=True, height=260)
else:
    st.warning("⚠️ 한국은행 Key 연동을 대기 중입니다. 키 값을 코드 15번째 줄에 넣어주세요.")


st.markdown("---")


# --- [표 2] 글로벌 데이터 렌더링 영역 ---
st.subheader("📌 2. 글로벌 금융시장 데이터 (주가, 원자재, 물류 등)")

# 스트림릿 공용 아이피 차단을 우회하기 위한 특수 세션 설정 장치 추가
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
})

yahoo_dfs = []
start_dt = today_dt - datetime.timedelta(days=16)

for cat_name, cat_info in YAHOO_CATEGORIES.items():
    data_type = cat_info["type"]
    for display_name, ticker in cat_info["tickers"].items():
        try:
            # 특수 세션을 주입하여 아이피 차단을 완벽 방어하는 야후 다운로드 방식 개편
            df_yf = yf.download(ticker, start=start_dt, end=today_dt, progress=False, session=session)
            if not df_yf.empty and data_type in df_yf.columns:
                col_data = df_yf[data_type].to_frame()
                col_data.columns = pd.MultiIndex.from_tuples([(cat_name, display_name)])
                yahoo_dfs.append(col_data)
        except Exception:
            pass

if yahoo_dfs:
    yahoo_master = pd.concat(yahoo_dfs, axis=1)
    yahoo_master = yahoo_master.dropna(how="all").ffill()
    yahoo_master = yahoo_master.tail(7).sort_index(ascending=True)
    yahoo_master.index = yahoo_master.index.strftime("%Y-%m-%d")

    buf2 = io.BytesIO()
    with pd.ExcelWriter(buf2, engine="xlsxwriter") as writer:
        yahoo_master.to_excel(writer, sheet_name="글로벌_지표")
    st.download_button(
        label="📥 글로벌 데이터 엑셀 다운로드",
        data=buf2.getvalue(),
        file_name=f"Global_data_{today_dt}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    st.dataframe(yahoo_master, use_container_width=True, height=280)
else:
    st.error("⚠️ 글로벌 금융 데이터 채널이 일시 차단 상태입니다. 잠시 후 새로고침해 주세요.")

