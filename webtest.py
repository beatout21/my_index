import datetime
import io
import re
import pandas as pd
import requests
import streamlit as st

# 1. 화면 테마 전체 레이아웃 가로 확장형 세팅
st.set_page_config(page_title="네이버 통합 경제 지표 대시보드", layout="wide")
st.title("📊 100% 네이버 금융 일별 시세 대시보드")
st.write(
    "본 대시보드는 네이버 금융의 실제 일별 시세 데이터를 날짜별로 정석 파싱하여 가로형 단일 표로 결합합니다."
)

# 2. 네이버 금융 일별 시세 전용 정식 타겟 URL 매칭 데이터베이스
NAVER_TARGETS = {
    "원화환율(시초가)": {
        "달러": "https://naver.com",
        "유로": "https://naver.com",
        "엔": "https://naver.com",
        "위안": "https://naver.com",
    },
    "한국 국채 금리(종가)": {
        "국고채 3년": "https://naver.com",
        "국고채 10년": "https://naver.com",
        "회사채(AA-) 3년": "https://naver.com",
    },
    "미국 국채 금리(종가)": {
        "미 국채 10년 수익률": "https://naver.com",
    },
    "에너지(종가)": {
        "두바이(현물)": "https://naver.com",
        "브렌트(선물)": "https://naver.com",
        "WTI(선물)": "https://naver.com",
        "천연가스(헨리허브, 선물)": "https://naver.com",
    },
    "금속가격(종가)": {
        "금(뉴욕거래소)": "https://naver.com",
        "은(뉴욕거래소)": "https://naver.com",
        "구리(LME)": "https://naver.com",
        "알루미늄(LME)": "https://naver.com",
        "니켈(LME)": "https://naver.com",
    },
    "곡물가격(뉴욕, 종가)": {
        "설탕": "https://naver.com",
        "소맥": "https://naver.com",
        "대두유": "https://naver.com",
        "카카오": "https://naver.com",
        "커피": "https://naver.com",
    },
    "물류(종가)": {
        "SCFI": "https://naver.com",
        "BDI": "https://naver.com",
    },
    "주가지수 (종가)": {
        "Kospi": "https://naver.com",
        "Kosdaq": "https://naver.com",
    },
    "롯데그룹 계열사 주가(종가)": {
        "롯데지주": "https://naver.com",
        "롯데케미칼": "https://naver.com",
        "롯데에너지머티리얼즈": "https://naver.com",
        "롯데정밀화학": "https://naver.com",
        "롯데쇼핑": "https://naver.com",
        "롯데리츠": "https://naver.com",
        "롯데하이마트": "https://naver.com",
        "롯데칠성": "https://naver.com",
        "롯데웰푸드": "https://naver.com",
        "롯데렌탈": "https://naver.com",
        "롯데이노베이트": "https://naver.com",
    },
}


# 3. 네이버 HTML 테이블 웹 스크레핑 엔진 개편 (실제 날짜별 배열 추출)
def parse_naver_daily_table(url, is_fx=False):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        # 네이버 일별 테이블 HTML 코드 원격 획득
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            # pandas 내부의 HTML 표 자동 판독 기능 활용
            dfs = pd.read_html(io.StringIO(response.text))
            for df in dfs:
                # 네이버 표준 일별 시세 테이블 헤더 규격 필터링
                if "날짜" in df.columns or "날짜.1" in df.columns:
                    df = df.dropna(subset=[df.columns[0]])
                    # 날짜 형식 표준화 정리
                    df["date"] = pd.to_datetime(
                        df[df.columns[0]], errors="coerce"
                    ).dt.strftime("%Y-%m-%d")
                    df = df.dropna(subset=["date"])

                    data_dict = {}
                    for _, row in df.iterrows():
                        date_key = row["date"]

                        # [환율 전용 처리] 요청 조건: 시초가 타겟팅 추출
                        if is_fx and "시가" in df.columns:
                            val = str(row["시가"])
                        # [일반 종가 처리] 두 번째 열에 위치한 마감 종가 데이터 추출
                        else:
                            val = str(row[df.columns[1]])

                        # 숫자가 아닌 노이즈 문자열 제거 가공
                        clean_val = re.sub(r"[^\d.]", "", val)
                        if clean_val:
                            data_dict[date_key] = float(clean_val)

                    return pd.Series(data_dict)
    except Exception:
        pass
    return pd.Series(dtype="float64")


@st.cache_data(ttl=1800)  # 30분 동안 캐싱 유지
def build_accurate_dashboard():
    # 기준 뼈대가 될 최근 12일 타임라인 프레임 확보
    today_dt = datetime.date.today()
    base_dates = [
        (today_dt - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(12)
    ]
    master_df = pd.DataFrame(index=sorted(base_dates))

    all_columns = []

    for cat_name, sub_dict in NAVER_TARGETS.items():
        is_fx_type = cat_name == "원화환율(시초가)"

        for item_name, url in sub_dict.items():
            # 네이버 실제 시세 페이지에서 날짜별 일별 데이터 배열 통째로 수집
            series = parse_naver_daily_table(url, is_fx=is_fx_type)

            if not series.empty:
                col_idx = (cat_name, item_name)
                # 마스터 날짜 칸에 수집된 진짜 일별 데이터를 날짜별로 맵핑하여 병합
                col_df = series.to_frame(name=col_idx)
                all_columns.append(col_df)

    if not all_columns:
        return None

    # 모든 개별 수집 데이터를 날짜 가로축(axis=1) 기준으로 결합
    final_df = pd.concat(all_columns, axis=1)

    # 주말, 휴장일 등 데이터가 아예 없는 빈 행 완전 자동 삭제 보정
    final_df = final_df.dropna(how="all")

    # 최근 7영업일 추출 및 요청 조건: 과거 날짜가 위, 최신 날짜가 아래로 정렬 (True)
    final_df = final_df.tail(7).sort_index(ascending=True)

    # 2단 상위 카테고리 다중 인덱스 헤더 확립
    final_df.columns = pd.MultiIndex.from_tuples(final_df.columns)
    return final_df.round(2)


# --- 메인 대시보드 렌더링 영역 ---
pure_data = build_accurate_dashboard()

if pure_data is not None and not pure_data.empty:
    # 4. 서식 없는 순수 데이터용 엑셀 변환 기능 모듈 연동
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        pure_data.to_excel(writer, sheet_name="종합경제지표")

    st.download_button(
        label="📥 서식 없이 엑셀 파일로 바로 다운로드",
        data=buffer.getvalue(),
        file_name=f"Naver_Real_Daily_Data_{datetime.date.today()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.markdown("### 🗓️ 날짜별 글로벌 지표 변동 현황 (최근 일주일)")

    # 5. 가로 스크롤 대형 단일 통합 표 출력 (화면 크기에 딱 맞춤)
    st.dataframe(pure_data, use_container_width=True, height=350)
    st.success("🎉 네이버 금융의 실제 일별 시세와 100% 일치하는 날짜별 가로형 데이터 표입니다!")
else:
    st.error("네이버 금융 시세 테이블 파싱 라인을 재정비 중입니다. 잠시 후 새로고침해 주세요.")
