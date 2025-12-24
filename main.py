import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import unicodedata
import io

# 1. 페이지 설정 및 한글 폰트 CSS
st.set_page_config(page_title="🌱 극지식물 최적 EC 농도 연구", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;700&display=swap');
html, body, [class*="css"], .stMarkdown, .stText {
    font-family: 'Noto Sans KR', 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif !important;
}
</style>
""", unsafe_allow_html=True)

# 2. 유틸리티 함수: 한글 파일명/시트명 정규화 대응
def normalize_text(text):
    return unicodedata.normalize('NFC', text)

@st.cache_data
def load_all_data():
    base_path = Path("data")
    schools = {
        "송도고": {"ec_target": 1.0, "color": "#AB63FA"},
        "하늘고": {"ec_target": 2.0, "color": "#00CC96"}, # 최적
        "아라고": {"ec_target": 4.0, "color": "#FFA15A"},
        "동산고": {"ec_target": 8.0, "color": "#EF553B"}
    }
    
    env_data = {}
    growth_data = {}
    
    # 환경 데이터 로드 (NFC/NFD 대응)
    if base_path.exists():
        for file_path in base_path.iterdir():
            norm_name = normalize_text(file_path.name)
            for school in schools.keys():
                if school in norm_name and file_path.suffix == '.csv':
                    df = pd.read_csv(file_path)
                    df['time'] = pd.to_datetime(df['time'])
                    env_data[school] = df

        # 생육 데이터 로드 (Excel 시트명 정규화 대응)
        xlsx_files = [f for f in base_path.iterdir() if f.suffix in ['.xlsx', '.xls']]
        if xlsx_files:
            target_xlsx = xlsx_files[0] # 첫 번째 엑셀 파일 사용
            xls = pd.ExcelFile(target_xlsx)
            for sheet_name in xls.sheet_names:
                norm_sheet = normalize_text(sheet_name)
                for school in schools.keys():
                    if school in norm_sheet:
                        growth_data[school] = pd.read_excel(target_xlsx, sheet_name=sheet_name)
    
    return schools, env_data, growth_data

# 3. 데이터 로딩 실행
with st.spinner('데이터를 불러오는 중입니다...'):
    SCHOOL_INFO, ENV_DICT, GROWTH_DICT = load_all_data()

if not ENV_DICT or not GROWTH_DICT:
    st.error("데이터 파일을 찾을 수 없습니다. 'data/' 폴더 내의 파일명을 확인해주세요.")
    st.stop()

# 4. 사이드바
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
        본 연구는 극지 환경에서 자생하는 식물의 최적 생장 조건을 규명하기 위해 수행되었습니다. 
        특히 영양액의 **전기전도도(EC) 농도**가 식물의 생중량 및 지상부 길이에 미치는 영향을 
        4개 학교(송도고, 하늘고, 아라고, 동산고)의 실험 데이터를 통해 분석합니다.
        """)
    
    with col2:
        st.subheader("학교별 설정 조건")
        cond_df = pd.DataFrame([
            {"학교명": k, "EC 목표": v["ec_target"], "개체수": len(GROWTH_DICT.get(k, []))} 
            for k, v in SCHOOL_INFO.items()
        ])
        st.table(cond_df)

    st.markdown("### 🚀 주요 지표 요약")
    m1, m2, m3, m4 = st.columns(4)
    total_count = sum([len(df) for df in GROWTH_DICT.values()])
    all_env = pd.concat(ENV_DICT.values())
    
    m1.metric("총 연구 개체수", f"{total_count} 개체")
    m2.metric("평균 온도", f"{all_env['temperature'].mean():.1f} °C")
    m3.metric("평균 습도", f"{all_env['humidity'].mean():.1f} %")
    m4.metric("최적 EC 농도", "2.0 (하늘고)", delta="Best Growth")

