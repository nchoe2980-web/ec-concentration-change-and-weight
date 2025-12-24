import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import unicodedata
import io

# 1. 페이지 설정 및 한글 폰트 CSS 주입
st.set_page_config(page_title="EC 농도 변화에 따른 극지식물 연구", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;700&display=swap');
html, body, [class*="css"], .stMarkdown, .stText {
    font-family: 'Noto Sans KR', 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif !important;
}
</style>
""", unsafe_allow_html=True)

# 2. 데이터 처리 함수
def normalize_text(text):
    return unicodedata.normalize('NFC', str(text))

@st.cache_data
def load_all_data():
    base_path = Path("data")
    schools = {
        "송도고": {"target_ec": 1.0, "color": "#AB63FA"},
        "하늘고": {"target_ec": 2.0, "color": "#00CC96"}, # 최적
        "아라고": {"target_ec": 4.0, "color": "#FFA15A"},
        "동산고": {"target_ec": 8.0, "color": "#EF553B"}
    }
    
    env_dict = {}
    growth_dict = {}
    
    if not base_path.exists():
        return schools, {}, {}

    # 환경 데이터 로드 (CSV)
    for f in base_path.iterdir():
        norm_name = normalize_text(f.name)
        for s_name in schools.keys():
            if s_name in norm_name and f.suffix == '.csv':
                df = pd.read_csv(f)
                df.columns = df.columns.str.strip() # 컬럼 공백 제거
                df['time'] = pd.to_datetime(df['time'])
                # EC 변화량 계산 (이전 값과의 차이가 0이 아닌 경우)
                df['ec_diff'] = df['ec'].diff().abs().fillna(0)
                env_dict[s_name] = df

    # 생육 결과 데이터 로드 (XLSX)
    xlsx_files = [f for f in base_path.iterdir() if f.suffix in ['.xlsx', '.xls']]
    if xlsx_files:
        target_xlsx = xlsx_files[0]
        xls = pd.ExcelFile(target_xlsx)
        for sheet in xls.sheet_names:
            norm_sheet = normalize_text(sheet)
            for s_name in schools.keys():
                if s_name in norm_sheet:
                    df_growth = pd.read_excel(target_xlsx, sheet_name=sheet)
                    df_growth.columns = df_growth.columns.str.strip()
                    growth_dict[s_name] = df_growth
                    
    return schools, env_dict, growth_dict

# 3. 메인 로직
with st.spinner('데이터를 불러오고 분석하는 중입니다...'):
    SCHOOL_INFO, ENV_DATA, GROWTH_DATA = load_all_data()

if not ENV_DATA or not GROWTH_DATA:
    st.error("⚠️ 'data/' 폴더 내에 CSV 또는 XLSX 파일이 없습니다. 파일명과 구조를 확인해주세요.")
    st.stop()

# 사이드바
st.sidebar.title("🌿 연구 대시보드")
selected_school = st.sidebar.selectbox("학교 선택", ["전체"] + list(SCHOOL_INFO.keys()))

st.title("🌱 EC 농도 변화량에 따른 극지식물 생육 변화")
st.markdown("---")

tab1, tab2, tab3 = st.tabs(["📈 EC 농도 변화량", "💡 EC 설정값의 영향", "📊 상관관계 분석"])

# --- Tab 1: EC 농도 변화량 ---
with tab1:
    st.subheader("시간에 따른 EC 농도 변화 추이")
    if selected_school == "전체":
        fig_ec = go.Figure()
        for name, df in ENV_DATA.items():
            fig_ec.add_trace(go.Scatter(x=df['time'], y=df['ec'], name=name, line_color=SCHOOL_INFO[name]['color']))
    else:
        df = ENV_DATA[selected_school]
        fig_ec = px.line(df, x='time', y='ec', title=f"{selected_school} EC 실측 데이터")
        fig_ec.add_hline(y=SCHOOL_INFO[selected_school]['target_ec'], line_dash="dash", line_color="red", annotation_text="목표 EC")

    fig_ec.update_layout(font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"))
    st.plotly_chart(fig_ec, use_container_width=True)

    # 변동 지표 요약
    st.markdown("### 🔍 학교별 EC 변동 통계")
    stat_cols = st.columns(4)
    for i, (name, df) in enumerate(ENV_DATA.items()):
        change_count = (df['ec'].diff().abs() > 0.01).sum()
        avg_diff = df['ec_diff'].mean()
        with stat_cols[i]:
            st.metric(name, f"변동 {change_count}회", f"평균 변동폭 {avg_diff:.4f}")

# --- Tab 2: EC 설정값 자체가 생육결과에 준 영향 ---
with tab2:
    st.subheader("EC 설정값(Target)에 따른 분석 결과")
    
    # 데이터 집계
    summary_list = []
    for name, df in GROWTH_DATA.items():
        avg_weight = df['생중량(g)'].mean()
        summary_list.append({
            "학교": name, 
            "목표EC": SCHOOL_INFO[name]['target_ec'], 
            "평균생중량": avg_weight
        })
    sum_df = pd.DataFrame(summary_list).sort_values("목표EC")

    col1, col2 = st.columns([1, 1])
    with col1:
        fig_bar = px.bar(sum_df, x="목표EC", y="평균생중량", color="학교", 
                         text=sum_df["평균생중량"].apply(lambda x: f"{x:.2f}g"),
                         title="목표 EC별 평균 생중량 비교")
        fig_bar.update_layout(font=dict(family="Malgun Gothic, sans-serif"))
        st.plotly_chart(fig_bar, use_container_width=True)

    with col2:
        st.markdown(f"""
        #### 📝 실험 결과 종합 분석
        
        본 실험에서 **하늘고(EC 2.0)** 조건이 평균 생중량 **{sum_df[sum_df['학교']=='하늘고']['평균생중량'].values[0]:.2f}g**으로 가장 높은 성장을 보였습니다.
        
        * **저농도 구간 (EC 1.0):** 영양 공급 부족으로 인해 생체량 증가가 제한적임.
        * **최적 구간 (EC 2.0):** 극지 식물이 흡수하기 가장 적절한 삼투압과 영양 균형을 유지함.
        * **고농도 구간 (EC 4.0 ~ 8.0):** 농도가 높아질수록 염류 집적 및 삼투 스트레스로 인해 오히려 생중량이 감소하는 경향을 보임.
        
        **결론:** 극지 식물 배양 시 EC 2.0 설정이 가장 효율적인 생육을 유도함.
        """)

# --- Tab 3: EC 농도 변화량과 생중량의 상관관계 ---
with tab3:
    st.subheader("EC 변동성(안정성)과 생중량 간의 상관관계")
    
    # 상관관계 데이터 생성 (학교별 평균 변동폭 vs 평균 생중량)
    corr_data = []
    for name, df_env in ENV_DATA.items():
        df_growth = GROWTH_DATA[name]
        corr_data.append({
            "학교": name,
            "EC평균변동폭": df_env['ec_diff'].mean(),
            "평균생중량": df_growth['생중량(g)'].mean(),
            "표준편차": df_env['ec'].std()
        })
    corr_df = pd.DataFrame(corr_data)

    fig_scatter = px.scatter(corr_df, x="EC평균변동폭", y="평균생중량", 
                             size=[20, 20, 20, 20], color="학교",
                             hover_name="학교", trendline="ols",
                             title="EC 변동폭 증가에 따른 생중량 변화 (안정성 분석)")
    
    fig_scatter.update_layout(font=dict(family="Malgun Gothic, sans-serif"))
    st.plotly_chart(fig_scatter, use_container_width=True)
    
    st.info("""
    **💡 그래프 해석:** 산점도의 기울기가 음수일 경우, EC 농도가 자주 변하거나(불안정) 변동폭이 클수록 식물의 생육이 저해됨을 의미합니다. 
    안정적인 EC 유지가 식물의 스트레스를 줄이는 핵심 요소임을 시사합니다.
    """)

    # 다운로드 섹션
    st.markdown("---")
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        for school, df in GROWTH_DATA.items():
            df.to_excel(writer, sheet_name=school, index=False)
    buffer.seek(0)
    
    st.download_button(
        label="📥 분석 데이터 전체 다운로드 (XLSX)",
        data=buffer,
        file_name="극지식물_연구데이터_통합.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
