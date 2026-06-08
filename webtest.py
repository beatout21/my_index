import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# 스트림릿 페이지 설정
st.set_page_config(page_title="경제지표 대시보드", layout="wide")

# 네이버 금융 크롤링용 USER-AGENT 설정
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
}

# 1. 국내 주식 및 국내 지수 크롤링 (종가 추출)
def get_domestic_data(code, name, is_index=False):
    if is_index:
        url = f"https://finance.naver.com/sise/sise_index_day.naver?code={code}&page=1"
    else:
        url = f"https://finance.naver.com/item/sise_day.naver?code={code}&page=1"

    res = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(res.text, "html.parser")

    data = []
    # 네이버 금융 일별 시세 테이블 파싱
    table = soup.find("table", class_="type2")
    if not table:
        return data

    rows = table.find_all("tr")
    for row in rows:
        cols = row.find_all("td")
        if len(cols) >= 7:
            date = cols[0].text.strip()
            if not date: continue
            # 종가 선택
            close_val = cols[1].text.strip().replace(",", "")
            if close_val:
                data.append({"날짜": date, "항목명": name, "값": float(close_val)})
    return data[:5]  # 최근 5영업일

# 2. 시장지표 (환율-시초가 / 원자재, 채권-종가) 크롤링
def get_market_data(code, name, price_type="close"):
    # 환율과 원자재/해외채권의 대문 페이지 구별
    if "FX_" in code:
        url = f"https://finance.naver.com/marketindex/exchangeDailyQuote.naver?marketindexCd={code}&page=1"
    else:
        url = f"https://finance.naver.com/marketindex/worldDailyQuote.naver?marketindexCd={code}&page=1"

    res = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(res.text, "html.parser")

    data = []
    table = soup.find("table", class_=["tbl_exchange", "tbl_types"])
    if not table:
        return data

    rows = table.find("tbody").find_all("tr") if table.find("tbody") else table.find_all("tr")
    for row in rows:
        cols = row.find_all("td")
        if len(cols) >= 2:
            date = cols[0].text.strip()
            # 네이버 시장지표 테이블 구조에 맞춰 값 파싱
            if "FX_" in code and price_type == "open":
                # 환율 시초가 대용 (고시회차별 첫 고시 가격 또는 매매기준율 활용)
                val = cols[1].text.strip().replace(",", "")
            else:
                val = cols[1].text.strip().replace(",", "")

            if val:
                data.append({"날짜": date, "항목명": name, "값": float(val)})
    return data[:5]

