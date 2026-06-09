import datetime
import io
import pandas as pd
import streamlit as st
import FinanceDataReader as fdr

# =========================================================
# 페이지 설정 (C-Level 경영 보고용 최적화)
# =========================================================
st.set_page_config(
    page_title="글로벌 경제지표 경영 대시보드",
    layout="wide"
)

st.title("📊 글로벌 경제지표 & 환율 경영 대시보드")
st.caption("최종 보충 완료 (V10) | FinanceDataReader 고성능 엔진 탑재")

# =========================================================
# 티커 정의 (사장님 지시 지표 100% 복원 및 fdr 심볼 매칭)
# =========================================================
INDICATORS = {
    "원화환율(시초가)": { # 환율은 시초가 요청 반영
        "달러 환율": "USD/KRW",
        "유로 환율": "EUR/KRW",
        "엔 환율": "JPY/KRW",
        "위안 환율": "CNY/KRW",
    },
    "한국 국채 및 회사채 금리(종가)": {
        "국고채 3년 수익률": "KR3YT=IF",
        "국고채 10년 수익률": "KR10YT=IF",
        "회사채(AA-) 3년 수익률": "KR3YAA-T=IF", 
    },
    "미국 국채 금리(종가)": {
        "미 국채 3년 수익률": "US3YT=IF",
        "미 국채 10년 수익률": "US10YT=IF",
    },
    "에너지(종가)": {
        "두바이유": "정부/Dubai", # fdr 지원 원자재 축 규칙
        "브렌트유": "COIL/BRN",
        "국제유가(WTI)": "COIL/WTI",
        "천연가스": "NG",
    },
    "금속가격(종가)": {
        "국제 금": "GOLD",
        "국제 은": "SILVER",
        "런던 구리(LME)": "COPPER",
        "런던 알루미늄(LME)": "ALUMINUM",
        "런던 니켈(LME)": "NICKEL",
    },
    "곡물가격(종가)": {
        "설탕": "SUGAR",
        "소맥(밀)": "WHEAT",
        "대두유": "SOYBEAN_OIL",
        "카카오": "COCOA",
        "커피": "COFFEE",
    },
    "물류 지수(종가)": {
        "BDI (발틱 건화물 지수)": "BDI",       
        "SCFI (상하이 컨테이너 운임지수)": "SCFI", 
    },
    "주가지수(종가)": {
        "KOSPI": "KS11",
        "KOSDAQ": "KQ11",
        "다우존스": "DJI",
        "나스닥": "IXIC",
        "S&P500": "US500",
        "니케이225": "N225",
        "상해종합": "SSEC",
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
# 데이터 조회 (환율 분기 처리 보충)
# =========================================================
@st.cache_data(ttl=3600)
def get_series(symbol, is_currency=False):
    try:
        # 영업일 기준 안전성 확보를 위해 과거 60일 데이터 수집
        start = datetime.date.today() - datetime.timedelta(days=60)
        df = fdr.DataReader(symbol, start.strftime("%Y-%m-%d"))

        if df.empty:
            return None

        # [보완] 환율 카테고리인 경우 요청사항인 시초가(Open)를 타겟팅
        if is_currency and "Open" in df.columns:
            return df["Open"]

        # 일반 지표는 종가(Close 또는 Adj Close) 타겟팅
        if "Close" in df.columns:
            return df["Close"]
        elif "Adj Close" in df.columns:
            return df["Adj Close"]
        else:
            return None
    except Exception:
        return None

@st.cache_data(ttl=3600)
def load_all_data():
    data_list = []
    
    # 기준 축(영업일 마스터 캘린더)으로 사용할 KOSPI 데이터를 선행 로드
    base_series = get_series("KS11")
    if base_series empty 또는 base_series.empty:
        # 대비용 예외 처리
        base_index = pd.date_range(end=datetime.date.today(), periods=40, freq='B')
    else:
        base_index = base_series.index

    for category, items in INDICATORS.items():
        is_currency = (category == "원화환율(시초가)")
        for name, symbol in items.items():
            series = get_series(symbol, is_currency=is_currency)
            if series is None or series.empty:
                continue
            
            # 기준 영업일 인덱스 축에 강제 동기화하여 시차 불일치 차단
            series = series.reindex(base_index).ffill().bfill()
            series.name = (category, name)
            data_list.append(series)

    if len(data_list) == 0:
        return None, None

    df = pd.concat(data_list, axis=1)
    df.columns = pd.MultiIndex.from_tuples(df.columns)
    df = df.dropna(how="all").sort_index(ascending=True)

    # [보완] 7영업일 전 첫 행까지 완벽하게 색상을 칠하기 위해 8행 분리 연산
    recent = df.tail(8).copy()
    diff_df = recent.diff().tail(7)
    display_df = recent.tail(7).copy()

    # [보완] 타임스탬프 인덱스를 깔끔한 문자열 포맷으로 변환
    display_df.index = display_df.index.strftime("%Y-%m-%d")
    diff_df.index = diff_df.index.strftime("%Y-%m-%d")

    return display_df.round(2), diff_df.round(2)

# =========================================================
# 색상 표시 (조건부 스타일링)
# =========================================================
def highlight_changes(data, diff_data):
    style = pd.DataFrame("", index=data.index, columns=data.columns)
    for col in data.columns:
        for idx in data.index:
            try:
                diff = diff_data.loc[idx, col]
                if pd.isna(diff) or diff == 0:
                    continue
                if diff > 0:
                    style.loc[idx, col] = "background-color:#FFEBEE; color:#D32F2F; font-weight:bold;"
                elif diff < 0:
                    style.loc[idx, col] = "background-color:#E3F2FD; color:#1976D2; font-weight:bold;"
            except Exception:
                pass
    return style

# =========================================================
# 데이터 로드 실행
# =========================================================
data, diff_data = load_all_data()

if data is None:
    st.error("데이터 파이프라인(FinanceDataReader) 연동에 실패했습니다.")
    st.stop()

# =========================================================
# 엑셀 다운로드 컨트롤러 배치
# =========================================================
col1, col2 = st.columns([4, 1])
with col1:
    st.subheader("🗓️ 날짜별 글로벌 지표 변동 현황 (최근 7영업일)")
with col2:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        data.to_excel(writer, sheet_name="경제지표")
    buffer.seek(0)

    st.download_button(
        "📥 경영 보고용 엑셀 다운로드",
        data=buffer,
        file_name=f"CEO_Economy_Report_{datetime.date.today()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

# =========================================================
# 테이블 표시 (가변 포맷 적용)
# =========================================================
styled = (
    data.style
    .apply(lambda x: highlight_changes(data, diff_data), axis=None)
    .format(lambda x: "" if pd.isna(x) else (f"{x:,.2f}" if x < 150 else f"{x:,.0f}"))
)

st.dataframe(styled, use_container_width=True, height=420)
st.info("💡 **안내**: 전일 대비 수치가 **상승하면 빨간색**, **하락하면 파란색**으로 강조 표시됩니다.")

# =========================================================
# 추세 그래프 (멀티인덱스 대응 보충)
# =========================================================
st.markdown("---")
st.subheader("📈 지표 추세 상세 트렌드")

options = [f"{cat} | {sub}" for cat, sub in data.columns]
selected = st.selectbox("추세를 확인할 경제 지표 선택", options)

if selected:
    cat, item = selected.split(" | ")
    chart_data = data[(cat, item)].copy()
    chart_df = pd.DataFrame({item: chart_data})
    st.line_chart(chart_df, use_container_width=True)

# =========================================================
# 원본 데이터 익스팬더
# =========================================================
with st.expander("원본 데이터 매트릭스 보기"):
    st.dataframe(data, use_container_width=True)
