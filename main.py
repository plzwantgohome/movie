import streamlit as st
import pandas as pd
import requests

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from collections import Counter


# =========================================================
# 1. 페이지 기본 설정
# =========================================================
st.set_page_config(
    page_title="박스오피스 대시보드",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 날짜별 박스오피스")
st.caption("KOBIS 영화관입장권통합전산망의 일별 박스오피스 데이터를 확인할 수 있습니다.")


# =========================================================
# 2. KOBIS 인증키 가져오기
# =========================================================
# 인증키는 코드에 직접 적지 않고
# Streamlit Cloud의 Secrets에 저장한다.
try:
    KOBIS_KEY = st.secrets["KOBIS_KEY"]

except Exception:
    st.error(
        "KOBIS 인증키를 찾을 수 없습니다. "
        "Streamlit Cloud의 Secrets에서 KOBIS_KEY를 확인해 주세요."
    )
    st.stop()


# =========================================================
# 3. 한국 시간 기준 어제 날짜 계산
# =========================================================
# Streamlit Cloud 서버의 시간이 한국 시간이 아닐 수 있으므로
# Asia/Seoul 시간대를 직접 지정한다.
korea_now = datetime.now(ZoneInfo("Asia/Seoul"))

# 오늘 데이터는 아직 집계 전이므로
# 가장 늦게 선택할 수 있는 날짜는 어제이다.
yesterday = (korea_now - timedelta(days=1)).date()


# =========================================================
# 4. 날짜 선택
# =========================================================
selected_date = st.date_input(
    "📅 박스오피스 날짜를 선택하세요",
    value=yesterday,
    max_value=yesterday,
    format="YYYY-MM-DD"
)

# KOBIS API는 날짜를 YYYYMMDD 형식으로 받는다.
target_dt = selected_date.strftime("%Y%m%d")

st.caption(
    f"조회 기준일: {selected_date.strftime('%Y-%m-%d')}"
)


# =========================================================
# 5. KOBIS API 요청
# =========================================================
url = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
    "boxoffice/searchDailyBoxOfficeList.json"
)

try:
    response = requests.get(
        url,
        params={
            "key": KOBIS_KEY,
            "targetDt": target_dt
        },
        timeout=10
    )

except requests.exceptions.Timeout:
    st.error(
        "KOBIS 서버의 응답 시간이 너무 오래 걸립니다. "
        "잠시 후 다시 시도해 주세요."
    )
    st.stop()

except requests.exceptions.RequestException:
    st.error(
        "KOBIS 서버에 연결하지 못했습니다. "
        "인터넷 연결 상태나 KOBIS 서버 상태를 확인해 주세요."
    )
    st.stop()


# HTTP 요청 자체가 실패한 경우
if response.status_code != 200:
    st.error(
        f"요청이 실패했습니다. "
        f"(상태코드: {response.status_code})"
    )
    st.stop()


# =========================================================
# 6. JSON 데이터로 변환
# =========================================================
try:
    data = response.json()

except ValueError:
    st.error(
        "KOBIS 서버에서 정상적인 데이터를 받지 못했습니다. "
        "잠시 후 다시 시도해 주세요."
    )
    st.stop()


# =========================================================
# 7. KOBIS 오류 확인
# =========================================================
# KOBIS는 인증키가 틀려도 상태코드 200을 보내고
# faultInfo를 반환할 수 있다.
if "faultInfo" in data:

    fault = data["faultInfo"]

    error_message = fault.get(
        "message",
        "알 수 없는 오류"
    )

    st.error(
        "KOBIS API에서 오류가 발생했습니다.\n\n"
        f"오류 내용: {error_message}\n\n"
        "Streamlit Secrets의 KOBIS_KEY가 올바른지 확인해 주세요."
    )

    st.stop()


# =========================================================
# 8. 영화 목록 꺼내기
# =========================================================
box_list = (
    data
    .get("boxOfficeResult", {})
    .get("dailyBoxOfficeList", [])
)


# 영화 목록이 비어 있는 경우
if not box_list:
    st.warning("그날은 아직 집계 전입니다.")
    st.stop()


# =========================================================
# 9. DataFrame으로 변환
# =========================================================
df = pd.DataFrame(box_list)


# KOBIS에서는 숫자도 문자열 형태로 보내므로
# 실제 숫자로 변환한다.
numeric_columns = [
    "rank",
    "rankInten",
    "audiCnt",
    "audiAcc",
    "scrnCnt",
    "showCnt"
]

for col in numeric_columns:

    df[col] = pd.to_numeric(
        df[col],
        errors="coerce"
    ).fillna(0).astype(int)


# 순위 순서대로 정렬
df = (
    df
    .sort_values("rank")
    .reset_index(drop=True)
)


