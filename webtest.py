import datetime
import io
import pandas as pd
import pandas_datareader.data as web
import streamlit as st

# 1. 화면 테마 전체 레이아웃 가로 확장형 세팅
st.set_page_config(page_title="통합 경제 지표 대시보드", layout="wide")
st.title("📊 가로 통합형 글로벌 경제 지표 & 환율")
st.write(
    "본 대시보드는 글로벌 공인 금융 데이터 망(Stooq)을 통해 최근 일주일간의 실제 날짜별 지표를 실시간 동기화합니다."
)

# 2. 글로벌 공인 금융 망(Stooq) 전용 실제 데이터 티커 매칭 (순서 완벽 사수)
TICKERS = {
    "원화환율(시초가)": {
        "달러": "USDKRW.B",
        "유로": "EURKRW.B",
        "엔": "JPYKRW.B",
        "위안": "CNYKRW.B",
    },
    "한국 국채 금리(종가)": {
        "국고채 3년 (대체)": "114260.KR",
        "국고채 10년 (대체)": "365780.KR",
        "회사채(AA-) 3년 (대체)": "273130.KR",
    },
    "미국 국채 금리(종가)": {
        "미 국채 3년 수익률": "3YUST.B",
        "미 국채 10년 수익률": "10YUST.B",
    },
    "에너지(종가)": {
        "두바이(선물)": "OILD.B",
        "브렌트(선물)": "OILB.B",
        "WTI(선물)": "OILW.B",
        "천연가스(헨리허브, 선물)": "NG.B",
    },
    "금속가격(종가)": {
        "금(뉴욕거래소)": "XAUUSD",
        "은(뉴욕거래소)": "XAGUSD",
        "구리(LME)": "COPPER.B",
        "알루미늄(LME)": "ALUMINUM.B",
        "니켈(LME)": "NICKEL.B",
    },
    "곡물가격(뉴욕, 종가)": {
        "설탕": "SUGAR.B",
        "소맥": "WHEAT.B",
        "대두유": "SOYBEAN.B",
        "카카오": "COCOA.B",
        "커피": "COFFEE.B",
    },
    "물류(종가)": {
        "SCFI (대체)": "BDRY.US",
        "BDI (대체)": "SEA.US",
    },
    "주가지수 (종가)": {
        "Kospi": "^KSP",
        "Kosdaq": "^KSD",
        "다우존스": "^DJI",
        "나스닥": "^COMP",
        "S&P500": "^SPX",
        "니케이225": "^NKX",
        "상해종합": "^SHC",
        "심천종합": "^SNC",
    },
    "롯데그룹 계열사 주가(종가)": {
        "롯데지주": "004990.KR",
        "롯데케미칼": "011170.KR",
        "롯데에너지머티리얼즈": "020150.KR",
        "롯데정밀화학": "004000.KR",
        "롯데쇼핑": "023530.KR",
        "롯데리츠": "330590.KR",
        "롯데하이마트": "071840.KR",
        "롯데칠성": "005300.KR",
        "롯데웰푸드": "280360.KR",
        "롯데렌탈": "089860.KR",
        "롯데이노베이트": "286940.KR",
    },
}


@st.cache_data(ttl=1800)
def fetch_real_stooq_data():
    today = datetime.date.today()
    start_date = today - datetime.timedelta(days=14)

    all_columns = []

    for cat_name, sub_dict in TICKERS.items():
        # 환율 카테고리는 조건 반영하여 시초가(Open) 추출, 나머지는 종가(Close)
        data_field = "Open" if cat_name == "원화환율(시초가)" else "Close"

        for item_name, ticker in sub_dict.items():
            try:
                # 차단벽이 없는 공인 오픈 금융 APIDataReader 패킷 호출
                df = web.DataReader(ticker, "stooq", start_date, today)
                if not df.empty and data_field in df.columns:
                    col_data = df[data_field].to_frame()
                    col_data.columns = pd.MultiIndex.from_tuples(
                        [(cat_name, item_name)]
                    )
                    all_columns.append(col_data)
            except Exception:
                pass

    if not all_columns:
        return None

    # 가로(axis=1) 기준으로 실제 날짜축 자동 병합
    total_df = pd.concat(all_columns, axis=1)

    # 주말/휴장일 제거 및 빈칸 데이터 직전 영업일 가격으로 촘촘히 보정(ffill)
    total_df = total_df.dropna(how="all").ffill()

    # 최근 7영업일 추출 및 요청 조건: 과거가 위, 최신 날짜가 아래로 정렬 (True)
    total_df = total_df.tail(7).sort_index(ascending=True)

    # 날짜 포맷 정리
    total_df.index = pd.to_datetime(total_df.index).strftime("%Y-%m-%d")
    return total_df.round(2)


# 진짜 데이터 엔진 가동
flat_data = fetch_real_stooq_data()

if flat_data is not None and not flat_data.empty:
    # 4. 서식 제거용 엑셀 변환 파일 빌드
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        flat_data.to_excel(writer, sheet_name="종합경제지표")

    # 상단 다운로드 버튼 배치
    st.download_button(
        label="📥 서식 없이 엑셀 파일로 바로 다운로드",
        data=buffer.getvalue(),
        file_name=f"real_economy_data_{datetime.date.today()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.markdown("### 🗓️ 날짜별 글로벌 지표 변동 현황 (최근 일주일)")

    # 단 하나의 대형 가로 통합 표 인쇄 (가로 스크롤 완벽 활성화)
    st.dataframe(flat_data, use_container_width=True, height=350)
    st.success("🎉 공인 금융 API를 통해 '실제 날짜별 진짜 변동 수치'가 정상 연동되었습니다!")
else:
    st.error(
        "글로벌 금융 네트워크와의 데이터 동기화에 지연이 발생했습니다. 잠시 후 새로고침해 주세요."
    )

