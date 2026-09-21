from collections import Counter


# ---------------------------------------------------------
# 이름의 자음·모음을 분석해서 영화 추천하기
# ---------------------------------------------------------

# 한글 초성 목록
CHO = [
    "ㄱ", "ㄲ", "ㄴ", "ㄷ", "ㄸ", "ㄹ", "ㅁ", "ㅂ", "ㅃ",
    "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅉ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"
]

# 한글 중성 목록
JUNG = [
    "ㅏ", "ㅐ", "ㅑ", "ㅒ", "ㅓ", "ㅔ", "ㅕ", "ㅖ",
    "ㅗ", "ㅘ", "ㅙ", "ㅚ", "ㅛ", "ㅜ", "ㅝ", "ㅞ",
    "ㅟ", "ㅠ", "ㅡ", "ㅢ", "ㅣ"
]

# 한글 종성 목록
JONG = [
    "", "ㄱ", "ㄲ", "ㄳ", "ㄴ", "ㄵ", "ㄶ", "ㄷ", "ㄹ",
    "ㄺ", "ㄻ", "ㄼ", "ㄽ", "ㄾ", "ㄿ", "ㅀ", "ㅁ",
    "ㅂ", "ㅄ", "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅊ", "ㅋ",
    "ㅌ", "ㅍ", "ㅎ"
]


def split_hangul(text):
    """
    한글을 초성, 중성, 종성으로 나눈다.

    예:
    '민지'
    → 자음: ㅁ, ㄴ, ㅈ
    → 모음: ㅣ, ㅣ
    """

    consonants = []
    vowels = []

    for char in text:

        # 한글 음절인지 확인
        if "가" <= char <= "힣":

            # '가'를 기준으로 몇 번째 한글 글자인지 계산
            code = ord(char) - ord("가")

            # 초성, 중성, 종성 번호 계산
            cho_index = code // 588
            jung_index = (code % 588) // 28
            jong_index = code % 28

            # 초성은 자음
            consonants.append(CHO[cho_index])

            # 중성은 모음
            vowels.append(JUNG[jung_index])

            # 받침이 있는 경우 자음에 추가
            if JONG[jong_index]:
                consonants.append(JONG[jong_index])

    return consonants, vowels


def overlap_score(list1, list2):
    """
    두 목록에서 같은 글자가 얼마나 많이 등장하는지 계산한다.

    예:
    이름 자음: ㅇ, ㅈ, ㅇ
    영화 자음: ㅇ, ㅈ, ㅅ

    → ㅇ과 ㅈ이 겹치므로 점수가 올라간다.
    """

    count1 = Counter(list1)
    count2 = Counter(list2)

    score = 0

    for letter in count1:
        score += min(
            count1[letter],
            count2.get(letter, 0)
        )

    return score


def movie_match_score(name, movie_title):
    """
    이름과 영화 제목의 자음·모음 유사도를 계산한다.
    """

    name_consonants, name_vowels = split_hangul(name)
    movie_consonants, movie_vowels = split_hangul(movie_title)

    # 자음이 같은 정도
    consonant_score = overlap_score(
        name_consonants,
        movie_consonants
    )

    # 모음이 같은 정도
    vowel_score = overlap_score(
        name_vowels,
        movie_vowels
    )

    # 자음은 1.2점, 모음은 1점으로 계산
    score = (
        consonant_score * 1.2
        + vowel_score
    )

    # 이름과 영화 제목의 글자 수가 비슷하면 약간의 추가 점수
    length_difference = abs(
        len(name) - len(movie_title)
    )

    length_bonus = max(
        0,
        1 - length_difference * 0.15
    )

    score += length_bonus

    return score


# ---------------------------------------------------------
# 화면에 영화 추천 기능 표시
# ---------------------------------------------------------
st.divider()

st.subheader("✨ 내 이름과 어울리는 영화 찾기")

st.write(
    "이름의 자음과 모음을 분석해서 "
    "현재 박스오피스 영화 중 가장 비슷한 제목을 찾아드려요."
)

user_name = st.text_input(
    "이름을 입력하세요",
    placeholder="예: 이주연"
)


# 이름을 입력했을 때만 추천 실행
if user_name:

    # 입력값에서 앞뒤 공백 제거
    user_name = user_name.strip()

    # 한글 분석
    name_consonants, name_vowels = split_hangul(user_name)

    # 한글 이름이 아닌 경우
    if not name_consonants and not name_vowels:

        st.warning(
            "한글 이름을 입력해 주세요."
        )

    else:

        # 각 영화의 이름 궁합 점수 계산
        recommend_df = df.copy()

        recommend_df["이름궁합점수"] = recommend_df["movieNm"].apply(
            lambda movie:
            movie_match_score(
                user_name,
                movie
            )
        )

        # 점수가 높은 영화부터 정렬
        recommend_df = recommend_df.sort_values(
            "이름궁합점수",
            ascending=False
        ).reset_index(drop=True)

        # 가장 잘 어울리는 영화
        best_movie = recommend_df.iloc[0]

        st.success(
            f"🎬 {user_name}님과 가장 어울리는 영화는 "
            f"**{best_movie['movieNm']}** 입니다!"
        )

        # 이름에서 분석한 자음과 모음 보여 주기
        st.write(
            "🔤 이름의 자음:",
            " ".join(name_consonants)
        )

        st.write(
            "🔡 이름의 모음:",
            " ".join(name_vowels)
        )

        # 추천 영화 3편
        st.markdown("#### 🎞️ 이름 궁합 TOP 3")

        top3 = recommend_df.head(3)

        for i, (_, movie) in enumerate(
            top3.iterrows(),
            start=1
        ):

            movie_consonants, movie_vowels = split_hangul(
                movie["movieNm"]
            )

            st.write(
                f"**{i}위. {movie['movieNm']}**  "
                f"｜ 관객수 {movie['audiCnt']:,}명"
            )
