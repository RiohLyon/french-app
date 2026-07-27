import streamlit as st
import pandas as pd
import random

# --- 音声再生用の関数（安定版） --- #
def speak_french(text):
    if text:
        safe_text = text.replace("'", "\\'").replace("\n", " ")
        import time
        # 現在の時刻からユニークなIDを作成
        run_id = int(time.time() * 1000)

        # JavaScriptのコードの中に run_id をコメントとして埋め込む！
        # これにより、毎回「全く新しいHTMLが生成された」とStreamlitが勘違いして、毎回実行してくれます。
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
        # key引数は削除し、毎回異なる文字列になった js_code だけを渡します
        st.components.v1.html(js_code, height=0)

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

    # 「はじめる」ボタンが押されたらフラグをTrueにして画面を再描画
    if st.button("🚀 はじめる", use_container_width=True):
        st.session_state.started = True
        st.rerun()  # 画面を更新してタイトルを消す
    
    # ここで処理を止めることで、最初の画面ではタイトルとボタンだけを表示
    st.stop()

# --- ここから下は「スタート後」に表示したいメインの処理 ---

# メイン画面には小さめの見出し（st.captionやst.subheader）を出しておくと親切です
st.caption("🇫🇷 フランス語単語アプリ")
st.markdown("""
    <style>
    /* 横並びブロックの隙間（gap）をゼロにする */
    [data-testid="stHorizontalBlock"] {
        gap: 0px !important;
    }
    
    /* カラム自体の左右のパディング（内側の余白）を削る */
    [data-testid="column"] {
        padding: 0px 2px !important; /* 2pxだけ残すとボタン同士がくっつきすぎず綺麗です */
        min-width: 0px !important;
        flex-grow: 1 !important;
    }
    
    /* 例：ボタンを角丸にして、ホバー時に少し浮き上がるようにする */
    .stButton > button {
        width: 100%;
        border-radius: 25px; /* 角を大きく丸める */
        background-color: #f0f8ff; /* 優しい青色 */
        border: 2px solid #87ceeb;
        font-weight: bold;
        transition: all 0.2s ease;
    }
    .stButton > button:hover {
        transform: scale(1.02); /* マウスを乗せると少し大きくなる */
        background-color: #e0f7fa;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 1. データの読み込み（スプレッドシート連携版） ---
if "sheet_url" in st.secrets:
    SHEET_URL = st.secrets["sheet_url"]
else:
    st.error("エラー: secrets.toml に 'sheet_url' が設定されていません。")
    st.stop()

@st.cache_data(ttl=600) # 10分間キャッシュを保持
def load_data():
    # URLからCSVとして読み込み
    df = pd.read_csv(SHEET_URL)
    
    # 演習・復習モードでのバグを防ぐため、日本語訳(japanese)が空の行を最初から除外する
    df = df[df['japanese'].notna()]
    
    # ダミーリストの作成
    df['dummy_list'] = df['dummies'].apply(lambda x: [i.strip() for i in str(x).split(',')])
    return df

df = load_data()

# --- 2. セッション状態の初期化 ---
# まだ変数が作られていなければ、初期値をセットする
if 'history' not in st.session_state:
    st.session_state.history = [] # 解いた問題の番号を順番に溜めていくリスト
if 'current_word_idx' not in st.session_state:
    st.session_state.current_word_idx = None
if 'old_filtered_len' not in st.session_state:
    st.session_state.old_filtered_len = 0
if 'wrong_list' not in st.session_state:
    st.session_state.wrong_list = [] # 間違えた問題のインデックスを保存
if 'answered' not in st.session_state:
    st.session_state.answered = False
if 'choices' not in st.session_state:
    st.session_state.choices = []
if 'mode' not in st.session_state:
    st.session_state.mode = "学習"

# --- 3. サイドメニュー ---
st.sidebar.header("メニュー")
mode = st.sidebar.radio("モード切替", ["学習", "演習", "復習（間違えた問題）", "単語検索"])

# モードが変わったら問題をリセットする処理
if 'mode' not in st.session_state:
    st.session_state.mode = mode

if mode != st.session_state.mode:
    st.session_state.mode = mode
    st.session_state.current_word_idx = None
    st.session_state.choices = []
    st.session_state.answered = False

st.sidebar.markdown("---")
st.sidebar.header("絞り込み")


# 絞り込み形式の作成
selected_levels = st.sidebar.multiselect("レベル選択", options=list(df['level'].unique()))

# サイドバーのテーマ選択肢をバラバラにする
all_themes = set()
for t in df['theme'].dropna():
    for item in str(t).split(','):
        all_themes.add(item.strip())

selected_themes = st.sidebar.multiselect("テーマ選択", options=sorted(list(all_themes)))

# デバッグ用：間違えたリストの中身を表示
st.sidebar.write(f"間違えた単語数: {len(st.session_state.wrong_list)}")

# --- サイドバー：フィードバック機能と免責事項とアップデート情報 ---
st.sidebar.markdown("---")

# 1. 免責事項（クリックすると開く）
with st.sidebar.expander("⚖️ 免責事項"):
    # st.caption を使うと、注釈用の少し小さくて上品な文字になります
    st.caption("""
    本アプリに掲載されている情報の正確性については万全を期していますが、利用者が本アプリの情報を用いて行う一切の行為について、開発者は何ら責任を負うものではありません。
    学習の補助ツールとしてご活用ください。
    """)

# 2.フィードバック機能
with st.sidebar.expander("💡 フィードバック"):
    st.caption("不備の報告や、機能の改善案、追加してほしい単語のリクエストなどをお待ちしています！")
    # エクスパンダーの中にリンクボタンを配置
    # ※withの中なので「st.sidebar.」ではなく「st.link_button」と書くだけで中に入ります
    st.link_button(
        "報告フォームを開く", 
        "https://docs.google.com/forms/d/e/1FAIpQLSfqiuWtqEr5AUaGwCaZWoK0Zm0bFQfSL2eg68k6hkknQdLZ4Q/viewform?usp=publish-editor",
        use_container_width=True
    )

# 3. アップデート情報（クリックすると開く）
with st.sidebar.expander("🚀 アップデート情報"):
    st.caption("""
    **v1.0.0 (2026/06/11)**
    - アプリ初期版リリース
    """)

# --- ここで「mode」を使った条件分岐を行う ---
if mode == "復習（間違えた問題）":
    filtered_df = df.iloc[st.session_state.wrong_list]
else:
    filtered_df = df.copy()
    
    # レベルでの絞り込み
    if selected_levels:
        filtered_df = filtered_df[filtered_df['level'].isin(selected_levels)]
    
    # テーマでの絞り込み（複数テーマ対応版）
    if selected_themes:
        # 各行の theme 列をカンマで分割してリストにし、選択されたテーマが含まれるかチェックする
        def check_theme(row_theme):
            if pd.isna(row_theme):
                return False
            # 「健康, 生活」を ['健康', '生活'] に分解
            themes_in_row = [t.strip() for t in str(row_theme).split(',')]
            # 選択されたテーマのどれか一つでも含まれていれば True
            return any(theme in themes_in_row for theme in selected_themes)

        # 条件に合う行だけを残す
        filtered_df = filtered_df[filtered_df['theme'].apply(check_theme)]

search_query = ""
if mode == "単語検索":
    search_query = st.text_input("フランス語を入力してください（例: pomme）", "").strip().lower()

# --- データのフィルタリング部分を更新 ---
if mode == "単語検索":
    if search_query:
        # 変更点： '==' ではなく '.str.contains()' を使って「部分一致」にします
        # na=False は、空欄のデータが混ざっていてもエラーを出さないためのおまじないです
        filtered_df = df[df['french'].str.lower().str.contains(search_query, na=False)]
    else:
        st.info("検索したいフランス語を入力してください。")
        st.stop()

# ここで「もし空っぽだったら」の処理を入れると安全です
if filtered_df.empty:
    if mode == "復習（間違えた問題）":
        st.info("間違えた問題はありません！")
    else:
        st.warning("条件に合う単語がありません。")
    st.stop()

# --- データのフィルタリングの後に入れる修正 ---

# 以前の選択を保存しておく変数がなければ作成
if 'old_filtered_len' not in st.session_state:
    st.session_state.old_filtered_len = len(filtered_df)

# 【重要】もし現在のリストの長さが変わったら、選んでいたインデックスをリセットする
if len(filtered_df) != st.session_state.old_filtered_len:
    st.session_state.current_word_idx = None
    st.session_state.old_filtered_len = len(filtered_df)

# 安全策：もし今の番号がリストの長さを超えていたらリセット
if st.session_state.current_word_idx is not None:
    if st.session_state.current_word_idx >= len(filtered_df):
        st.session_state.current_word_idx = None

# 演習モードまたは復習モードの場合、日本語訳(japanese)が空の行を最初から除外する
if mode in ["演習", "復習（間違えた問題）"]:
    # .notna() は「値が入っている（空じゃない）」行だけを抽出するメソッドです
    filtered_df = filtered_df[filtered_df['japanese'].notna()]

# --- 4. クイズの状態管理 ---
if 'current_word_idx' not in st.session_state or st.session_state.current_word_idx is None:
    # filtered_dfのインデックスを直接使うのではなく、現在の行の位置をランダムに選ぶ
    st.session_state.current_word_idx = random.randint(0, len(filtered_df) - 1)
    st.session_state.answered = False
    st.session_state.choices = []

# 現在の問題データ（filtered_dfの中のn番目の行を取得）
word_row = filtered_df.iloc[st.session_state.current_word_idx]
# 元のdfにおけるインデックス（間違えたリスト用）
original_idx = filtered_df.index[st.session_state.current_word_idx]

# --- 5. 画面表示 ---

if mode == "単語検索":
    # --- 単語検索モードの画面 ---
    if filtered_df.empty:
        st.warning(f"「{search_query}」を含む単語は見つかりませんでした。")
    else:
        st.success(f"🔍 {len(filtered_df)}件の単語が見つかりました！")
        
        # 見つかった単語を for ループで全て表示する
        for index, word_row in filtered_df.iterrows():
            col_text, col_btn = st.columns([0.8, 0.2])
            with col_text:
                st.subheader(f"単語: :blue[{word_row['french']}]")
            with col_btn:
                st.markdown("<div style='padding-top: 10px;'></div>", unsafe_allow_html=True)
                # 複数ボタンが並ぶため、個別の名前(key)をつける必要があります
                if st.button("🔊", key=f"search_btn_{index}", help="発音を聞く", use_container_width=True):
                    speak_french(word_row['french'])

            word_type = f" ({word_row['type']})" if pd.notna(word_row['type']) else ""
            st.write(f"意味: **{word_row['japanese']}** {word_type}")
            
            if pd.notna(word_row['explanation']):
                st.write(f"説明: {word_row['explanation']}")
            
            st.markdown("---") # 複数の結果を見やすくするための区切り線

elif mode == "学習":
    # --- 学習モードの画面（基本はそのまま） ---
    if filtered_df.empty:
        st.warning("条件に合う単語がありません。")
    else:
        word_row = filtered_df.iloc[st.session_state.current_word_idx]
        
        col_text, col_btn = st.columns([0.8, 0.2])
        with col_text:
            st.subheader(f"単語: :blue[{word_row['french']}]")
            
        with col_btn:
            st.markdown("<div style='padding-top: 10px;'></div>", unsafe_allow_html=True)
            if st.button("🔊", help="発音を聞く", use_container_width=True):
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
            st.write(f"例文: *{word_row['example']}*")

        st.caption(f"レベル: {word_row['level']} / テーマ: {word_row['theme']}")
        
        if 'image_file' in word_row and pd.notna(word_row['image_file']):
            st.image(f"images/{word_row['image_file']}", width=300)
        
        # 前へ・次へボタンの処理
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

    # --- 1. 選択肢の作成（ここは変更なし） ---
    if not st.session_state.choices:
        correct_list = [w.strip() for w in str(word_row['japanese']).split(',')]
        correct = random.choice(correct_list)
        dummies = random.sample(word_row['dummy_list'], min(3, len(word_row['dummy_list'])))
        choices = dummies + [correct]
        random.shuffle(choices)
        st.session_state.choices = choices

    # --- 2. 4択ボタンの表示 ---
    for choice in st.session_state.choices:
        # すでに回答済みの場合は、全てのボタンをdisabledにする
        if st.button(choice, use_container_width=True, disabled=st.session_state.answered):
            # ボタンが押された瞬間の処理
            st.session_state.answered = True
            correct_list = [w.strip() for w in str(word_row['japanese']).split(',')]
            
            if choice in correct_list:
                st.session_state.last_result = "correct" # 結果を保存
                if original_idx in st.session_state.wrong_list:
                    st.session_state.wrong_list.remove(original_idx)
            else:
                st.session_state.last_result = "wrong" # 結果を保存
                if original_idx not in st.session_state.wrong_list:
                    st.session_state.wrong_list.append(original_idx)
            
            # 【重要】ここで再実行して、全てのボタンをdisabledの状態で描き直す
            st.rerun()

    # --- 3. メッセージの表示（ボタンの外側で出す） ---
    if st.session_state.answered:
        if st.session_state.last_result == "correct":
            st.success("正解！")
        else:
            st.error(f"不正解。正解は「{word_row['japanese']}」")

    # --- 4. 次へ/前へボタン（ここは変更なし） ---
    col1, col2 = st.columns(2)

    with col1:
        # 前の問題ボタン
        # 履歴が空じゃない時だけボタンを押せるようにする
        if st.session_state.history:
            if st.button("前の問題へ", use_container_width=True):
                # 履歴の最後の番号を取り出して現在の番号にセット
                st.session_state.current_word_idx = st.session_state.history.pop()
                st.session_state.choices = [] # 選択肢もリセット
                st.session_state.answered = False
                st.rerun()
        else:
            st.button("前の問題へ", use_container_width=True, disabled=True)

        with col2:    
            if st.session_state.answered:
                if st.button("次の問題へ", use_container_width=True):
                    # 次に行く前に、今の番号を履歴に保存する
                    st.session_state.history.append(st.session_state.current_word_idx)
                    
                    st.session_state.current_word_idx = None # 新しい番号を選ばせる
                    st.session_state.choices = []
                    st.session_state.answered = False
                    st.rerun()
    
    






