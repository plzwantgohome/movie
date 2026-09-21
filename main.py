import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

st.set_page_config(page_title="박스오피스 대시보드", layout="wide")
st.title("🎬 날짜별 박스오피스")

# ---------------------------------------------------------
# 1. 비밀 금고에서 인증키 가져오기
# ---------------------------------------------------------
# 실제 인증키는 코드에 직접 적지 않고
# Streamlit Cloud의 Secrets에 저장한다.
KOBIS_KEY = st.secrets["KOBIS_KEY"]


# ---------------------------------------------------------
# 2. 한국 시간 기준으로 선택 가능한 마지막 날짜 계산
# ---------------------------------------------------------
# Streamlit Cloud 서버는 한국 시간이 아닐 수도 있으므로
# Asia/Seoul 시간대를 직접 지정한다.
korea_now = datetime.now(ZoneInfo("Asia/Seoul"))

# 오늘 데이터는 아직 집계 전이므로
# 선택 가능한 가장 늦은 날짜는 어제이다.
yesterday = (korea_now - timedelta(days=1)).date()


# ---------------------------------------------------------
# 3. 달력에서 조회할 날짜 선택
# ---------------------------------------------------------
selected_date = st.date_input(
    "📅 박스오피스 날짜를 선택하세요",
    value=yesterday,       # 처음에는 어제를 보여 준다.
    max_value=yesterday,   # 오늘과 미래 날짜는 선택할 수 없다.
    format="YYYY-MM-DD"
)

# KOBIS API는 날짜를 YYYYMMDD 형식으로 요구한다.
target_dt = selected_date.strftime("%Y%m%d")

st.caption(
    f"조회 기준일: {selected_date.strftime('%Y-%m-%d')}"
)


# ---------------------------------------------------------
# 4. KOBIS API에 박스오피스 데이터 요청
# ---------------------------------------------------------
url = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
    "boxoffice/searchDailyBoxOfficeList.json"
)

try:
    res = requests.get(
        url,
        params={
            "key": KOBIS_KEY,
            "targetDt": target_dt
        },
        timeout=10
    )

except requests.exceptions.RequestException:
    st.error(
        "KOBIS 서버에 연결하지 못했습니다. "
        "인터넷 연결 상태나 KOBIS 서버 상태를 확인해 주세요."
    )
    st.stop()


# HTTP 요청 자체가 실패한 경우
if res.status_code != 200:
    st.error(
        f"요청이 실패했습니다. "
        f"(상태코드: {res.status_code})"
    )
    st.stop()


# ---------------------------------------------------------
# 5. 받은 데이터를 JSON 형태로 변환
# ---------------------------------------------------------
try:
    data = res.json()

except ValueError:
    st.error(
        "KOBIS 서버에서 정상적인 데이터를 받지 못했습니다. "
        "잠시 후 다시 시도해 주세요."
    )
    st.stop()


# ---------------------------------------------------------
# 6. KOBIS 오류 확인
# ---------------------------------------------------------
# KOBIS는 인증키가 틀려도 상태코드 200을 줄 수 있다.
# 이 경우 응답 안에 faultInfo가 들어 있다.
if "faultInfo" in data:
    st.error(
        "KOBIS API에서 오류가 발생했습니다. "
        "금고(Secrets)의 KOBIS_KEY가 올바른지 확인해 주세요."
    )
    st.stop()


# ---------------------------------------------------------
# 7. 영화 목록 꺼내기
# ---------------------------------------------------------
box_list = (
    data
    .get("boxOfficeResult", {})
    .get("dailyBoxOfficeList", [])
)


# 영화 목록이 비어 있는 경우
if not box_list:
    st.warning("그날은 아직 집계 전입니다")
    st.stop()


# ---------------------------------------------------------
# 8. 판다스 DataFrame으로 변환
# ---------------------------------------------------------
df = pd.DataFrame(box_list)


