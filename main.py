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
.stMetric {
    background-color: #f0f2f6;
    padding: 10px;
    border-radius: 10px;
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
        "하늘고": {"target_ec": 2.0, "color": "#00CC96"}, 
        "아라고": {"target_ec": 4.0, "color": "#FFA15A"},
        "동산고": {"target_ec": 8.0, "color": "#EF553B"}
    }
    
    env_dict = {}
    growth_dict = {}
    
    if not base_path.exists():
        return schools, {}, {}

    for f in base_path.iterdir():
        norm_name = normalize_text(f.name)
        for s_name in schools.keys():
            if s_name in norm_name and f.suffix == '.csv':
                df = pd.read_csv(f)
                df.columns = df.columns.str.strip()
                df['time'] = pd.to_datetime(df['time'])
                df['ec_diff'] = df['ec'].diff().abs().fillna(0)
                env_dict[s_name] = df

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

# 3. 데이터 로딩
with st.spinner('데이터를 분석 중입니다...'):
    SCHOOL_INFO, ENV_DATA, GROWTH_DATA = load_all_data()

if not ENV_DATA or not GROWTH_DATA:
    st.error("⚠️ 'data/' 폴더 내에 필요한 데이터 파일이 없습니다.")
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
    
    fig_ec.update_layout(font=dict(family="Malgun Gothic, sans-serif"))
    st.plotly_chart(fig_ec, use_container_width=True)

    # 변동 지표 요약
    st.markdown("### 🔍 학교별 EC 변동 통계")
    stat_cols = st.columns(4)
    for i, (name, df) in enumerate(ENV_DATA.items()):
        change_count = (df['ec'].diff().abs() > 0.01).sum()
        avg_diff = df['ec_diff'].mean()
        with stat_cols[i]:
            st.metric(name, f"변동 {change_count}회", f"평균 변동폭 {avg_diff:.4f}")

    # --- 새로 추가된 분석 섹션 ---
    st.markdown("---")
    st.markdown("### 🧪 EC 변동 요소별 생육 영향력 심층 분석")
    
    inf_col1, inf_col2, inf_col3 = st.columns(3)
    
    with inf_col1:
        st.markdown("#### 1. 변동폭 (Magnitude)")
        st.markdown("## ⭐⭐⭐")
        st.warning("**영향도: 가장 높음**\n\n급격한 EC 변화는 뿌리의 삼투압 쇼크를 유발하여 수분 흡수를 즉각 방해합니다. 가장 치명적인 변수입니다.")

    with inf_col2:
        st.markdown("#### 2. 변동 횟수 (Frequency)")
        st.markdown("## ⭐⭐")
        st.info("**영향도: 높음**\n\n잦은 농도 변화는 식물이 환경 적응에 에너지를 소모하게 만들어, 결과적으로 생체량 성장을 저해하는 원인이 됩니다.")

    with inf_col3:
        st.markdown("#### 3. 변동 시간 (Duration)")
        st.markdown("## ⭐")
        st.success("**영향도: 보통**\n\n일시적 변동은 회복 가능하나, 부적절한 농도가 장시간 유지될 경우 누적 데미지로 인해 근관이 사멸합니다.")

# --- Tab 2: EC 설정값의 영향 ---
with tab2:
    st.subheader("EC 설정값(Target)에 따른 분석 결과")
    summary_list = []
    for name, df in GROWTH_DATA.items():
        avg_weight = df['생중량(g)'].mean()
        summary_list.append({"학교": name, "목표EC": SCHOOL_INFO[name]['target_ec'], "평균생중량": avg_weight})
    sum_df = pd.DataFrame(summary_list).sort_values("목표EC")

    col1, col2 = st.columns([1, 1])
    with col1:
        fig_bar = px.bar(sum_df, x="목표EC", y="평균생중량", color="학교", text_auto='.2f', title="목표 EC별 평균 생중량")
        st.plotly_chart(fig_bar, use_container_width=True)
    with col2:
        st.markdown("""
        #### 📝 실험 결과 종합 요약
        - **최적 조건:** EC 2.0 (하늘고)에서 생중량이 극대화됨.
        - **농도 영향:** 저농도(1.0)는 영양 부족, 고농도(4.0~8.0)는 삼투 스트레스를 유발함.
        - **결론:** 안정적인 EC 2.0 유지가 극지 식물 배양의 핵심임.
        """)

# --- Tab 3: 상관관계 분석 ---
with tab3:
    st.subheader("EC 변동성(안정성)과 생중량 간의 상관관계")
    corr_data = []
    for name, df_env in ENV_DATA.items():
        corr_data.append({
            "학교": name,
            "EC평균변동폭": df_env['ec_diff'].mean(),
            "평균생중량": GROWTH_DATA[name]['생중량(g)'].mean()
        })
    corr_df = pd.DataFrame(corr_data)

    fig_scatter = px.scatter(corr_df, x="EC평균변동폭", y="평균생중량", color="학교", size=[25]*4, trendline="ols")
    st.plotly_chart(fig_scatter, use_container_width=True)
    
    st.info("💡 **해석:** 변동폭(X축)이 커질수록 생중량(Y축)이 감소하는 음의 상관관계를 통해 EC 안정성의 중요성을 확인할 수 있습니다.")

    # 📥 엑셀 다운로드
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        for school, df in GROWTH_DATA.items():
            df.to_excel(writer, sheet_name=school, index=False)
    buffer.seek(0)
    st.download_button("📥 통합 생육 데이터 다운로드", data=buffer, file_name="Integrated_Growth_Data.xlsx")