# --- Tab 2: 환경 데이터 ---
with tab2:
    st.subheader("🌡️ 학교별 환경 지표 비교")
    
    # 데이터 집계
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

    fig_env = make_subplots(rows=2, cols=2, subplot_titles=("평균 온도 (°C)", "평균 습도 (%)", "평균 pH", "목표 vs 실측 EC"))
    
    fig_env.add_trace(go.Bar(x=summary_df["학교"], y=summary_df["평균온도"], marker_color="#636EFA"), row=1, col=1)
    fig_env.add_trace(go.Bar(x=summary_df["학교"], y=summary_df["평균습도"], marker_color="#EF553B"), row=1, col=2)
    fig_env.add_trace(go.Bar(x=summary_df["학교"], y=summary_df["평균pH"], marker_color="#00CC96"), row=2, col=1)
    
    fig_env.add_trace(go.Bar(name='목표', x=summary_df["학교"], y=summary_df["목표EC"]), row=2, col=2)
    fig_env.add_trace(go.Bar(name='실측', x=summary_df["학교"], y=summary_df["평균EC"]), row=2, col=2)

    fig_env.update_layout(height=700, showlegend=False, font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"))
    st.plotly_chart(fig_env, use_container_width=True)

    if selected_school != "전체":
        st.subheader(f"📈 {selected_school} 시계열 변화")
        target_df = ENV_DICT[selected_school]
        
        fig_line = make_subplots(specs=[[{"secondary_y": True}]])
        fig_line.add_trace(go.Scatter(x=target_df['time'], y=target_df['temperature'], name="온도"), secondary_y=False)
        fig_line.add_trace(go.Scatter(x=target_df['time'], y=target_df['humidity'], name="습도", line=dict(dash='dot')), secondary_y=True)
        fig_line.update_layout(title=f"{selected_school} 온/습도 추이")
        st.plotly_chart(fig_line, use_container_width=True)
        
        fig_ec = px.line(target_df, x='time', y='ec', title=f"{selected_school} EC 실측 추이")
        fig_ec.add_hline(y=SCHOOL_INFO[selected_school]["ec_target"], line_dash="dash", line_color="red", annotation_text="목표 EC")
        st.plotly_chart(fig_ec, use_container_width=True)

    with st.expander("📄 환경 원본 데이터 확인 및 다운로드"):
        exp_school = selected_school if selected_school != "전체" else "송도고"
        st.dataframe(ENV_DICT[exp_school])
        csv = ENV_DICT[exp_school].to_csv(index=False).encode('utf-8-sig')
        st.download_button("CSV 다운로드", data=csv, file_name=f"{exp_school}_환경데이터.csv", mime="text/csv")

# --- Tab 3: 생육 결과 ---
with tab3:
    growth_summary = []
    for name, df in GROWTH_DICT.items():
        summary = df.mean(numeric_only=True).to_dict()
        summary["학교"] = name
        summary["EC"] = SCHOOL_INFO[name]["ec_target"]
        growth_summary.append(summary)
    gs_df = pd.DataFrame(growth_summary)

    # 핵심 결과 카드
    best_row = gs_df.loc[gs_df['생중량(g)'].idxmax()]
   st.success(f"🥇 **분석 결과:** EC **{best_row['EC']}**({best_row['학교']}) 조건에서 평균 생중량 **{best_row['생중량(g)']:.2f}g**으로 가장 우수한 성장을 보였습니다.")

    # 2x2 생육 지표 비교
    fig_growth = make_subplots(rows=2, cols=2, subplot_titles=("평균 생중량(g) ⭐", "평균 잎 수(장)", "평균 지상부 길이(mm)", "실험 개체수"))
    
    colors = ['gold' if x == best_row['학교'] else '#636EFA' for x in gs_df['학교']]
    
    fig_growth.add_trace(go.Bar(x=gs_df["학교"], y=gs_df["생중량(g)"], marker_color=colors), row=1, col=1)
    fig_growth.add_trace(go.Bar(x=gs_df["학교"], y=gs_df["잎 수(장)"]), row=1, col=2)
    fig_growth.add_trace(go.Bar(x=gs_df["학교"], y=gs_df["지상부 길이(mm)"]), row=2, col=1)
    
    counts = [len(GROWTH_DICT[sch]) for sch in gs_df["학교"]]
    fig_growth.add_trace(go.Bar(x=gs_df["학교"], y=counts), row=2, col=2)

    fig_growth.update_layout(height=700, showlegend=False, font=dict(family="Malgun Gothic, sans-serif"))
    st.plotly_chart(fig_growth, use_container_width=True)

    # 상관관계 분석
    st.subheader("🧬 주요 지표 상관관계")
    col_sc1, col_sc2 = st.columns(2)
    
    all_growth_df = pd.concat([df.assign(학교=name) for name, df in GROWTH_DICT.items()])
    
    with col_sc1:
        fig_sc1 = px.scatter(all_growth_df, x="잎 수(장)", y="생중량(g)", color="학교", trendline="ols", title="잎 수 vs 생중량")
        st.plotly_chart(fig_sc1, use_container_width=True)
    with col_sc2:
        fig_sc2 = px.scatter(all_growth_df, x="지상부 길이(mm)", y="생중량(g)", color="학교", trendline="ols", title="지상부 길이 vs 생중량")
        st.plotly_chart(fig_sc2, use_container_width=True)

    with st.expander("📄 생육 원본 데이터 다운로드 (Excel)"):
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            for school, df in GROWTH_DICT.items():
                df.to_excel(writer, sheet_name=school, index=False)
        buffer.seek(0)
        st.download_button(
            label="통합 생육 데이터 XLSX 다운로드",
            data=buffer,
            file_name="전체학교_생육결과.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
