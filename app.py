import streamlit as st
import pandas as pd
import random
import time

# --- 音声再生用の関数（安定版） --- #
def speak_french(text):
    if text:
        safe_text = text.replace("'", "\\'").replace("\n", " ")
        run_id = int(time.time() * 1000)

        js_code = f"""
            <script>
            // 実行ID: {run_id} 
            (function() {{
                var synth = window.speechSynthesis;
                synth.cancel(); // 進行中の音声を止める

                var utter = new SpeechSynthesisUtterance('{safe_text}');
                utter.lang = 'fr-FR';
                utter.rate = 0.9;
                
                // 再生
                synth.speak(utter);
            }})();
            </script>
        """
        st.components.v1.html(js_code, height=0)

# --- 単語の詳細UIを描画する共通関数（モジュール） --- #
def display_word_card(word_row, key_suffix=""):
    col_text, col_btn = st.columns([0.8, 0.2])
    with col_text:
        st.subheader(f"単語: :blue[{word_row['french']}]")
        
    with col_btn:
        st.markdown("<div style='padding-top: 10px;'></div>", unsafe_allow_html=True)
        btn_key = f"audio_{key_suffix}_{word_row.name}"
        if st.button("🔊", key=btn_key, help="発音を聞く", use_container_width=True):
            speak_french(word_row['french'])

    # 1. 日本語（意味）の判定
    if pd.isna(word_row['japanese']):
        st.warning("⚠️ 日本語がまだ登録されていません")
    else:
        word_type = f" ({word_row['type']})" if pd.notna(word_row['type']) else ""
        st.write(f"意味: **{word_row['japanese']}** {word_type}")

    # 2. 説明の判定
    if pd.isna(word_row['explanation']):
        st.info("ℹ️ 説明がまだ登録されていません")
    else:
        st.write(f"説明: {word_row['explanation']}")

    # 3. 例文の判定
    if pd.isna(word_row['example']):
        st.info("ℹ️ 例文がまだ登録されていません")
    else:
        examples = [e.strip() for e in str(word_row['example']).split('|') if e.strip()]
        st.write("例文:")
        for ex in examples:
            st.markdown(f"- *{ex}*")

    st.caption(f"レベル: {word_row['level']} / テーマ: {word_row['theme']}")
    
    if 'image_file' in word_row and pd.notna(word_row['image_file']):
        st.image(f"images/{word_row['image_file']}", width=300)

# --- 初期設定 --- #
st.set_page_config(
    page_title="フランス語単語学習",
    layout="centered",
    initial_sidebar_state="collapsed" # スマホ用にサイドバーを隠す
)

# 1. アプリの開始状態（フラグ）を初期化
if "started" not in st.session_state:
    st.session_state.started = False

# 2. まだスタートしていない場合のみタイトルとスタートボタンを表示
if not st.session_state.started:
    st.title("🇫🇷 フランス語単語アプリ")
    st.write("たのしくフランス語の単語をおぼえよう！")

    if st.button("🚀 はじめる", use_container_width=True):
        st.session_state.started = True
        st.rerun()
    
    st.stop()

# --- 1. データの読み込み（スプレッドシート連携版） ---
if "sheet_url" in st.secrets:
    SHEET_URL = st.secrets["sheet_url"]
else:
    st.error("エラー: secrets.toml に 'sheet_url' が設定されていません。")
    st.stop()

@st.cache_data(ttl=600)
def load_data():
    df = pd.read_csv(SHEET_URL)
    df = df[df['japanese'].notna()]
    df['dummy_list'] = df['dummies'].apply(lambda x: [i.strip() for i in str(x).split(',')])
    return df

df = load_data()

