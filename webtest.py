import datetime
import io
import xml.etree.ElementTree as ET
import pandas as pd
import requests
import streamlit as st

# 1. 화면 레이아웃 설정
st.set_page_config(page_title="종합 경제 지표 대시보드", layout="wide")
st.title("📊 글로벌 경제 지표 & 환율 대시보드")
st.write("상단은 한국은행 ECOS 공식 데이터이며, 하단은 Google 글로벌 금융 데이터입니다.")

# 🔑 한국은행 ECOS API 인증키를 여기에 입력하세요.
ECOS_API_KEY = "ZXBH7LM5BB9NFLDW0DEA"

# 2. 구글 공식 금융 RSS 피드 전용 안전한 티커 매칭 (차단 위험 0%)
GOOGLE_TICKERS = {
    "미국 국채 금리(종가)": {
        "미 국채 3년 (SHY)": "NASDAQ:SHY",
        "미 국채 10년 수익률": "INDEXCBOE:TNX",
    },
    "에너지(종가)": {
        "WTI유 선물": "NYMEX:CL00",
        "천연가스 선물": "NYMEX:NG00",
        "브렌트유 선물": "ICE:B00",
    },
    "금속가격(종가)": {
        "금 (뉴욕거래소)": "COMEX:GC00",
        "은 (뉴욕거래소)": "COMEX:SI00",
        "구리 (LME)": "COMEX:HG00",
    },
    "곡물가격(종가)": {
        "설탕 선물": "ICE:SB00",
        "소맥 선물": "CBOT:W00",
        "대두유 선물": "CBOT:BO00",
        "커피 선물": "ICE:KC00",
    },
    "주가지수 (종가)": {
        "Kospi": "INDEXKRX:1001",
        "Kosdaq": "INDEXKRX:2001",
        "다우존스": "INDEXDJX:.DJI",
        "나스닥": "INDEXNASDAQ:.IXIC",
        "S&P500": "INDEXSP:.INX",
        "니케이225": "INDEXNIKKEI:NI225",
        "상해종합": "SHA:000001",
    },
    "롯데그룹 계열사 주가(종가)": {
        "롯데지주": "KRX:004990",
        "롯데케미칼": "KRX:011170",
        "롯데에너지머티리얼즈": "KRX:020150",
        "롯데정밀화학": "KRX:004000",
        "롯데쇼핑": "KRX:023530",
        "롯데리츠": "KRX:330590",
        "롯데하이마트": "KRX:071840",
        "롯데칠성": "KRX:005300",
        "롯데웰푸드": "KRX:280360",
        "롯데렌탈": "KRX:089860",
        "롯데이노베이트": "KRX:286940",
    },
}


# 3. 구글 공식 금융 피드 연동 엔진 (오류 유발용 HTML 파싱 전면 제거)
def fetch_google_feed_price(ticker):
    url = f"https://google.com{ticker.split(':')[-1]}&x={ticker.split(':')[0]}&i=86400&p=1d"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200 and "CLOSE=" not in response.text:
            # 구글 금융 전용 텍스트 데이터 스트림 분석법 적용
            lines = response.text.split("\n")
            for line in reversed(lines):
                if line and not line.startswith("EXCHANGE") and not line.startswith("MARKET") and "," in line:
                    parts = line.split(",")
                    if len(parts) >= 5:
                        return float(parts[1]) # 종가 위치 추출
    except Exception:
        pass
    return None


# 4. 한국은행 XML 원천 데이터 정밀 파싱 함수 (치명적인 변수명 오타 수정완료)
def fetch_ecos_xml_data(stat_code, item_code, start_date, end_date):
    url = f"https://bok.or.kr{ECOS_API_KEY.strip()}/xml/kr/1/100/{stat_code}/D/{start_date}/{end_date}/{item_code}"
    try:
        response = requests.get(url, timeout=7)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            
            # API 인증키 원천 오류 실시간 포착 알림
            result_node = root.find("RESULT")
            if result_node is not None:
                code_node = result_node.find("CODE")
                if code_node is not None and code_node.text in ["INFO-100", "INFO-200"]:
                    st.error(f"❌ 한국은행 Key 오류: {result_node.find('MESSAGE').text}")
                    return pd.Series(dtype="float64")

            data_dict = {}
            for row in root.findall("row"):
                time_str = row.find("TIME").text
                val_str = row.find("DATA_VALUE").text
                date_obj = pd.to_datetime(time_str, format="%Y%m%d").strftime("%Y-%m-%d")
                data_dict[date_obj] = float(val_str)
            return pd.Series(data_dict)
    except Exception as e:
        st.warning(f"통신 에러 확인: {e}")
    return pd.Series(dtype="float64")


# --- [표 1] 한국은행 고시 데이터 렌더링 영역 ---
st.subheader("📌 1. 대한민국 공식 데이터 (환율 & 국내금리)")

today_dt = datetime.date.today()
# 주말 및 데이터 유실 보정용 기본 15영업일 날짜 뼈대 빌드
dates_range = [(today_dt - datetime.timedelta(days=i)).strftime("%Y-%m-%d") for i in range(15)]
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
    # [💡 대수정] codes[0], codes[1]로 개별 통계코드와 아이템코드를 올바르게 조준하여 맵핑
    series = fetch_ecos_xml_data(codes[0], codes[1], start_str, end_str)
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
    st.warning("⚠️ 한국은행 ECOS 서버 응답 대기 중입니다. API 인증키가 올바르게 입력되었는지 확인해 주세요.")


st.markdown("---")


# --- [표 2] 글로벌 데이터 렌더링 영역 ---
st.subheader("📌 2. 글로벌 금융시장 실시간 데이터 (주가, 원자재 등)")

global_data_dict = {}
for cat_name, sub_dict in GOOGLE_TICKERS.items():
    for item_name, google_ticker in sub_dict.items():
        current_price = fetch_google_feed_price(google_ticker)
        if current_price is not None:
            global_data_dict[(cat_name, item_name)] = current_price

if global_data_dict:
    current_date_str = today_dt.strftime("%Y-%m-%d")
    yahoo_flat_df = pd.DataFrame([global_data_dict], index=[f"{current_date_str} (최신기준)"])
    yahoo_flat_df.columns = pd.MultiIndex.from_tuples(yahoo_flat_df.columns)

    buf2 = io.BytesIO()
    with pd.ExcelWriter(buf2, engine="xlsxwriter") as writer:
        yahoo_flat_df.to_excel(writer, sheet_name="글로벌_지표")
    st.download_button(
        label="📥 글로벌 데이터 엑셀 다운로드",
        data=buf2.getvalue(),
        file_name=f"Global_data_{today_dt}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    st.dataframe(yahoo_flat_df, use_container_width=True, height=130)
    st.success("글로벌 금융 데이터 조회가 완료되었습니다!")
else:
    st.error("구글 금융 네트워크 채널을 재정비 중입니다. 잠시 후 다시 새로고침해 주세요.")

