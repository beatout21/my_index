import datetime
import io
import re
import urllib.request
import json
import pandas as pd
import streamlit as st

# 1. 화면 테마 전체 레이아웃 가로 확장형 세팅 (C-Level 보고용 최적화)
st.set_page_config(page_title="경제 지표 대시보드 (보고용)", layout="wide")
st.title("📊 글로벌 경제 지표 & 환율 경영 대시보드")
st.caption("최종 검증 완료 (V9) | 네이버 금융 공식 실시간 인덱스 연동 파이프라인")

# 2. 네이버 금융 공식 원본 코드 구조 (순서 고정)
CATEGORIES = {
    "원화환율(종가)": {
        "tickers": {
            "달러 환율": "FX_USDKRW",
            "유로 환율": "FX_EURKRW",
            "엔 환율": "FX_JPYKRW",
            "위안 환율": "FX_CNYKRW",
        },
    },
    "한국 국채 및 회사채 금리(종가)": {
        "tickers": {
            "국고채 3년 수익률": "CD@KRW3Y",
            "국고채 10년 수익률": "CD@KRW10Y",
            "회사채(AA-) 3년 수익률": "CD@KRW3YAA-",
        },
    },
    "미국 국채 금리(종가)": {
        "tickers": {
            "미 국채 3년 수익률": "US@YT03",
            "미 국채 10년 수익률": "US@YT10",
        },
    },
    "에너지(종가)": {
        "tickers": {
            "두바이유": "OIL_DU",    
            "브렌트유": "OIL_LCO",   
            "국제유가(WTI)": "OIL_CL", 
            "천연가스": "NG_NG",
        },
    },
    "금속가격(종가)": {
        "tickers": {
            "국제 금": "GOL_GC",
            "국제 은": "SLV_SI",
            "런던 구리(LME)": "COP_HG",
            "런던 알루미늄(LME)": "ALU_AL",
            "런던 니켈(LME)": "NIC_NI",
        },
    },
    "곡물가격(종가)": {
        "tickers": {
            "설탕": "SUG_SB",
            "소맥(밀)": "WHT_W",
            "대두유": "SOY_BO",
            "카카오": "COC_CC",
            "커피": "COF_KC",
        },
    },
    "물류 지수(종가)": {
        "tickers": {
            "BDI (발틱 건화물 지수)": "LGI@BDI",       
            "SCFI (상하이 컨테이너 운임지수)": "LGI@SCFI", 
        },
    },
    "주가지수 (종가)": {
        "tickers": {
            "Kospi": "KOSPI",
            "Kosdaq": "KOSDAQ",
            "다우존스": "SPI@DJI",
            "나스닥": "SPI@IXIC",
            "S&P500": "SPI@SPX",
            "니케이225": "NII@NI225",
            "상해종합": "SHS@000001",
        },
    },
    "롯데그룹 계열사 주가(종가)": {
        "tickers": {
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
    },
}

@st.cache_data(ttl=1800)
def fetch_naver_sise_json(symbol):
    """네이버 금융 API 스크래핑 안전화 레이어"""
    url = f"https://naver.com{symbol}&requestType=1&startTime=20250101&endTime={datetime.date.today().strftime('%Y%m%d')}&timeframe=day"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
    try:
        with urllib.request.urlopen(req) as response:
            raw_text = response.read().decode('utf-8').strip()
            cleaned_text = re.sub(r"([a-zA-Z0-9_@-]+)\s*:", r'"\1":', raw_text)
            cleaned_text = cleaned_text.replace("'", '"')
            
            parsed_data = json.loads(cleaned_text)
            data_rows = parsed_data[1:]
            
            dates = [datetime.datetime.strptime(row[0], "%Y%m%d").date() for row in data_rows]
            closes = [float(row[4]) for row in data_rows]
            
            df = pd.DataFrame(closes, index=pd.to_datetime(dates), columns=["Close"])
            return df.sort_index().ffill()
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=1800)
def fetch_total_flat_data():
    all_columns = []
    base_df = fetch_naver_sise_json("KOSPI")
    if base_df.empty:
        return None, None

    for cat_name, cat_info in CATEGORIES.items():
        for display_name, symbol in cat_info["tickers"].items():
            df = fetch_naver_sise_json(symbol)
            if not df.empty:
                series_data = df["Close"].reindex(base_df.index).ffill().bfill()
                series_data.name = (cat_name, display_name)
                all_columns.append(series_data)
                
    if not all_columns:
        return None, None

    total_df = pd.concat(all_columns, axis=1)
    total_df.columns = pd.MultiIndex.from_tuples(total_df.columns)
    
    # [보완 2 해결] 첫 영업일 전일 대비 마킹 누락 방지를 위해 8행 추출 후 계산용 diff 분리
    full_slice = total_df.tail(8).copy()
    diff_matrix = full_slice.diff().tail(7) # 증감 매트릭스 (7행)
    
    final_df = full_slice.tail(7).copy() # 화면 출력용 데이터 (7행)
    
    final_df.index = final_df.index.strftime("%Y-%m-%d")
    diff_matrix.index = diff_matrix.index.strftime("%Y-%m-%d")
    
    return final_df.round(2), diff_matrix.round(2)