# --- ここから下は「スタート後」に表示したいメインの処理 ---
nb_words = len(df)
st.caption(f"🇫🇷 フランス語単語アプリ: {nb_words} 語")
st.markdown("""
    <style>
    [data-testid="stHorizontalBlock"] {
        gap: 0px !important;
    }
    
    [data-testid="column"] {
        padding: 0px 2px !important;
        min-width: 0px !important;
        flex-grow: 1 !important;
    }
    
    .stButton > button {
        width: 100%;
        border-radius: 25px;
        background-color: #f0f8ff;
        border: 2px solid #87ceeb;
        font-weight: bold;
        transition: all 0.2s ease;
    }
    .stButton > button:hover {
        transform: scale(1.02);
        background-color: #e0f7fa;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. セッション状態の初期化 ---
if 'history' not in st.session_state:
    st.session_state.history = []
if 'current_word_idx' not in st.session_state:
    st.session_state.current_word_idx = None
if 'old_filtered_len' not in st.session_state:
    st.session_state.old_filtered_len = 0
if 'wrong_list' not in st.session_state:
    st.session_state.wrong_list = []
if 'answered' not in st.session_state:
    st.session_state.answered = False
if 'choices' not in st.session_state:
    st.session_state.choices = []
if 'mode' not in st.session_state:
    st.session_state.mode = "学習"
if 'selected_search_idx' not in st.session_state:
    st.session_state.selected_search_idx = None

# --- 3. サイドメニュー ---
st.sidebar.header("メニュー")
mode = st.sidebar.radio("モード切替", ["学習", "演習", "復習（間違えた問題）", "単語検索"])

if mode != st.session_state.mode:
    st.session_state.mode = mode
    st.session_state.current_word_idx = None
    st.session_state.choices = []
    st.session_state.answered = False
    st.session_state.selected_search_idx = None

st.sidebar.markdown("---")
st.sidebar.header("絞り込み")

selected_levels = st.sidebar.multiselect("レベル選択", options=list(df['level'].unique()))

all_themes = set()
for t in df['theme'].dropna():
    for item in str(t).split(','):
        all_themes.add(item.strip())

selected_themes = st.sidebar.multiselect("テーマ選択", options=sorted(list(all_themes)))

st.sidebar.write(f"間違えた単語数: {len(st.session_state.wrong_list)}")

st.sidebar.markdown("---")

with st.sidebar.expander("⚖️ 免責事項"):
    st.caption("""
    本アプリに掲載されている情報の正確性については万全を期していますが、利用者が本アプリの情報を用いて行う一切の行為について、開発者は何ら責任を負うものではありません。
    学習の補助ツールとしてご活用ください。
    """)

with st.sidebar.expander("💡 フィードバック"):
    st.caption("不備の報告や、機能の改善案、追加してほしい単語のリクエストなどをお待ちしています！")
    st.link_button(
        "報告フォームを開く", 
        "https://docs.google.com/forms/d/e/1FAIpQLSfqiuWtqEr5AUaGwCaZWoK0Zm0bFQfSL2eg68k6hkknQdLZ4Q/viewform?usp=publish-editor",
        use_container_width=True
    )

with st.sidebar.expander("🚀 アップデート情報"):
    st.caption("""
    **v1.0.0 (2026/06/11)**
    - アプリ初期版リリース
    """)

# --- 4. データのフィルタリング ---
if mode == "復習（間違えた問題）":
    filtered_df = df.iloc[st.session_state.wrong_list]
else:
    filtered_df = df.copy()
    
    if selected_levels:
        filtered_df = filtered_df[filtered_df['level'].isin(selected_levels)]
    
    if selected_themes:
        def check_theme(row_theme):
            if pd.isna(row_theme):
                return False
            themes_in_row = [t.strip() for t in str(row_theme).split(',')]
            return any(theme in themes_in_row for theme in selected_themes)

        filtered_df = filtered_df[filtered_df['theme'].apply(check_theme)]

# リストの長さが変わった場合のリセット処理
if len(filtered_df) != st.session_state.old_filtered_len:
    st.session_state.current_word_idx = None
    st.session_state.old_filtered_len = len(filtered_df)

if st.session_state.current_word_idx is not None:
    if st.session_state.current_word_idx >= len(filtered_df):
        st.session_state.current_word_idx = None

# --- 5. 画面表示 ---

if mode == "単語検索":
    # 検索詳細画面が開かれている場合
    if st.session_state.selected_search_idx is not None:
        if st.button("⬅ 検索結果に戻る"):
            st.session_state.selected_search_idx = None
            st.rerun()
            
        st.markdown("---")
        selected_row = df.loc[st.session_state.selected_search_idx]
        display_word_card(selected_row, key_suffix="search_detail")
        
    # 通常の検索入力・一覧画面の場合
    else:
        search_query = st.text_input("フランス語を入力してください（例: pomme）", "", key="search_input_box").strip().lower()

        if search_query:
            search_filtered_df = df[df['french'].str.lower().str.contains(search_query, na=False)]
            if search_filtered_df.empty:
                st.warning(f"「{search_query}」を含む単語は見つかりませんでした。")
            else:
                st.success(f"🔍 {len(search_filtered_df)}件の単語が見つかりました！")
                
                for index, word_row in search_filtered_df.iterrows():
                    with st.container():
                        col1, col2 = st.columns([0.7, 0.3])
                        with col1:
                            st.markdown(f"**{word_row['french']}**")
                            st.write(f"意味: {word_row['japanese']}")
                        with col2:
                            if st.button("詳細を見る ➔", key=f"go_detail_{index}", use_container_width=True):
                                st.session_state.selected_search_idx = index
                                st.rerun()
                        st.markdown("---")
        else:
            st.info("検索したいフランス語を入力してください。")

    # 単語検索モードの場合はここで処理を終了する
    st.stop()

# フィルタリング後の条件チェック（学習・演習・復習モード用）
if filtered_df.empty:
    if mode == "復習（間違えた問題）":
        st.info("間違えた問題はありません！")
    else:
        st.warning("条件に合う単語がありません。")
    st.stop()

# --- 6. クイズ・学習の状態管理 ---
if st.session_state.current_word_idx is None:
    st.session_state.current_word_idx = random.randint(0, len(filtered_df) - 1)
    st.session_state.answered = False
    st.session_state.choices = []

word_row = filtered_df.iloc[st.session_state.current_word_idx]
original_idx = filtered_df.index[st.session_state.current_word_idx]

# --- モード別の表示（学習 / 演習 / 復習） ---
if mode == "学習":
    display_word_card(word_row, key_suffix="learning")
    
    c1, c2 = st.columns(2)
    with c1:
        if st.session_state.history:
            if st.button("前の単語へ", use_container_width=True):
                st.session_state.current_word_idx = st.session_state.history.pop()
                st.rerun()
        else:
            st.button("前の単語へ", use_container_width=True, disabled=True)
    
    with c2:
        if st.button("次の単語へ", use_container_width=True):
            st.session_state.history.append(st.session_state.current_word_idx)
            st.session_state.current_word_idx = None
            st.rerun()

else: # 演習または復習モード
    st.subheader(f"この単語の意味は？ : :blue[{word_row['french']}]")

    if not st.session_state.choices:
        correct_list = [w.strip() for w in str(word_row['japanese']).split(',')]
        correct = random.choice(correct_list)
        dummies = random.sample(word_row['dummy_list'], min(3, len(word_row['dummy_list'])))
        choices = dummies + [correct]
        random.shuffle(choices)
        st.session_state.choices = choices

    for choice in st.session_state.choices:
        if st.button(choice, use_container_width=True, disabled=st.session_state.answered):
            st.session_state.answered = True
            correct_list = [w.strip() for w in str(word_row['japanese']).split(',')]
            
            if choice in correct_list:
                st.session_state.last_result = "correct"
                if original_idx in st.session_state.wrong_list:
                    st.session_state.wrong_list.remove(original_idx)
            else:
                st.session_state.last_result = "wrong"
                if original_idx not in st.session_state.wrong_list:
                    st.session_state.wrong_list.append(original_idx)
            
            st.rerun()

    if st.session_state.answered:
        if st.session_state.last_result == "correct":
            st.success("正解！")
        else:
            st.error(f"不正解。正解は「{word_row['japanese']}」")

    col1, col2 = st.columns(2)

    with col1:
        if st.session_state.history:
            if st.button("前の問題へ", use_container_width=True):
                st.session_state.current_word_idx = st.session_state.history.pop()
                st.session_state.choices = []
                st.session_state.answered = False
                st.rerun()
        else:
            st.button("前の問題へ", use_container_width=True, disabled=True)

    with col2:    
        if st.session_state.answered:
            if st.button("次の問題へ", use_container_width=True):
                st.session_state.history.append(st.session_state.current_word_idx)
                st.session_state.current_word_idx = None
                st.session_state.choices = []
                st.session_state.answered = False
                st.rerun()
        else:
            st.button("次の問題へ", use_container_width=True, disabled=True)