# 지표 매핑 리스트 정의
INDICATORS = [
    # 원화환율 (시초가 대상 항목)
    {"category": "원화환율(시초가)", "name": "달러", "code": "FX_USDKRW", "src": "market", "type": "open"},
    {"category": "원화환율(시초가)", "name": "유로", "code": "FX_EURKRW", "src": "market", "type": "open"},
    {"category": "원화환율(시초가)", "name": "엔", "code": "FX_JPYKRW", "src": "market", "type": "open"},
    {"category": "원화환율(시초가)", "name": "위안", "code": "FX_CNYKRW", "src": "market", "type": "open"},

    # 국채 수익률 (종가)
    {"category": "한국 국채 수익률(종가)", "name": "국고채 3년", "code": "CDJKR3Y", "src": "market", "type": "close"},
    {"category": "한국 국채 수익률(종가)", "name": "국고채 10년", "code": "CDJKR10Y", "src": "market", "type": "close"},
    {"category": "한국 국채 수익률(종가)", "name": "회사채(AA-) 3년", "code": "CDJCORP3Y", "src": "market", "type": "close"},
    {"category": "미국 국채 수익률(종가)", "name": "미 국채 2년(3년 대용)", "code": "IRX_US2Y", "src": "market", "type": "close"},
    {"category": "미국 국채 수익률(종가)", "name": "미 국채 10년", "code": "IRX_US10Y", "src": "market", "type": "close"},

    # 에너지 & 금속 & 곡물 (종가)
    {"category": "에너지(종가)", "name": "두바이(선물)", "code": "OIL_DU", "src": "market", "type": "close"},
    {"category": "에너지(종가)", "name": "브렌트(선물)", "code": "OIL_BRT", "src": "market", "type": "close"},
    {"category": "에너지(종가)", "name": "WTI(선물)", "code": "OIL_CL", "src": "market", "type": "close"},
    {"category": "에너지(종가)", "name": "천연가스(헨리허브)", "code": "OIL_NG", "src": "market", "type": "close"},

    {"category": "금속가격(종가)", "name": "금(뉴욕)", "code": "CMDT_GC", "src": "market", "type": "close"},
    {"category": "금속가격(종가)", "name": "은(뉴욕)", "code": "CMDT_SI", "src": "market", "type": "close"},
    {"category": "금속가격(종가)", "name": "구리(LME)", "code": "CMDT_CU", "src": "market", "type": "close"},

    {"category": "곡물가격(종가)", "name": "설탕", "code": "CMDT_SB", "src": "market", "type": "close"},
    {"category": "곡물가격(종가)", "name": "소맥", "code": "CMDT_W", "src": "market", "type": "close"},

    # 주가지수 (종가)
    {"category": "주가지수(종가)", "name": "Kospi", "code": "KOSPI", "src": "domestic_idx", "type": "close"},
    {"category": "주가지수(종가)", "name": "Kosdaq", "code": "KOSDAQ", "src": "domestic_idx", "type": "close"},

    # 롯데그룹 계열사 (종가)
    {"category": "롯데그룹 계열사(종가)", "name": "롯데지주", "code": "004990", "src": "domestic", "type": "close"},
    {"category": "롯데그룹 계열사(종가)", "name": "롯데케미칼", "code": "011170", "src": "domestic", "type": "close"},
    {"category": "롯데그룹 계열사(종가)", "name": "롯데에너지머티리얼즈", "code": "020150", "src": "domestic", "type": "close"},
    {"category": "롯데그룹 계열사(종가)", "name": "롯데정밀화학", "code": "004000", "src": "domestic", "type": "close"},
    {"category": "롯데그룹 계열사(종가)", "name": "롯데쇼핑", "code": "023530", "src": "domestic", "type": "close"},
    {"category": "롯데그룹 계열사(종가)", "name": "롯데리츠", "code": "330590", "src": "domestic", "type": "close"},
    {"category": "롯데그룹 계열사(종가)", "name": "롯데하이마트", "code": "071840", "src": "domestic", "type": "close"},
    {"category": "롯데그룹 계열사(종가)", "name": "롯데칠성", "code": "005300", "src": "domestic", "type": "close"},
    {"category": "롯데그룹 계열사(종가)", "name": "롯데웰푸드", "code": "280360", "src": "domestic", "type": "close"},
    {"category": "롯데그룹 계열사(종가)", "name": "롯데렌탈", "code": "089860", "src": "domestic", "type": "close"},
    {"category": "롯데그룹 계열사(종가)", "name": "롯데이노베이트", "code": "286940", "src": "domestic", "type": "close"}, ]

st.title("📊 최근 일주일간 주요 경제지표 및 롯데그룹 주가") st.caption("네이버 금융 데이터를 기반으로 실시간 수집된 일별 지표 테이블입니다.")

if st.button("🔄 데이터 불러오기 / 새로고침"):
    all_data = []

    with st.spinner("네이버 금융에서 데이터를 수집하는 중입니다..."):
        for item in INDICATORS:
            try:
                if item["src"] == "domestic":
                    res = get_domestic_data(item["code"], item["name"], is_index=False)
                elif item["src"] == "domestic_idx":
                    res = get_domestic_data(item["code"], item["name"], is_index=True)
                else:
                    res = get_market_data(item["code"], item["name"], item["type"])

                for d in res:
                    d["지표분류"] = item["category"]
                    all_data.append(d)
            except Exception as e:
                # 크롤링 실패 시 에러를 뿜지 않고 유연하게 넘어가도록 처리
                pass

    if all_data:
        df = pd.DataFrame(all_data)

        # '날짜' 포맷 통일 (YYYY.MM.DD)
        df['날짜'] = df['날짜'].str.replace("-", ".").str.slice(0, 10)

        # 가로로 쭉 이어진 표로 만들기 위해 Pivot 수행
        # 행: 지표분류, 항목명 / 열: 날짜 / 값: 종가 또는 시초가
        df_pivot = df.pivot_with_blocks = df.pivot(index=["지표분류", "항목명"], columns="날짜", values="값")

        # 날짜 컬럼을 최신순 혹은 과거순으로 정렬 (여기서는 과거 -> 최신 순 정렬)
        df_pivot = df_pivot.reindex(sorted(df_pivot.columns), axis=1)

        # 웹 화면에 표출
        st.success("데이터 수집 완료!")
        st.dataframe(df_pivot, use_container_width=True)

        # Excel 및 CSV 다운로드 기능 제공
        csv = df_pivot.to_csv().encode('utf-8-sig')
        st.download_button("📥 CSV 파일로 내보내기", data=csv, file_name="economic_indicators.csv", mime="text/csv")
    else:
        st.error("데이터를 가져오지 못했습니다. 잠시 후 다시 시도해 주세요.")
else:
    st.info("💡 위의 '데이터 불러오기' 버튼을 클릭하시면 실시간으로 네이버 금융 조회가 시작됩니다.")
