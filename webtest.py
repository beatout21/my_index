import datetime
import io
import pandas as pd
import streamlit as st
import FinanceDataReader as fdr

# =========================================================
# 페이지 설정
# =========================================================

st.set_page_config(
  page_title="글로벌 경제지표 경영 대시보드",
  layout="wide"
)

st.title("📊 글로벌 경제지표 & 환율 경영 대시보드")
st.caption("최근 7영업일 기준")

# =========================================================
# 티커 정의
# =========================================================

INDICATORS = {

  "원화환율(시초가)": {
    "달러 환율": "USD/KRW",
    "유로 환율": "EUR/KRW",
    "엔 환율": "JPY/KRW",
    "위안 환율": "CNY/KRW",
  },

  "주가지수(종가)": {
    "KOSPI": "KS11",
    "KOSDAQ": "KQ11",
    "다우존스": "DJI",
    "나스닥": "IXIC",
    "S&P500": "US500",
  },

  "롯데그룹 계열사 주가(종가)": {
    "롯데지주": "004990",
    "롯데케미칼": "011170",
    "롯데에너지머티리얼즈": "020150",
    "롯데정밀화학": "004000",
    "롯데쇼핑": "023530",
    "롯데리츠": "330590",
    "롯데하이마트": "071840",
    "롯데칠성": "005300",
    "롯데웰푸드": "280360",
    "롯데렌탈": "089860",
    "롯데이노베이트": "286940",
  },
}

# =========================================================
# 데이터 조회
# =========================================================

@st.cache_data(ttl=3600)
def get_series(symbol):

  try:

    start = datetime.date.today() - datetime.timedelta(days=60)

    df = fdr.DataReader(
      symbol,
      start.strftime("%Y-%m-%d")
    )

    if df.empty:
      return None

    if "Close" in df.columns:
      series = df["Close"]

    elif "Adj Close" in df.columns:
      series = df["Adj Close"]

    else:
      return None

    return series

  except Exception:
    return None


@st.cache_data(ttl=3600)
def load_all_data():

  data_list = []

  for category, items in INDICATORS.items():

    for name, symbol in items.items():

      series = get_series(symbol)

      if series is None:
        continue

      series.name = (category, name)

      data_list.append(series)

  if len(data_list) == 0:
    return None, None

  df = pd.concat(data_list, axis=1)

  df.columns = pd.MultiIndex.from_tuples(df.columns)

  df = df.ffill().bfill()

  recent = df.tail(8)

  diff_df = recent.diff().tail(7)

  display_df = recent.tail(7)

  return display_df.round(2), diff_df.round(2)

# =========================================================
# 색상 표시
# =========================================================

def highlight_changes(data, diff_data):

  style = pd.DataFrame(
    "",
    index=data.index,
    columns=data.columns
  )

  for col in data.columns:

    for idx in data.index:

      try:

        diff = diff_data.loc[idx, col]

        if pd.isna(diff):
          continue

        if diff > 0:

          style.loc[idx, col] = (
            "background-color:#FFEBEE;"
            "color:#D32F2F;"
            "font-weight:bold;"
          )

        elif diff < 0:

          style.loc[idx, col] = (
            "background-color:#E3F2FD;"
            "color:#1976D2;"
            "font-weight:bold;"
          )

      except Exception:
        pass

  return style

# =========================================================
# 데이터 로드
# =========================================================

data, diff_data = load_all_data()

if data is None:

  st.error("데이터를 불러오지 못했습니다.")
  st.stop()

# =========================================================
# 엑셀 다운로드
# =========================================================

col1, col2 = st.columns([4, 1])

with col1:

  st.subheader("최근 7영업일 경제지표")

with col2:

  buffer = io.BytesIO()

  with pd.ExcelWriter(
    buffer,
    engine="xlsxwriter"
  ) as writer:

    data.to_excel(
      writer,
      sheet_name="경제지표"
    )

  buffer.seek(0)

  st.download_button(
    "📥 엑셀 다운로드",
    data=buffer,
    file_name=f"CEO_Economy_Report_{datetime.date.today()}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True,
  )

# =========================================================
# 테이블 표시
# =========================================================

styled = (
  data.style
  .apply(
    lambda x: highlight_changes(data, diff_data),
    axis=None
  )
  .format(
    lambda x:
    ""
    if pd.isna(x)
    else f"{x:,.2f}"
  )
)

st.dataframe(
  styled,
  use_container_width=True,
  height=450
)

st.info(
  "🔴 상승 / 🔵 하락 자동 강조"
)

# =========================================================
# 추세 그래프
# =========================================================

st.markdown("---")
st.subheader("📈 지표 추세")

options = []

for cat, sub in data.columns:

  options.append(
    f"{cat} | {sub}"
  )

selected = st.selectbox(
  "지표 선택",
  options
)

cat, item = selected.split(" | ")

series = data[(cat, item)]

chart_df = pd.DataFrame(
  {item: series}
)

st.line_chart(
  chart_df,
  use_container_width=True
)

# =========================================================
# 원본 데이터
# =========================================================

with st.expander("원본 데이터 보기"):

  st.dataframe(
    data,
    use_container_width=True
  )