# 데이터 결합 구동
flat_data, global_diff = fetch_total_flat_data()

if flat_data is not None:
    # ----------------------------------------------------
    # [기능 1] 상단 레이아웃 및 보고용 엑셀 출력
    # ----------------------------------------------------
    col_top1, col_top2 = st.columns([3, 1])
    with col_top1:
        st.markdown("### 🗓️ 날짜별 글로벌 지표 변동 현황 (최근 7영업일 마감 기준)")
    with col_top2:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            flat_data.to_excel(writer, sheet_name="경제지표")

        st.download_button(
            label="📥 경영 보고용 엑셀 다운로드 (Clean File)",
            data=buffer.getvalue(),
            file_name=f"CEO_Economy_Report_{datetime.date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    # ----------------------------------------------------
    # [기능 2] 조건부 스타일링 (CEO 가독성 극대화)
    # ----------------------------------------------------
    def highlight_diff(val):
        style_df = pd.DataFrame('', index=flat_data.index, columns=flat_data.columns)
        for col in flat_data.columns:
            for i in range(len(flat_data)):
                date_idx = flat_data.index[i]
                change = global_diff.at[date_idx, col]
                
                if pd.notna(change) and change != 0:
                    # 거시경제 직관에 따른 컬러 세팅 (상승=연빨강, 하락=연파랑)
                    if change > 0:
                        style_df.at[date_idx, col] = 'color: #D32F2F; background-color: #FFEBEE; font-weight: bold;'
                    elif change < 0:
                        style_df.at[date_idx, col] = 'color: #1976D2; background-color: #E3F2FD; font-weight: bold;'
        return style_df

    # 표 렌더링 스타일 컴포넌트 확정
    styled_df = flat_data.style.apply(highlight_diff, axis=None).format(lambda x: f"{x:,.2f}" if x < 100 else f"{x:,.0f}")
    st.dataframe(styled_df, use_container_width=True, height=400)
    
    st.info("💡 **가이드**: 전일 대비 수치가 **상승한 지표는 빨간색(Bold)**, **하락한 지표는 파란색(Bold)**으로 자동 강조되어 브리핑에 용이합니다.")

    # ----------------------------------------------------
    # [기능 3] 핵심 지표 실시간 대조 선형 트렌드 차트
    # ----------------------------------------------------
    st.markdown("---")
    st.markdown("### 📈 지표별 장기 추이 상세 트렌드 차트")
    
    available_metrics = [f"{cat} - {sub}" for cat, sub in flat_data.columns]
    selected_metric = st.selectbox("추세를 확인할 경제 지표 선택:", options=available_metrics, index=0)
    
    if selected_metric:
        sel_cat, sel_sub = selected_metric.split(" - ")
        chart_data = flat_data[(sel_cat, sel_sub)].copy()
        chart_df = pd.DataFrame(chart_data)
        chart_df.columns = [sel_sub]
        st.line_chart(chart_df, use_container_width=True)

else:
    st.error("금융 데이터 파이프라인 점검 중입니다. 네이버 금융 백엔드 서버 상태를 확인하세요.")
