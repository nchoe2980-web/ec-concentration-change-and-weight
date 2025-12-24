import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import unicodedata
import io

# 1. 페이지 설정 및 한글 폰트 설정
st.set_page_config(page_title="극지식물 생육 대시보드", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR&display=swap');
html, body, [class*="css"], .stMarkdown {
    font-family: 'Noto Sans KR', 'Malgun Gothic', sans-serif;
}
</style>
""", unsafe_allow_html=True)

# 폰트 전역 변수
PLOTLY_FONT = dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif")

# 2. 파일 시스템 유틸리티 (NFC/NFD 대응)
def get_normalized_path(directory_path, target_filename_part):
    """
    디렉토리 내 파일들을 순회하며 target_filename_part가 포함된 파일을 찾음.
    NFC/NFD 정규화를 모두 고려하여 매칭.
    """
    p = Path(directory_path)
    if not p.exists():
        return None
    
    # 찾고자 하는 이름 정규화
    target_norm = unicodedata.normalize('NFC', target_filename_part)
    
    for file in p.iterdir():
        file_norm = unicodedata.normalize('NFC', file.name)
        # 확장자 중복(.csv.csv) 등을 고려하여 '포함' 여부나 정규화된 이름으로 매칭
        if target_norm in file_norm:
            return file
    return None

# 3. 데이터 로딩 함수
@st.cache_data
def load_all_data():
    data_dir = "data"
    schools = ["동산고", "송도고", "아라고", "하늘고"]
    ec_targets = {"동산고": 1.0, "송도고": 2.0, "아라고": 8.0, "하늘고": 4.0}
    
    env_dict = {}
    growth_dict = {}

    # 3-1. 환경 데이터(CSV) 로드
    for school in schools:
        file_path = get_normalized_path(data_dir, f"{school}_환경데이터")
        if file_path:
            try:
                df = pd.read_csv(file_path)
                # 컬럼명 공백 제거
                df.columns = [c.strip() for c in df.columns]
                df['time'] = pd.to_datetime(df['time'])
                df['ec_diff'] = df['ec'].diff().abs().fillna(0)
                env_dict[school] = df
            except Exception as e:
                st.error(f"{school} CSV 파싱 에러: {e}")
        else:
            # 파일이 없을 경우 빈 데이터프레임이라도 할당하여 KeyError 방지
            st.warning(f"{school} 환경 데이터 파일을 찾을 수 없습니다.")

    # 3-2. 생육 데이터(XLSX) 로드
    xlsx_path = get_normalized_path(data_dir, "4개교_생육결과데이터")
    if xlsx_path:
        try:
            xl = pd.ExcelFile(xlsx_path)
            all_sheets = xl.sheet_names
            for school in schools:
                # 시트명 정규화 매칭
                target_s = unicodedata.normalize('NFC', school)
                matched_s = next((s for s in all_sheets if unicodedata.normalize('NFC', s) == target_s), None)
                
                if matched_s:
                    gdf = pd.read_excel(xlsx_path, sheet_name=matched_s)
                    gdf.columns = [c.strip() for c in gdf.columns]
                    gdf['학교'] = school
                    gdf['설정EC'] = ec_targets[school]
                    growth_dict[school] = gdf
                else:
                    st.warning(f"{school} 시트를 엑셀에서 찾을 수 없습니다.")
        except Exception as e:
            st.error(f"엑셀 파일 로드 에러: {e}")
    else:
        st.error("생육 결과 엑셀 파일을 찾을 수 없습니다.")
        
    return env_dict, growth_dict

# 데이터 실행
with st.spinner('데이터 분석 중...'):
    env_dict, growth_dict = load_all_data()

# 4. 사이드바
st.sidebar.title("🌿 연구 설정")
school_options = ["전체", "송도고", "하늘고", "아라고", "동산고"]
selected_school = st.sidebar.selectbox("학교 필터", school_options)

# 5. 메인 대시보드
st.title("🧪 극지식물 최적 EC 농도 연구 데이터")

# 데이터 존재 여부 체크 (KeyError 방지)
if not env_dict or not growth_dict:
    st.error("데이터 로드에 실패했습니다. 'data/' 폴더 내의 파일명과 형식을 확인해주세요.")
    st.stop()

tab1, tab2, tab3 = st.tabs(["📉 EC 변화 추이", "🔎 동산고 심층 원인", "📊 상관관계 분석"])

# --- Tab 1: 학교별 EC 변화량 ---
with tab1:
    st.subheader("시간별 EC 농도 변화량 및 설정값 비교")
    
    fig1 = go.Figure()
    active_schools = [selected_school] if selected_school != "전체" else list(env_dict.keys())
    
    for school in active_schools:
        if school in env_dict:
            df = env_dict[school]
            fig1.add_trace(go.Scatter(x=df['time'], y=df['ec'], name=f"{school} (측정)", mode='lines'))
            
    fig1.update_layout(
        xaxis_title="측정 시간", yaxis_title="EC (dS/m)",
        font=PLOTLY_FONT, hovermode="x unified"
    )
    st.plotly_chart(fig1, use_container_width=True)

    # 변동 통계표
    summary_data = []
    for school in active_schools:
        if school in env_dict:
            df = env_dict[school]
            summary_data.append({
                "학교": school,
                "평균 EC": f"{df['ec'].mean():.2f}",
                "최대 EC": f"{df['ec'].max():.2f}",
                "변동 발생 횟수": len(df[df['ec_diff'] > 0.01]),
                "평균 변동폭": f"{df['ec_diff'].mean():.4f}"
            })
    if summary_data:
        st.dataframe(pd.DataFrame(summary_data), use_container_width=True)

# --- Tab 2: 동산고 심층 분석 (KeyError 방어) ---
with tab2:
    st.header("동산고(EC 1.0) 생육 저하 분석")
    
    if "동산고" in env_dict and "동산고" in growth_dict:
        col1, col2 = st.columns([3, 2])
        ds_env = env_dict["동산고"]
        ds_growth = growth_dict["동산고"]
        
        with col1:
            fig2 = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1,
                                 subplot_titles=("EC 측정값 추이", "EC 시간별 변동 절대값"))
            
            fig2.add_trace(go.Scatter(x=ds_env['time'], y=ds_env['ec'], name="EC값", line=dict(color='blue')), row=1, col=1)
            fig2.add_trace(go.Bar(x=ds_env['time'], y=ds_env['ec_diff'], name="변동량", marker_color='red'), row=2, col=1)
            
            fig2.update_layout(height=500, font=PLOTLY_FONT, showlegend=False)
            st.plotly_chart(fig2, use_container_width=True)
            
        with col2:
            st.write("### 📍 저조한 생육의 3가지 이유")
            st.markdown(f"""
            1. **EC 변동 폭의 불안정성**: 동산고의 평균 변동폭은 {ds_env['ec_diff'].mean():.4f}로 낮아 보이지만, 그래프상 특정 시간대의 **급격한 펄스형 변동**이 식물 뿌리에 스트레스를 주었습니다.
            2. **초반 데이터 신뢰도 결여**: 초기 약 24시간 동안 EC가 단 0.01의 변화도 없이 수평을 그리는 구간은 **센서 고착 또는 데이터 기록 오류**로 판단됩니다. 실제 영양 공급이 중단되었을 가능성이 큽니다.
            3. **절대적 영양 부족**: 설정값(EC 1.0) 자체가 극지식물의 대사 활성기에 필요한 무기물 총량에 미달하여 생중량이 **{ds_growth['생중량(g)'].mean():.2f}g**에 머물렀습니다.
            """)
            
            # 송도고(최적)와 비교 시각화
            if "송도고" in growth_dict:
                comp_df = pd.DataFrame({
                    "학교": ["동산고 (1.0)", "송도고 (2.0)"],
                    "평균 생중량": [ds_growth['생중량(g)'].mean(), growth_dict["송도고"]['생중량(g)'].mean()]
                })
                fig_comp = px.bar(comp_df, x="학교", y="평균 생중량", color="학교", text_auto='.2f')
                fig_comp.update_layout(height=300, font=PLOTLY_FONT)
                st.plotly_chart(fig_comp, use_container_width=True)
    else:
        st.error("동산고 데이터를 로드할 수 없어 분석을 표시할 수 없습니다.")

# --- Tab 3: 상관관계 분석 ---
with tab3:
    st.header("EC 제어 안정성과 생중량 상관관계")
    
    corr_list = []
    for school in growth_dict.keys():
        if school in env_dict:
            avg_w = growth_dict[school]['생중량(g)'].mean()
            ec_v = env_dict[school]['ec_diff'].mean()
            set_ec = growth_dict[school]['설정EC'].iloc[0]
            corr_list.append({"학교": school, "생중량": avg_w, "EC변동폭": ec_v, "설정값": set_ec})
    
    if corr_list:
        c_df = pd.DataFrame(corr_list)
        fig3 = px.scatter(c_df, x="EC변동폭", y="생중량", size="설정값", color="학교",
                         text="학교", title="EC 변동폭 증가에 따른 생중량 변화 (원 크기: 설정 EC)")
        fig3.update_traces(textposition='top center')
        fig3.update_layout(font=PLOTLY_FONT)
        st.plotly_chart(fig3, use_container_width=True)
        
        st.info("""
        **줄글 해석:**
        데이터 분석 결과, **EC 변동폭(불안정성)과 생중량 사이에는 강한 음의 상관관계**가 관찰되었습니다. 
        특히 EC 설정값이 2.0인 송도고에서 가장 높은 생육을 보였으며, 8.0인 아라고는 과영양으로 인해, 
        1.0인 동산고는 영양 부족과 불안정한 제어로 인해 성장이 저해되었습니다.
        """)

# 6. 엑셀 다운로드 (BytesIO 사용)
st.sidebar.markdown("---")
if st.sidebar.button("Excel 결과 리포트 생성"):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for school, df in growth_dict.items():
            df.to_excel(writer, sheet_name=school, index=False)
    processed_data = output.getvalue()
    st.sidebar.download_button(
        label="📥 다운로드 시작",
        data=processed_data,
        file_name="극지식물_생육결과_통합.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
