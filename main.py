import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import unicodedata
import io

# 1. 페이지 설정
st.set_page_config(page_title="극지식물 생육 대시보드", layout="wide")

# 한글 폰트 깨짐 방지 CSS
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR&display=swap');
html, body, [class*="css"], .stMarkdown {
    font-family: 'Noto Sans KR', 'Malgun Gothic', sans-serif;
}
</style>
""", unsafe_allow_html=True)

# 유틸리티 함수: 한글 파일명 매칭 (NFC/NFD 대응)
def find_file_normalized(directory_path, target_name):
    """디렉토리 내 파일들을 순회하며 NFC/NFD 정규화를 거쳐 파일 매칭"""
    p = Path(directory_path)
    if not p.exists():
        return None
    
    target_norm = unicodedata.normalize('NFC', target_name)
    for file in p.iterdir():
        file_norm = unicodedata.normalize('NFC', file.name)
        if file_norm == target_norm:
            return file
    return None

# 2. 데이터 로딩 함수
@st.cache_data
def load_data():
    data_dir = "data"
    schools = ["동산고", "송도고", "아라고", "하늘고"]
    ec_targets = {"동산고": 1.0, "송도고": 2.0, "아라고": 8.0, "하늘고": 4.0}
    
    env_data = {}
    growth_data = {}
    
    # 환경 데이터 로드 (CSV)
    for school in schools:
        file_path = find_file_normalized(data_dir, f"{school}_환경데이터.csv")
        if file_path:
            df = pd.read_csv(file_path)
            df['time'] = pd.to_datetime(df['time'])
            # EC 변화량 계산 (이전 시간과의 차이의 절대값)
            df['ec_diff'] = df['ec'].diff().abs().fillna(0)
            env_data[school] = df
        else:
            st.error(f"환경 데이터 파일을 찾을 수 없습니다: {school}")

    # 생육 데이터 로드 (XLSX)
    xlsx_path = find_file_normalized(data_dir, "4개교_생육결과데이터.xlsx")
    if xlsx_path:
        xl = pd.ExcelFile(xlsx_path)
        # 시트명 정규화하여 매칭
        sheet_names = xl.sheet_names
        for school in schools:
            target_sheet = unicodedata.normalize('NFC', school)
            matched_sheet = next((s for s in sheet_names if unicodedata.normalize('NFC', s) == target_sheet), None)
            
            if matched_sheet:
                growth_df = pd.read_excel(xlsx_path, sheet_name=matched_sheet)
                growth_df['학교'] = school
                growth_df['설정EC'] = ec_targets[school]
                growth_data[school] = growth_df
            else:
                st.error(f"엑셀 시트를 찾을 수 없습니다: {school}")
    else:
        st.error("생육 결과 데이터(xlsx) 파일을 찾을 수 없습니다.")
        
    return env_data, growth_data

# 데이터 로딩 실행
with st.spinner('데이터를 불러오는 중입니다...'):
    env_dict, growth_dict = load_data()

# 3. 사이드바 설정
st.sidebar.title("🔍 분석 필터")
school_options = ["전체", "송도고", "하늘고", "아라고", "동산고"]
selected_school = st.sidebar.selectbox("학교 선택", school_options)

st.title("🌱 EC 농도 변화량에 따른 극지식물 생육 변화")

# 4. 탭 구성
tab1, tab2, tab3 = st.tabs(["📈 학교별 EC 변화량", "🧐 동산고 심층 분석", "📊 상관관계 분석"])

# 공통 폰트 설정
plotly_font = dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif")

# --- Tab 1: 학교별 EC 농도 변화량 ---
with tab1:
    st.header("시간에 따른 EC 농도 변화")
    
    fig1 = go.Figure()
    display_schools = [selected_school] if selected_school != "전체" else ["동산고", "송도고", "아라고", "하늘고"]
    
    for school in display_schools:
        if school in env_dict:
            df = env_dict[school]
            fig1.add_trace(go.Scatter(x=df['time'], y=df['ec'], name=school, mode='lines'))
    
    fig1.update_layout(
        title="학교별 EC 측정값 추이",
        xaxis_title="시간", yaxis_title="EC (dS/m)",
        font=plotly_font,
        hovermode="x unified"
    )
    st.plotly_chart(fig1, use_container_width=True)

    # EC 변동 통계표
    st.subheader("EC 변동성 통계")
    stats_list = []
    for school in display_schools:
        if school in env_dict:
            df = env_dict[school]
            stats_list.append({
                "학교": school,
                "평균 EC": round(df['ec'].mean(), 2),
                "EC 변동 횟수": (df['ec_diff'] > 0).sum(),
                "최대 변동폭": round(df['ec_diff'].max(), 2),
                "평균 변동폭": round(df['ec_diff'].mean(), 4)
            })
    st.table(pd.DataFrame(stats_list))

# --- Tab 2: 동산고 심층 분석 ---
with tab2:
    st.header("동산고 생육 저하 원인 분석 (EC 1.0)")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        # 동산고의 큰 변동폭 시각화
        ds_env = env_dict["동산고"]
        fig2 = make_subplots(rows=2, cols=1, subplot_titles=("EC 측정값", "EC 변동량(Absolute Diff)"))
        
        fig2.add_trace(go.Scatter(x=ds_env['time'], y=ds_env['ec'], name="EC값", line=dict(color='blue')), row=1, col=1)
        fig2.add_trace(go.Bar(x=ds_env['time'], y=ds_env['ec_diff'], name="변동폭", marker_color='red'), row=2, col=1)
        
        fig2.update_layout(height=500, font=plotly_font, showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)

    with col2:
        st.subheader("동산고 생중량 저하의 3가지 핵심 이유")
        st.info("""
        **1. EC 변동 폭의 불안정성**
        동산고 데이터 분석 결과, 평균 EC는 설정값에 근접했으나 특정 구간에서 **급격한 EC 변동(Spike)**이 관찰되었습니다. 이러한 급격한 환경 변화는 극지식물의 삼투압 조절에 스트레스를 유발했습니다.

        **2. 초기 데이터 신뢰도 문제**
        초반 EC 측정값이 과도하게 일정하게 유지되는 구간이 발견되었습니다. 이는 실제 제어가 잘 된 것이 아니라 **센서 오류 또는 데이터 기록 누락**으로 해석되며, 이 시기 실제 식물은 적절한 영양 공급을 받지 못했을 가능성이 큽니다.

        **3. 낮은 EC 설정값 (EC 1.0)**
        가장 근본적인 원인으로, 송도고(EC 2.0)와 비교했을 때 설정값 자체가 낮습니다. 극지식물의 활발한 대사를 지원하기에는 **공급된 무기양분의 총량이 부족**하여 생중량 증가로 이어지지 못했습니다.
        """)

    # 학교별 생중량 비교 그래프 (하늘고/송도고 최적값 강조)
    all_growth = pd.concat(growth_dict.values())
    avg_growth = all_growth.groupby('학교')['생중량(g)'].mean().reset_index()
    
    fig_comp = px.bar(avg_growth, x='학교', y='생중량(g)', color='학교',
                     title="학교별 평균 생중량 비교 (송도고 EC 2.0 최적)")
    fig_comp.update_traces(marker_line_width=2, marker_line_color='black')
    fig_comp.update_layout(font=plotly_font)
    st.plotly_chart(fig_comp, use_container_width=True)

# --- Tab 3: 상관관계 분석 ---
with tab3:
    st.header("EC 농도 변화량과 생중량의 상관관계")
    
    # 데이터 통합 분석
    correlation_data = []
    for school, gdf in growth_dict.items():
        edf = env_dict[school]
        avg_weight = gdf['생중량(g)'].mean()
        ec_std = edf['ec'].std() # 변동성 지표
        ec_var_mean = edf['ec_diff'].mean() # 평균 변동폭
        
        correlation_data.append({
            "학교": school,
            "평균생중량": avg_weight,
            "EC변동성(표준편차)": ec_std,
            "평균변동폭": ec_var_mean,
            "설정EC": gdf['설정EC'].iloc[0]
        })
    
    corr_df = pd.DataFrame(correlation_data)
    
    fig3 = px.scatter(corr_df, x="평균변동폭", y="평균생중량", text="학교", size="설정EC",
                     color="학교", title="EC 변동폭과 생중량의 관계")
    fig3.update_traces(textposition='top center')
    fig3.update_layout(font=plotly_font)
    st.plotly_chart(fig3, use_container_width=True)
    
    st.write("""
    ### 📝 종합 분석 의견
    1. **EC 설정값의 중요성**: 실험 결과 **EC 2.0(송도고)** 환경에서 극지식물의 생중량이 가장 높게 나타났습니다. EC 1.0(동산고)은 영양 부족, EC 8.0(아라고)은 과잉 공급으로 인한 성장이 저해되는 경향을 보입니다.
    2. **변동폭과 성장**: EC의 평균값이 적절하더라도 **평균 변동폭이 클수록 식물의 생중량은 감소**하는 음의 상관관계를 보입니다. 이는 안정적인 양분 농도 유지가 성장에 필수적임을 시사합니다.
    3. **결론**: 최적의 생육을 위해서는 **EC 2.0 수준의 농도를 유지**하되, 센서 정밀 제어를 통해 **시간당 변동폭을 최소화**하는 시스템 관리가 필요합니다.
    """)

# 5. 데이터 다운로드 기능 (XLSX)
st.sidebar.markdown("---")
if st.sidebar.button("📊 분석 결과 다운로드 (XLSX)"):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        for school, df in growth_dict.items():
            df.to_excel(writer, sheet_name=school, index=False)
    buffer.seek(0)
    
    st.sidebar.download_button(
        label="💾 파일 받기",
        data=buffer,
        file_name="극지식물_생육분석_결과.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
