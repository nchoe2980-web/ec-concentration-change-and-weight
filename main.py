import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import unicodedata
import io

# 1. 페이지 설정 및 한글 폰트 CSS 적용 (Streamlit Cloud 환경 대응)
st.set_page_config(page_title="🌱 극지식물 최적 EC 농도 연구", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;700&display=swap');
html, body, [class*="css"], .stMarkdown, .stText {
    font-family: 'Noto Sans KR', 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif !important;
}
</style>
""", unsafe_allow_html=True)

# 2. 유틸리티 함수: 한글 파일명/시트명 정규화(NFC) 대응
def normalize_text(text):
    return unicodedata.normalize('NFC', str(text))

@st.cache_data
def load_all_data():
    base_path = Path("data")
    schools = {
        "송도고": {"ec_target": 1.0, "color": "#AB63FA"},
        "하늘고": {"ec_target": 2.0, "color": "#00CC96"}, # 최적 EC
        "아라고": {"ec_target": 4.0, "color": "#FFA15A"},
        "동산고": {"ec_target": 8.0, "color": "#EF553B"}
    }
    
    env_data = {}
    growth_data = {}
    
    if not base_path.exists():
        return schools, env_data, growth_data

    # 📁 환경 데이터 로드 (CSV)
    for file_path in base_path.iterdir():
        norm_name = normalize_text(file_path.name)
        for school in schools.keys():
            if school in norm_name and file_path.suffix == '.csv':
                try:
                    df = pd.read_csv(file_path)
                    df.columns = df.columns.str.strip() # 컬럼명 공백 제거
                    df['time'] = pd.to_datetime(df['time'])
                    env_data[school] = df
                except Exception as e:
                    st.warning(f"{file_path.name} 로드 중 오류 발생: {e}")

    # 📁 생육 데이터 로드 (Excel)
    xlsx_files = [f for f in base_path.iterdir() if f.suffix in ['.xlsx', '.xls']]
    if xlsx_files:
        target_xlsx = xlsx_files[0]
        try:
            xls = pd.ExcelFile(target_xlsx)
            for sheet_name in xls.sheet_names:
                norm_sheet = normalize_text(sheet_name)
                for school in schools.keys():
                    if school in norm_sheet:
                        df_sheet = pd.read_excel(target_xlsx, sheet_name=sheet_name)
                        df_sheet.columns = df_sheet.columns.str.strip() # 컬럼명 공백 제거
                        growth_data[school] = df_sheet
        except Exception as e:
            st.warning(f"Excel 로드 중 오류 발생: {e}")
    
    return schools, env_data, growth_data

# 3. 데이터 로딩 실행
with st.spinner('데이터를 분석 중입니다...'):
    SCHOOL_INFO, ENV_DICT, GROWTH_DICT = load_all_data()

# 데이터 부재 시 에러 처리
if not ENV_DICT or not GROWTH_DICT:
    st.error("⚠️ 'data/' 폴더에 환경 데이터(CSV) 및 생육 결과 데이터(XLSX)가 있는지 확인해주세요.")
    st.stop()

# 4. 사이드바 구성
st.sidebar.title("📊 연구 대시보드")
school_options = ["전체"] + list(SCHOOL_INFO.keys())
selected_school = st.sidebar.selectbox("조회할 학교를 선택하세요", school_options)

# 5. 메인 타이틀
st.title("🌱 극지식물 최적 EC 농도 연구")
st.markdown("---")

tab1, tab2, tab3 = st.tabs(["📖 실험 개요", "🌡️ 환경 데이터", "📊 생육 결과"])

# --- Tab 1: 실험 개요 ---
with tab1:
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("연구 배경 및 목적")
        st.info("""
        본 연구는 극지 환경 자생 식물의 최적 생장 조건을 규명하기 위해 수행되었습니다. 
        특히 **전기전도도(EC) 농도**가 식물의 생체량 증대에 미치는 영향을 분석하며, 
        4개 학교의 실험 데이터를 통합 비교하여 최적의 양액 농도를 도출합니다.
        """)
    
    with col2:
        st.subheader("학교별 설정 조건")
        cond_list = []
        for k, v in SCHOOL_INFO.items():
            count = len(GROWTH_DICT.get(k, []))
            cond_list.append({"학교명": k, "EC 목표": v["ec_target"], "개체수": f"{count}개체"})
        st.table(pd.DataFrame(cond_list))

    st.markdown("### 🚀 주요 지표 요약")
    m1, m2, m3, m4 = st.columns(4)
    total_count = sum([len(df) for df in GROWTH_DICT.values()])
    all_env = pd.concat(ENV_DICT.values())
    
    m1.metric("총 연구 개체수", f"{total_count} 개체")
    m2.metric("평균 온도", f"{all_env['temperature'].mean():.1f} °C")
    m3.metric("평균 습도", f"{all_env['humidity'].mean():.1f} %")
    m4.metric("최적 EC 농도", "2.0 (하늘고)", delta="생중량 최대")

# --- Tab 2: 환경 데이터 ---
with tab2:
    st.subheader("🌡️ 학교별 환경 지표 비교")
    
    env_summary = []
    for name, df in ENV_DICT.items():
        env_summary.append({
            "학교": name,
            "평균온도": df['temperature'].mean(),
            "평균습도": df['humidity'].mean(),
            "평균pH": df['ph'].mean(),
            "평균EC": df['ec'].mean(),
            "목표EC": SCHOOL_INFO[name]["ec_target"]
        })
    summary_df = pd.DataFrame(env_summary)

    fig_env = make_subplots(rows=2, cols=2, 
                           subplot_titles=("평균 온도 (°C)", "평균 습도 (%)", "평균 pH", "목표 vs 실측 EC"))
    
    fig_env.add_trace(go.Bar(x=summary_df["학교"], y=summary_df["평균온도"], marker_color="#636EFA"), row=1, col=1)
    fig_env.add_trace(go.Bar(x=summary_df["학교"], y=summary_df["평균습도"], marker_color="#EF553B"), row=1, col=2)
    fig_env.add_trace(go.Bar(x=summary_df["학교"], y=summary_df["평균pH"], marker_color="#00CC96"), row=2, col=1)
    
    fig_env.add_trace(go.Bar(name='목표', x=summary_df["학교"], y=summary_df["목표EC"], marker_color="lightgray"), row=2, col=2)
    fig_env.add_trace(go.Bar(name='실측', x=summary_df["학교"], y=summary_df["평균EC"], marker_color="#AB63FA"), row=2, col=2)

    fig_env.update_layout(height=600, showlegend=False, font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"))
    st.plotly_chart(fig_env, use_container_width=True)

    if selected_school != "전체":
        st.subheader(f"📈 {selected_school} 실시간 환경 추이")
        target_df = ENV_DICT[selected_school]
        
        fig_ec = px.line(target_df, x='time', y='ec', title=f"{selected_school} EC 실측 변화")
        fig_ec.add_hline(y=SCHOOL_INFO[selected_school]["ec_target"], line_dash="dash", line_color="red", annotation_text="목표 EC")
        st.plotly_chart(fig_ec, use_container_width=True)

    with st.expander("📄 환경 데이터 원본 보기"):
        view_school = selected_school if selected_school != "전체" else "송도고"
        st.dataframe(ENV_DICT[view_school])

# --- Tab 3: 생육 결과 ---
with tab3:
    growth_list = []
    for name, df in GROWTH_DICT.items():
        summary = df.mean(numeric_only=True).to_dict()
        summary["학교"] = name
        summary["EC"] = SCHOOL_INFO[name]["ec_target"]
        growth_list.append(summary)
    gs_df = pd.DataFrame(growth_list)

    # 🥇 핵심 결과 카드 (수정된 부분: 오타 제거 및 안전한 접근)
    target_metric = "생중량(g)"
    if target_metric in gs_df.columns:
        best_row = gs_df.loc[gs_df[target_metric].idxmax()]
        st.success(f"🥇 **분석 결과:** EC **{best_row['EC']}**({best_row['학교']}) 조건에서 "
                   f"평균 생중량 **{best_row[target_metric]:.2f}g**으로 가장 우수한 성장을 보였습니다.")
    
    # 2x2 생육 지표 시각화
    fig_growth = make_subplots(rows=2, cols=2, 
                               subplot_titles=("평균 생중량(g)", "평균 잎 수(장)", "평균 지상부 길이(mm)", "평균 지하부 길이(mm)"))
    
    # 생중량은 하늘고(EC 2.0) 강조 컬러 적용
    colors = [SCHOOL_INFO[sch]["color"] for sch in gs_df["학교"]]
    
    fig_growth.add_trace(go.Bar(x=gs_df["학교"], y=gs_df.get("생중량(g)", 0), marker_color=colors), row=1, col=1)
    fig_growth.add_trace(go.Bar(x=gs_df["학교"], y=gs_df.get("잎 수(장)", 0)), row=1, col=2)
    fig_growth.add_trace(go.Bar(x=gs_df["학교"], y=gs_df.get("지상부 길이(mm)", 0)), row=2, col=1)
    fig_growth.add_trace(go.Bar(x=gs_df["학교"], y=gs_df.get("지하부길이(mm)", 0)), row=2, col=2)

    fig_growth.update_layout(height=700, showlegend=False, font=dict(family="Malgun Gothic, sans-serif"))
    st.plotly_chart(fig_growth, use_container_width=True)

    # 상관관계 산점도
    st.subheader("🧬 생장 지표 간 상관관계 분석")
    all_growth_df = pd.concat([df.assign(학교=name) for name, df in GROWTH_DICT.items()])
    
    c1, c2 = st.columns(2)
    with c1:
        fig_s1 = px.scatter(all_growth_df, x="잎 수(장)", y="생중량(g)", color="학교", trendline="ols", title="잎 수와 생중량의 관계")
        st.plotly_chart(fig_s1, use_container_width=True)
    with c2:
        fig_s2 = px.scatter(all_growth_df, x="지상부 길이(mm)", y="생중량(g)", color="학교", trendline="ols", title="지상부 길이와 생중량의 관계")
        st.plotly_chart(fig_s2, use_container_width=True)

    # 📥 데이터 다운로드
    with st.expander("📄 생육 데이터 원본 확인 및 Excel 다운로드"):
        st.dataframe(all_growth_df)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            for school, df in GROWTH_DICT.items():
                df.to_excel(writer, sheet_name=school, index=False)
        buffer.seek(0)
        st.download_button(
            label="📥 전체 생육 결과 데이터(XLSX) 다운로드",
            data=buffer,
            file_name="4개교_생육결합데이터_최종.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
