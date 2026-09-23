import streamlit as st
from openai import OpenAI

# 페이지 기본 설정
st.set_page_config(page_title="AI 정보 선생님", page_icon="🤖")
st.title("🤖 AI 정보 선생님")

# 비밀 금고(secrets)에서 API 키를 꺼내 접속 준비
client = OpenAI(
    api_key=st.secrets["GEMINI_API_KEY"],
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)

# ---------------------------------------------------------
# [사이드바] 설정 영역
# ---------------------------------------------------------
st.sidebar.title("⚙️ AI 설정")

# 1. 말투 선택 옵션 정의
TONE_PROMPTS = {
    "기본 (선생님)": "너는 중고등학생에게 설명하는 친절한 정보 선생님이야. 어려운 말은 쉬운 말로 바꿔 주고, 반드시 순수 한국어로만 답해.",
    "돌쇠": "너는 조선 시대의 충성스러운 머쇠/돌쇠야. '마님!', '나으리!' 같은 표현을 사용하고, 구수한 하인의 말투(~했습지요, ~입습지요)로 친절하고 유쾌하게 설명해줘.",
    "집사": "너는 매우 정중하고 예의 바른 고급 저택의 전문 집사야. 사용자에게 최고의 격식을 갖추어 아주 정중하고 친근하게(~하옵니다, ~하시겠습니까) 설명해줘.",
    "AI 비서": "너는 유능하고 명쾌하며 똑부러지는 최첨단 AI 비서야. 객관적이고 간결하면서도 정확하게 핵심 위주로 깔끔히 답변해줘."
}

# 사이드바: 말투 선택
selected_tone = st.sidebar.selectbox(
    "🎭 말투 고르기",
    list(TONE_PROMPTS.keys()),
    index=0
)

# 기본 프롬프트 설정 (선택된 말투에 따라 변경)
default_prompt = TONE_PROMPTS[selected_tone]

# 사이드바: 성격 문장 직접 수정 (텍스트 영역)
custom_prompt = st.sidebar.text_area(
    "✏️ AI 성격/지시사항 직접 수정",
    value=default_prompt,
    height=120,
    help="선택한 말투의 지시사항이 입력되며, 원하는 대로 직접 수정할 수도 있습니다."
)

# 사이드바: 대화 지우기 버튼
if st.sidebar.button("🗑️ 대화 지우기", use_container_width=True):
    st.session_state.messages = []
    st.rerun()

# ---------------------------------------------------------
# [대화 세션] 관리 및 업데이트
# ---------------------------------------------------------
# 대화 기록이 없으면 리스트 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

# 기존 대화에서 system 메시지 제외한 유저/AI 대화 내용만 남기기
user_ai_messages = [msg for msg in st.session_state.messages if msg["role"] != "system"]

# 최신 선택/수정된 system 프롬프트를 맨 앞에 적용
st.session_state.messages = [{"role": "system", "content": custom_prompt}] + user_ai_messages

# ---------------------------------------------------------
# [화면] 지금까지의 대화 출력 (성격 문장은 숨김)
# ---------------------------------------------------------
for msg in st.session_state.messages:
    if msg["role"] != "system":
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# ---------------------------------------------------------
# [채팅 입력 및 AI 응답]
# ---------------------------------------------------------
user_input = st.chat_input("궁금한 것을 물어보세요!")

if user_input:
    # 보낸 말을 기록에 넣고 화면에도 그리기
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # AI 답 받아오기
    with st.chat_message("assistant"):
        try:
            stream = client.chat.completions.create(
                model="gemini-3.5-flash-lite",       # 모델 이름 유지
                messages=st.session_state.messages,  # 최신 system 프롬프트가 포함된 전체 대화
                stream=True,                         # 스트리밍 방식
            )
            answer = st.write_stream(
                chunk.choices[0].delta.content or ""
                for chunk in stream if chunk.choices
            )
            # AI 답도 기록에 저장
            st.session_state.messages.append({"role": "assistant", "content": answer})
        except Exception:
            st.error("응답을 받지 못했습니다. 잠시 후 다시 보내 주세요.")
