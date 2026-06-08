import datetime
import pandas as pd
import streamlit as st
import yfinance as yf

# 1. 스트림릿 모바일/웹 화면 타이틀 설정
st.set_page_config(page_title="경제 지표 대시보드", layout="centered")
st.title("📊 실시간 주요 경제 지표 & 환율")
st.write("최근 일주일간의 주요 경제 지표 종가와 환율 시초가를 보여줍니다.")

# 2. 데이터 티커 정의
INDEX_TICKERS = {
    "코스피 (KOSPI)": "^KS11",
    "S&P 500": "^GSPC",
    "나스닥 (NASDAQ)": "^IXIC",
}

CURRENCY_TICKERS = {
    "달러/원 (USD)": "KRW=X",
    "유로/원 (EUR)": "EURKRW=X",
    "엔/원 (100JPY)": "JPYKRW=X",
    "위안/원 (CNY)": "CNYKRW=X",
}


@st.cache_data(ttl=3600)  # 1시간 동안 데이터를 기억하여 로딩 속도 향상
def load_data():
    today = datetime.date.today()
    start_date = today - datetime.timedelta(days=7)

    index_df_list = []
    for name, ticker in INDEX_TICKERS.items():
        try:
            data = yf.download(
                ticker, start=start_date, end=today, progress=False
            )
            if not data.empty:
                close_data = data["Close"].copy()
                close_data.columns = [f"{name} (종가)"]
                index_df_list.append(close_data)
        except Exception:
            pass

    currency_df_list = []
    for name, ticker in CURRENCY_TICKERS.items():
        try:
            data = yf.download(
                ticker, start=start_date, end=today, progress=False
            )
            if not data.empty:
                open_data = data["Open"].copy()
                open_data.columns = [f"{name} (시초가)"]
                currency_df_list.append(open_data)
        except Exception:
            pass

    if not index_df_list and not currency_df_list:
        return None

    final_df = pd.concat(index_df_list + currency_df_list, axis=1)
    final_df = final_df.dropna(how="all").sort_index(ascending=False)
    final_df.index = final_df.index.strftime("%Y-%m-%d")
    return final_df.round(2)


# 3. 화면에 데이터 표 그리기
data = load_data()

if data is not None:
    # 모바일에서 보기 좋게 확장형 표로 렌더링
    st.dataframe(data, use_container_width=True)
    st.success("최신 데이터 업데이트 완료!")
else:
    st.error("데이터를 가져오지 못했습니다. 잠시 후 다시 시도해 주세요.")
