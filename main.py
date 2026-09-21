import streamlit as st
import pandas as pd
import requests

# 날짜와 시간 계산에 사용하는 파이썬 기본 라이브러리
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ---------------------------------------------------------
# 1. 페이지 기본 설정
# ---------------------------------------------------------
st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 어제의 박스오피스")
st.caption("KOBIS 영화관입장권통합전산망 일별 박스오피스")


# ---------------------------------------------------------
# 2. 한국 시간 기준으로 '어제' 날짜 계산
# ---------------------------------------------------------
# Streamlit Cloud 서버는 한국 시간이 아닐 수 있기 때문에
# 반드시 Asia/Seoul 시간대를 직접 지정한다.
korea_now = datetime.now(ZoneInfo("Asia/Seoul"))
yesterday = korea_now.date() - timedelta(days=1)

# KOBIS API에는 YYYYMMDD 형식으로 보내야 한다.
target_date = yesterday.strftime("%Y%m%d")

# 화면에는 보기 편하게 YYYY년 MM월 DD일 형식으로 보여 준다.
display_date = yesterday.strftime("%Y년 %m월 %d일")

st.write(f"📅 **조회 기준일: {display_date}**")


# ---------------------------------------------------------
# 3. KOBIS API 데이터 가져오기
# ---------------------------------------------------------
def get_boxoffice_data(target_dt):
    """
    KOBIS 일별 박스오피스 API에 요청하고
    성공하면 영화 목록을 반환한다.

    실패하면 (None, 오류 메시지)를 반환한다.
    """

    # API 주소
    url = (
        "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
        "boxoffice/searchDailyBoxOfficeList.json"
    )

    # 인증키는 코드에 직접 쓰지 않고
    # Streamlit Secrets에서 가져온다.
    try:
        kobis_key = st.secrets["KOBIS_KEY"]
    except Exception:
        return None, (
            "KOBIS 인증키를 찾을 수 없습니다.\n\n"
            "Streamlit Cloud의 **Settings → Secrets**에서 "
            "`KOBIS_KEY`가 제대로 등록되어 있는지 확인해 주세요."
        )

    # KOBIS API에 전달할 값
    params = {
        "key": kobis_key,
        "targetDt": target_dt
    }

    try:
        # timeout을 설정해 서버가 응답하지 않을 때
        # 앱이 계속 멈춰 있는 것을 방지한다.
        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        # 404, 500 등의 HTTP 오류가 있으면 예외 발생
        response.raise_for_status()

    except requests.exceptions.Timeout:
        return None, (
            "KOBIS 서버의 응답 시간이 너무 오래 걸렸습니다.\n\n"
            "잠시 후 다시 접속해 주세요."
        )

    except requests.exceptions.RequestException as error:
        return None, (
            "KOBIS API에 연결하지 못했습니다.\n\n"
            "인터넷 연결 상태와 KOBIS 서버 상태를 확인해 주세요.\n\n"
            f"오류 정보: {error}"
        )

    # 응답 내용을 JSON으로 변환
    try:
        data = response.json()
    except ValueError:
        return None, (
            "KOBIS 서버에서 정상적인 JSON 데이터를 받지 못했습니다.\n\n"
            "잠시 후 다시 시도해 주세요."
        )

    # -----------------------------------------------------
    # 중요:
    # KOBIS는 인증키가 틀려도 HTTP 상태코드 200을 반환하고
    # 대신 faultInfo를 보내는 경우가 있다.
    # -----------------------------------------------------
    if "faultInfo" in data:
        fault = data["faultInfo"]

        message = fault.get("message", "알 수 없는 오류")
        error_code = fault.get("errorCode", "확인 불가")

        return None, (
            "KOBIS API에서 오류를 반환했습니다.\n\n"
            f"오류 코드: {error_code}\n\n"
            f"오류 내용: {message}\n\n"
            "Streamlit Secrets의 `KOBIS_KEY`가 올바른지, "
            "KOBIS Open API 인증키가 정상적으로 발급되어 있는지 확인해 주세요."
        )

    # boxOfficeResult가 없는 경우도 처리
    if "boxOfficeResult" not in data:
        return None, (
            "응답에서 박스오피스 정보를 찾지 못했습니다.\n\n"
            "KOBIS API 응답 형식이 변경되었거나 일시적인 서버 문제가 있을 수 있습니다."
        )

    # 영화 목록 가져오기
    movie_list = data["boxOfficeResult"].get(
        "dailyBoxOfficeList",
        []
    )

    # 목록 자체가 비어 있는 경우
    if not movie_list:
        return None, (
            "해당 날짜의 박스오피스 영화 목록이 비어 있습니다.\n\n"
            "조회 날짜의 집계가 완료되었는지 또는 "
            "KOBIS 서버에 데이터가 정상적으로 등록되어 있는지 확인해 주세요."
        )

    return movie_list, None