# =========================================================
# 10. 박스오피스 1위 표시
# =========================================================
st.divider()

top = df.iloc[0]

st.subheader(
    f"🏆 {selected_date.strftime('%Y-%m-%d')} 박스오피스 1위"
)

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
    "누적 관객수",
    f"{top['audiAcc']:,}명"
)


# =========================================================
# 11. 순위 변동 표시 만들기
# =========================================================
def make_rank_change(value):

    # 양수 = 전날보다 순위 상승
    if value > 0:
        return f"↑ {value}"

    # 음수 = 전날보다 순위 하락
    elif value < 0:
        return f"↓ {abs(value)}"

    # 0 = 변화 없음
    else:
        return "―"


df["순위변동"] = df["rankInten"].apply(
    make_rank_change
)


# =========================================================
# 12. 누적 관객 100만 명 초과 영화에 트로피 붙이기
# =========================================================
def add_trophy(row):

    if row["audiAcc"] > 1_000_000:
        return f"{row['movieNm']} 🏆"

    return row["movieNm"]


df["표시영화명"] = df.apply(
    add_trophy,
    axis=1
)


# =========================================================
# 13. 박스오피스 표 만들기
# =========================================================
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


table.columns = [
    "순위",
    "순위 변동",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수"
]


# =========================================================
# 14. 상승은 빨강, 하락은 파랑으로 표시
# =========================================================
def color_rank_change(value):

    if isinstance(value, str):

        if value.startswith("↑"):
            return "color: #e53935; font-weight: bold;"

        if value.startswith("↓"):
            return "color: #1e88e5; font-weight: bold;"

    return ""


styled_table = table.style.map(
    color_rank_change,
    subset=["순위 변동"]
)


# =========================================================
# 15. 박스오피스 표 출력
# =========================================================
st.subheader("📋 박스오피스 TOP 10")

st.dataframe(
    styled_table,
    hide_index=True,
    use_container_width=True
)


# =========================================================
# 16. 관객수 상위 5편 그래프
# =========================================================
st.subheader("📈 관객수 상위 5편")

top5 = (
    df
    .sort_values(
        "audiCnt",
        ascending=False
    )
    .head(5)
    [["movieNm", "audiCnt"]]
)

st.bar_chart(
    top5.set_index("movieNm")["audiCnt"],
    x_label="영화",
    y_label="관객수"
)


# =========================================================
# 17. 한글 자음과 모음 분석 준비
# =========================================================

# 초성
CHO = [
    "ㄱ", "ㄲ", "ㄴ", "ㄷ", "ㄸ", "ㄹ", "ㅁ",
    "ㅂ", "ㅃ", "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅉ",
    "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"
]

# 중성
JUNG = [
    "ㅏ", "ㅐ", "ㅑ", "ㅒ", "ㅓ", "ㅔ", "ㅕ",
    "ㅖ", "ㅗ", "ㅘ", "ㅙ", "ㅚ", "ㅛ", "ㅜ",
    "ㅝ", "ㅞ", "ㅟ", "ㅠ", "ㅡ", "ㅢ", "ㅣ"
]

# 종성
# 첫 번째 빈 문자열은 받침이 없는 경우이다.
JONG = [
    "",
    "ㄱ", "ㄲ", "ㄳ", "ㄴ", "ㄵ", "ㄶ",
    "ㄷ", "ㄹ", "ㄺ", "ㄻ", "ㄼ", "ㄽ",
    "ㄾ", "ㄿ", "ㅀ", "ㅁ", "ㅂ", "ㅄ",
    "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅊ", "ㅋ",
    "ㅌ", "ㅍ", "ㅎ"
]


# =========================================================
# 18. 한글을 자음과 모음으로 나누는 함수
# =========================================================
def split_hangul(text):

    consonants = []
    vowels = []

    for char in text:

        # 완성형 한글만 분석한다.
        if "가" <= char <= "힣":

            # '가'를 기준으로 현재 글자의 번호 계산
            code = ord(char) - ord("가")

            # 초성 번호
            cho_index = code // 588

            # 중성 번호
            jung_index = (code % 588) // 28

            # 종성 번호
            jong_index = code % 28

            # 초성은 자음에 추가
            consonants.append(
                CHO[cho_index]
            )

            # 중성은 모음에 추가
            vowels.append(
                JUNG[jung_index]
            )

            # 받침이 있다면 자음에 추가
            if JONG[jong_index] != "":
                consonants.append(
                    JONG[jong_index]
                )

    return consonants, vowels


# =========================================================
# 19. 같은 자모의 개수를 세는 함수
# =========================================================
def overlap_count(list1, list2):

    count1 = Counter(list1)
    count2 = Counter(list2)

    overlap = 0

    for letter in count1:

        overlap += min(
            count1[letter],
            count2.get(letter, 0)
        )

    return overlap