# ---------------------------------------------------------
# 9. 문자열로 온 숫자를 실제 숫자로 변환
# ---------------------------------------------------------
# KOBIS에서는 숫자도 문자열 형태로 보내 준다.
for col in [
    "rank",
    "rankInten",
    "audiCnt",
    "audiAcc",
    "scrnCnt",
    "showCnt"
]:
    df[col] = pd.to_numeric(
        df[col],
        errors="coerce"
    ).fillna(0).astype(int)


# 순위 순서대로 정렬
df = df.sort_values("rank").reset_index(drop=True)


# ---------------------------------------------------------
# 10. 1위 영화 정보
# ---------------------------------------------------------
top = df.iloc[0]

st.subheader(f"🏆 {selected_date.strftime('%Y-%m-%d')} 박스오피스 1위")

c1, c2, c3 = st.columns(3)

c1.metric(
    "1위 영화",
    top["movieNm"]
)

c2.metric(
    "당일 관객수",
    f"{top['audiCnt']:,}명"
)

c3.metric(
    "누적 관객",
    f"{top['audiAcc']:,}명"
)


# ---------------------------------------------------------
# 11. 표에 표시할 순위 변동 만들기
# ---------------------------------------------------------
def make_rank_change(value):
    """
    rankInten:
    양수 = 전날보다 순위 상승
    음수 = 전날보다 순위 하락
    0 = 순위 변화 없음
    """

    if value > 0:
        return f"↑ {value}"

    elif value < 0:
        return f"↓ {abs(value)}"

    else:
        return "―"


df["순위변동"] = df["rankInten"].apply(make_rank_change)


# ---------------------------------------------------------
# 12. 누적 관객 100만 명 이상 영화에 트로피 붙이기
# ---------------------------------------------------------
def add_trophy(row):
    if row["audiAcc"] >= 1_000_000:
        return f"{row['movieNm']} 🏆"
    else:
        return row["movieNm"]


df["표시영화명"] = df.apply(
    add_trophy,
    axis=1
)


# ---------------------------------------------------------
# 13. 전체 박스오피스 표 만들기
# ---------------------------------------------------------
table = df[
    [
        "rank",
        "순위변동",
        "표시영화명",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt"
    ]
].copy()


# 한글 열 이름으로 변경
table.columns = [
    "순위",
    "순위 변동",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수"
]


# ---------------------------------------------------------
# 14. 순위 변동에 색 넣기
# ---------------------------------------------------------
def color_rank_change(value):
    """
    상승 화살표는 빨간색,
    하락 화살표는 파란색으로 표시한다.
    """

    if isinstance(value, str):

        if value.startswith("↑"):
            return "color: #e53935; font-weight: bold;"

        elif value.startswith("↓"):
            return "color: #1e88e5; font-weight: bold;"

    return ""


styled_table = table.style.map(
    color_rank_change,
    subset=["순위 변동"]
)


# ---------------------------------------------------------
# 15. 표 출력
# ---------------------------------------------------------
st.subheader("📋 박스오피스 TOP 10")

st.dataframe(
    styled_table,
    hide_index=True,
    use_container_width=True,
    column_config={
        "순위": st.column_config.NumberColumn(
            "순위",
            format="%d위"
        ),
        "관객수": st.column_config.NumberColumn(
            "관객수",
            format="%d명"
        ),
        "누적관객": st.column_config.NumberColumn(
            "누적관객",
            format="%d명"
        ),
        "스크린수": st.column_config.NumberColumn(
            "스크린수",
            format="%d개"
        )
    }
)


# ---------------------------------------------------------
# 16. 관객수 상위 5편 막대그래프
# ---------------------------------------------------------
st.subheader("📈 관객수 상위 5편")

# 당일 관객수 기준으로 가장 많은 영화 5편
top5 = (
    df
    .sort_values("audiCnt", ascending=False)
    .head(5)
    [["movieNm", "audiCnt"]]
)

st.bar_chart(
    top5.set_index("movieNm")["audiCnt"],
    x_label="영화",
    y_label="관객수"
)


# ---------------------------------------------------------
# 17. 데이터 출처
# ---------------------------------------------------------
st.caption(
    "데이터 출처: 영화진흥위원회 KOBIS 영화관입장권통합전산망 Open API"
)
