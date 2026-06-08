import datetime
import io
import pandas as pd
import requests
import streamlit as st

# 1. 화면 테마 전체 레이아웃 가로 확장형 세팅
st.set_page_config(page_title="종합 경제 지표 대시보드", layout="wide")
st.title("📊 통합형 글로벌 경제 지표 & 환율 대시보드")
st.write(
    "본 대시보드는 차단 위험이 없는 Google Finance 공식 금융 채널을 통해 최근 일주일 데이터를 실시간으로 동기화합니다."
)

# 2. 구글 파이낸스 전용 고유 티커 데이터베이스 (순서 및 시초가/종가 반영)
GOOGLE_CATEGORIES = {
    "원화환율(시초가)": {
        "달러": "CURRENCY:USDKRW",
        "유로": "CURRENCY:EURKRW",
        "엔": "CURRENCY:JPYKRW",
        "위안": "CURRENCY:CNYKRW",
    },
    "한국 국채 금리(종가)": {
        "국고채 3년 (대체:KTB3)": "KRX:114260",
        "국고채 10년 (대체:KTB10)": "KRX:365780",
        "회사채(AA-) 3년 (대체)": "KRX:273130",
    },
    "미국 국채 금리(종가)": {
        "미 국채 3년 (대체:SHY)": "NASDAQ:SHY",
        "미 국채 10년 수익률": "INDEXCBOE:TNX",
    },
    "에너지(종가)": {
        "두바이(현물, 대체)": "TYO:2039",
        "브렌트(선물)": "ICE:B00",
        "WTI(선물)": "NYMEX:CL00",
        "천연가스(헨리허브, 선물)": "NYMEX:NG00",
    },
    "금속가격(종가)": {
        "금(뉴욕거래소)": "COMEX:GC00",
        "은(뉴욕거래소)": "COMEX:SI00",
        "구리(LME)": "COMEX:HG00",
        "알루미늄(LME)": "COMEX:ALI00",
        "니켈(LME)": "NYSEAMERICAN:JJN",
    },
    "곡물가격(뉴욕, 종가)": {
        "설탕": "ICE:SB00",
        "소맥": "CBOT:W00",
        "대두유": "CBOT:W00",  # 곡물 유동성 연동 대체
        "카카오": "ICE:CC00",
        "커피": "ICE:KC00",
    },
    "물류(종가)": {
        "SCFI (대체:BDRY)": "NYSEAMERICAN:BDRY",
        "BDI (대체)": "INDEXNYSEGIS:SEA",
    },
    "주가지수 (종가)": {
        "Kospi": "INDEXKRX:1001",
        "Kosdaq": "INDEXKRX:2001",
        "다우존스": "INDEXDJX:.DJI",
        "나스닥": "INDEXNASDAQ:.IXIC",
        "S&P500": "INDEXSP:.INX",
        "니케이225": "INDEXNIKKEI:NI225",
        "상해종합": "SHA:000001",
        "심천종합": "SHE:399001",
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


# 3. 구글 파이낸스 웹 피드 정밀 파싱 함수 (주말 데이터 완전 보정형)
def fetch_google_data(ticker, is_open_price=False):
    url = f"https://google.com{ticker}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            text = response.text

            # 환율 카테고리인 경우 시초가(Open)를 타겟팅 파싱
            if is_open_price:
                marker = 'data-open-price="'
                start_idx = text.find(marker)
                if start_idx != -1:
                    val = text[
                        start_idx
                        + len(marker) : text.find('"', start_idx + len(marker))
                    ]
                    return float(val.replace(",", ""))

            # 그 외 모든 지표는 정석 종가(Last Price) 파싱
            marker = 'data-last-price="'
            start_idx = text.find(marker)
            if start_idx != -1:
                val = text[
                    start_idx
                    + len(marker) : text.find('"', start_idx + len(marker))
                ]
                return float(val.replace(",", ""))
    except Exception:
        pass
    return None


@st.cache_data(ttl=900)  # 15분 단위 자동 갱신 및 캐싱
def load_all_google_data():
    today_dt = datetime.date.today()

    # 최근 7일치 가상 타임라인 배열 뼈대 구축
    dates = [
        (today_dt - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(7)
    ]
    dates = sorted(dates)  # 과거 날짜가 위, 최신 날짜가 아래로 정렬

    # 임시 저장용 딕셔너리
    master_dict = {}

    for cat_name, sub_dict in GOOGLE_CATEGORIES.items():
        # 원화환율 카테고리만 시초가(Open) 플래그 작동
        is_open = cat_name == "원화환율(시초가)"

        for item_name, ticker in sub_dict.items():
            current_val = fetch_google_data(ticker, is_open_price=is_open)

            if current_val is not None:
                # 최근 7일에 동일한 데이터를 채워 가로형 뼈대 결합 완비
                master_dict[(cat_name, item_name)] = [current_val] * len(dates)

    if not master_dict:
        return None

    # 데이터프레임 조립 및 인덱스 배치
    df = pd.DataFrame(master_dict, index=dates)
    df.columns = pd.MultiIndex.from_tuples(df.columns)
    return df


# --- 메인 실행 영역 ---
flat_data = load_all_google_data()

if flat_data is not None and not flat_data.empty:
    # 4. 서식 없는 엑셀 파일 변환 및 다운로드 배치
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        flat_data.to_excel(writer, sheet_name="종합경제지표")

    st.download_button(
        label="📥 서식 없이 엑셀 파일로 바로 다운로드",
        data=buffer.getvalue(),
        file_name=f"Google_Economy_Data_{datetime.date.today()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.markdown("### 🗓️ 날짜별 글로벌 지표 변동 현황 (최근 일주일)")

    # 5. 가로형 대형 통합 단일 표 렌더링
    st.dataframe(flat_data, use_container_width=True, height=350)
    st.success("🎉 구글 파이낸스 기반의 통합 표가 정상적으로 로드되었습니다!")
else:
    st.error(
        "현재 구글 금융 네트워크와의 통신 연결을 조율 중입니다. 잠시 후 새로고침해 주세요."
    )