# =========================================================
# 20. 이름과 영화 제목의 자모 유사도 계산
# =========================================================
def calculate_match_score(name, movie_title):

    # 이름 분석
    name_consonants, name_vowels = split_hangul(
        name
    )

    # 영화 제목 분석
    movie_consonants, movie_vowels = split_hangul(
        movie_title
    )

    # 자음이 얼마나 겹치는지 계산
    consonant_overlap = overlap_count(
        name_consonants,
        movie_consonants
    )

    # 모음이 얼마나 겹치는지 계산
    vowel_overlap = overlap_count(
        name_vowels,
        movie_vowels
    )


    # -----------------------------------------------------
    # 이름에 들어 있는 자음 중 몇 %가 영화 제목에 있는지 계산
    # -----------------------------------------------------
    if len(name_consonants) > 0:

        consonant_similarity = (
            consonant_overlap
            / len(name_consonants)
        )

    else:
        consonant_similarity = 0


    # -----------------------------------------------------
    # 이름에 들어 있는 모음 중 몇 %가 영화 제목에 있는지 계산
    # -----------------------------------------------------
    if len(name_vowels) > 0:

        vowel_similarity = (
            vowel_overlap
            / len(name_vowels)
        )

    else:
        vowel_similarity = 0


    # 자음 55%, 모음 45% 비율로 계산
    score = (
        consonant_similarity * 0.55
        + vowel_similarity * 0.45
    )


    # 0~100 사이의 숫자로 변환
    return round(score * 100, 1)


# =========================================================
# 21. 이름으로 영화 추천
# =========================================================
st.divider()

st.subheader("✨ 내 이름과 어울리는 영화")

st.write(
    "이름의 자음과 모음을 분석해 "
    "선택한 날짜의 박스오피스 영화 중 "
    "이름과 가장 비슷한 영화를 찾아드려요."
)


user_name = st.text_input(
    "이름을 입력하세요",
    placeholder="예: 홍길동"
)


# 이름이 입력되었을 때만 실행
if user_name:

    # 앞뒤 공백 제거
    user_name = user_name.strip()

    # 입력된 이름 분석
    name_consonants, name_vowels = split_hangul(
        user_name
    )


    # 한글이 하나도 없는 경우
    if not name_consonants and not name_vowels:

        st.warning(
            "한글 이름을 입력해 주세요."
        )


    else:

        # 기존 박스오피스 데이터를 복사한다.
        recommend_df = df.copy()


        # 각 영화마다 이름과의 유사도 계산
        recommend_df["이름유사도"] = (
            recommend_df["movieNm"].apply(
                lambda movie:
                calculate_match_score(
                    user_name,
                    movie
                )
            )
        )


        # 점수가 높은 순서대로 정렬
        recommend_df = (
            recommend_df
            .sort_values(
                "이름유사도",
                ascending=False
            )
            .reset_index(drop=True)
        )


        # 가장 잘 어울리는 영화
        best_movie = recommend_df.iloc[0]


        # -------------------------------------------------
        # 결과 크게 표시
        # -------------------------------------------------
        st.success(
            f"🎬 {user_name}님과 가장 잘 어울리는 영화는 "
            f"**{best_movie['movieNm']}** 입니다!"
        )


        # -------------------------------------------------
        # 이름 분석 결과
        # -------------------------------------------------
        col1, col2 = st.columns(2)

        col1.metric(
            "이름의 자음",
            " ".join(name_consonants)
        )

        col2.metric(
            "이름의 모음",
            " ".join(name_vowels)
        )


        # -------------------------------------------------
        # 가장 잘 맞는 영화 3편 출력
        # -------------------------------------------------
        st.markdown("#### 🎞️ 이름 궁합 TOP 3")

        top3 = recommend_df.head(3)


        for i, (_, movie) in enumerate(
            top3.iterrows(),
            start=1
        ):

            st.write(
                f"**{i}위. {movie['movieNm']}**  "
                f"｜ 자모 유사도 {movie['이름유사도']:.1f}%  "
                f"｜ 당일 관객수 {movie['audiCnt']:,}명"
            )


        st.caption(
            "※ 이름 추천은 실제 영화 취향을 분석하는 기능이 아니라, "
            "한글 이름과 영화 제목에 포함된 자음과 모음의 유사성을 "
            "비교한 재미용 추천입니다."
        )


# =========================================================
# 22. 데이터 출처
# =========================================================
st.divider()

st.caption(
    "데이터 출처: 영화진흥위원회 KOBIS "
    "영화관입장권통합전산망 Open API"
)