# ---------------------------------------------------------
# 4. API 호출
# ---------------------------------------------------------
movie_list, error_message = get_boxoffice_data(target_date)

# 오류가 발생한 경우 안내 메시지를 보여 주고 실행 중단
if error_message:
    st.error(error_message)
    st.stop()


# ---------------------------------------------------------
# 5. 필요한 데이터만 DataFrame으로 정리
# ---------------------------------------------------------
df = pd.DataFrame(movie_list)

# KOBIS API의 숫자는 문자열로 오기 때문에
# 실제 숫자로 변환한다.
numeric_columns = [
    "rank",
    "rankInten",
    "audiCnt",
    "audiAcc",
    "scrnCnt",
    "showCnt"
]

for column in numeric_columns:
    if column in df.columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        ).fillna(0).astype(int)


# 순위 순서대로 정렬
df = df.sort_values("rank").reset_index(drop=True)


# ---------------------------------------------------------
# 6. 1위 영화 크게 보여 주기
# ---------------------------------------------------------
first_movie = df.iloc[0]

st.divider()

st.subheader(
    f"🏆 박스오피스 1위 · {first_movie['movieNm']}"
)

# 세 개의 지표 카드를 가로로 배치
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="어제 관객수",
        value=f"{first_movie['audiCnt']:,}명"
    )

with col2:
    st.metric(
        label="누적 관객수",
        value=f"{first_movie['audiAcc']:,}명"
    )

with col3:
    st.metric(
        label="스크린수",
        value=f"{first_movie['scrnCnt']:,}개"
    )


# ---------------------------------------------------------
# 7. 관객수 상위 5편 막대그래프
# ---------------------------------------------------------
st.divider()

st.subheader("📊 관객수 TOP 5")

# 일일 관객수가 많은 순서로 정렬한 뒤 5편만 선택
top5 = (
    df.sort_values(
        "audiCnt",
        ascending=False
    )
    .head(5)
    .copy()
)

# st.bar_chart에서 영화명을 세로축 이름으로 사용하기 위해
# 영화명을 인덱스로 설정한다.
chart_data = (
    top5[
        ["movieNm", "audiCnt"]
    ]
    .set_index("movieNm")
)

st.bar_chart(
    chart_data,
    y="audiCnt",
    x_label="영화",
    y_label="관객수"
)


# ---------------------------------------------------------
# 8. 전체 박스오피스 표
# ---------------------------------------------------------
st.divider()

st.subheader("🍿 일별 박스오피스 순위")

# 사용자에게 보여 줄 열만 선택한다.
table_df = df[
    [
        "rank",
        "movieNm",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt"
    ]
].copy()

# 한글 열 이름으로 변경
table_df.columns = [
    "순위",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수"
]

# 숫자가 보기 쉽도록 천 단위 쉼표 적용
table_df["관객수"] = table_df["관객수"].map(
    lambda x: f"{x:,}"
)

table_df["누적관객"] = table_df["누적관객"].map(
    lambda x: f"{x:,}"
)

table_df["스크린수"] = table_df["스크린수"].map(
    lambda x: f"{x:,}"
)

# 표 출력
st.dataframe(
    table_df,
    hide_index=True,
    use_container_width=True
)


# ---------------------------------------------------------
# 9. 출처 표시
# ---------------------------------------------------------
st.caption(
    "데이터 출처: 영화진흥위원회 KOBIS 영화관입장권통합전산망 Open API"
)
