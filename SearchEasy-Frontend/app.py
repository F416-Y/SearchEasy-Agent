import streamlit as st
import requests
from datetime import datetime

st.set_page_config(page_title="搜EASY - AI导购", page_icon="🛒", layout="wide", initial_sidebar_state="collapsed")

# ========== 初始化 session_state ==========
if "page" not in st.session_state:
    st.session_state.page = "home"
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_products" not in st.session_state:
    st.session_state.last_products = None

# ========== CSS 样式（包含 Emoji 字体回退） ==========
st.markdown("""
    <style>
    /* 隐藏默认元素 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    [data-testid="stSidebar"] {display: none;}
    
    /* 全局字体 + Emoji 回退 */
    * {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', sans-serif;
    }
    .stApp {
        background: linear-gradient(145deg, #f6f9fc 0%, #eef2f9 100%);
    }
    .main .block-container {
        background: rgba(255,255,255,0.96);
        border-radius: 32px;
        padding: 1.5rem 2rem;
        margin: 1rem auto;
        box-shadow: 0 20px 35px -12px rgba(0,0,0,0.1);
        backdrop-filter: blur(2px);
    }
    
    /* 首页样式 */
    .hero {
        text-align: center;
        padding: 2rem 1rem;
        background: linear-gradient(120deg, #3498db10, #2c3e5005);
        border-radius: 48px;
        margin-bottom: 2rem;
    }
    .hero h1 {
        font-size: 4.2rem;
        font-weight: 800;
        background: linear-gradient(135deg, #1e3c72, #2a5298);
        -webkit-background-clip: text;
        background-clip: text;
        color: transparent;
        margin-bottom: 0.5rem;
        letter-spacing: -0.02em;
    }
    .hero p {
        font-size: 1.2rem;
        color: #4a627a;
        max-width: 600px;
        margin: 0 auto;
    }
    .feature-grid {
        display: flex;
        gap: 1.5rem;
        justify-content: center;
        flex-wrap: wrap;
        margin: 2.5rem 0;
    }
    .feature-item {
        background: white;
        border-radius: 28px;
        padding: 1.5rem;
        flex: 1;
        min-width: 180px;
        text-align: center;
        box-shadow: 0 8px 20px rgba(0,0,0,0.02);
        border: 1px solid rgba(52,152,219,0.1);
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .feature-item:hover {
        transform: translateY(-6px);
        box-shadow: 0 20px 30px -12px rgba(52,152,219,0.2);
        border-color: #3498db30;
    }
    .feature-icon {
        font-size: 3rem;
        margin-bottom: 0.5rem;
    }
    
    /* 聊天界面样式 */
    .chat-title {
        text-align: center;
        padding-bottom: 0.75rem;
        border-bottom: 2px solid #eef2f6;
        margin-bottom: 1.5rem;
    }
    .chat-title h2 {
        font-size: 1.8rem;
        font-weight: 600;
        background: linear-gradient(90deg, #2c3e50, #3498db);
        -webkit-background-clip: text;
        background-clip: text;
        color: transparent;
    }
    .user-bubble {
        background: linear-gradient(135deg, #eef5ff, #e0edfc);
        border-radius: 24px 24px 8px 24px;
        padding: 12px 18px;
        max-width: 75%;
        float: right;
        clear: both;
        margin-bottom: 12px;
        color: #1e2f3e;
        box-shadow: 0 2px 5px rgba(0,0,0,0.02);
    }
    .ai-bubble {
        background: white;
        border: 1px solid #e2edf7;
        border-radius: 24px 24px 24px 8px;
        padding: 14px 20px;
        max-width: 85%;
        float: left;
        clear: both;
        margin-bottom: 16px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.03);
    }
    .timestamp {
        font-size: 0.7rem;
        color: #8ba0bc;
        margin-top: 6px;
        letter-spacing: 0.3px;
    }
    .product-row {
        display: flex;
        gap: 16px;
        margin-top: 16px;
        flex-wrap: wrap;
    }
    .product-card {
        background: #fafdff;
        border-radius: 20px;
        padding: 8px;
        text-align: center;
        flex: 1;
        min-width: 100px;
        transition: transform 0.2s;
        border: 1px solid #eef2f8;
    }
    .product-card:hover {
        transform: translateY(-3px);
        border-color: #3498db40;
    }
    .product-card img {
        width: 100%;
        border-radius: 16px;
        aspect-ratio: 1 / 1;
        object-fit: cover;
        background: #f1f5f9;
    }
    .similarity-badge {
        background: #3498db;
        color: white;
        border-radius: 40px;
        padding: 4px 12px;
        font-size: 0.7rem;
        font-weight: 500;
        display: inline-block;
        margin-top: 8px;
    }
    .upload-area {
        position: sticky;
        bottom: 0;
        background: rgba(255,255,255,0.98);
        backdrop-filter: blur(12px);
        padding: 1rem 0.5rem 0.5rem;
        border-radius: 28px 28px 0 0;
        border-top: 1px solid #eef2f6;
        margin-top: 1.5rem;
    }
    [data-testid="stFileUploader"] {
        background: #f8fafd;
        border: 1.5px dashed #3498db;
        border-radius: 28px;
        padding: 0.75rem;
    }
    .stButton > button {
        background: linear-gradient(90deg, #3498db, #2980b9);
        color: white;
        border: none;
        border-radius: 40px;
        padding: 0.4rem 1.6rem;
        font-weight: 500;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        transform: scale(1.02);
        box-shadow: 0 8px 18px #3498db40;
    }
    @media (max-width: 768px) {
        .main .block-container { padding: 1rem; }
        .hero h1 { font-size: 2.5rem; }
        .user-bubble, .ai-bubble { max-width: 90%; }
        .product-card { min-width: 80px; }
    }
    </style>
""", unsafe_allow_html=True)

# ========== API 函数 ==========
def call_recommend_api(image_file):
    url = "https://yunyunwaifu-flora-ai-shop-agent.hf.space/api/agent/recommend"
    files = {"file": image_file}
    with st.spinner("🔍 正在识别商品..."):
        try:
            resp = requests.post(url, files=files, timeout=15)
            if resp.status_code == 200:
                return resp.json()
            else:
                st.error(f"接口错误 {resp.status_code}")
                return None
        except Exception as e:
            st.error(f"网络错误: {e}")
            return None

def call_feedback_api(feedback_type, last_products):
    url = "https://yunyunwaifu-flora-ai-shop-agent.hf.space/api/agent/feedback"
    payload = {"feedback": feedback_type, "last_products": last_products}
    with st.spinner("✨ 根据反馈优化推荐..."):
        try:
            resp = requests.post(url, json=payload, timeout=15)
            if resp.status_code == 200:
                return resp.json()
            else:
                st.error(f"反馈接口错误 {resp.status_code}")
                return None
        except Exception as e:
            st.error(f"反馈失败: {e}")
            return None

# ========== 首页 ==========
def show_home():
    st.markdown("""
        <div class="hero">
            <h1>🛒 搜EASY</h1>
            <p>拍照即搜 · AI 智能推荐 · 对话式导购</p>
        </div>
        <div class="feature-grid">
            <div class="feature-item">
                <div class="feature-icon">📸</div>
                <h3>拍照上传</h3>
                <p>随手一拍，AI 自动识别商品特征</p>
            </div>
            <div class="feature-item">
                <div class="feature-icon">⚡</div>
                <h3>毫秒检索</h3>
                <p>向量数据库精准匹配相似好物</p>
            </div>
            <div class="feature-item">
                <div class="feature-icon">💬</div>
                <h3>智能对话</h3>
                <p>点赞点踩，越用越懂你的喜好</p>
            </div>
        </div>
    """, unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        if st.button("✨ 开始体验 ✨", use_container_width=True):
            st.session_state.page = "chat"
            st.rerun()
    st.markdown("---")
    st.caption("搜EASY · AI 全栈挑战赛作品 | 基于多模态检索 + 大语言模型")

# ========== 聊天界面 ==========
def show_chat():
    # 标题（使用 Emoji 字体回退 + 通用 Emoji）
    st.markdown("""
        <div class="chat-title">
            <h2><span style="font-family: 'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', sans-serif;">🛍️</span> 搜EASY · AI导购</h2>
        </div>
    """, unsafe_allow_html=True)
    
    # 渲染所有消息
    for idx, msg in enumerate(st.session_state.messages):
        if msg["role"] == "user":
            st.markdown(f"""
                <div style="display: flex; justify-content: flex-end;">
                    <div class="user-bubble">
                        {msg['content']}
                        <div class="timestamp">{msg['timestamp']}</div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
        else:
            products = msg.get("products", [])
            # 修复 HTML 显示问题：使用字符串拼接，不换行
            product_html = ""
            if products:
                product_html = '<div class="product-row">'
                for p in products[:3]:
                    sim = p.get("similarity_score", 0)
                    img_path = p.get("image_path", "")
                    img_url = img_path if img_path.startswith("http") else "https://placehold.co/300x300/f1f5f9/8ba0bc?text=🛍️"
                    product_html += '<div class="product-card">'
                    product_html += f'<img src="{img_url}">'
                    product_html += f'<div class="similarity-badge">相似度 {sim*100:.1f}%</div>'
                    product_html += '</div>'
                product_html += '</div>'
            
            ai_html = f"""
                <div style="display: flex; justify-content: flex-start;">
                    <div class="ai-bubble">
                        🤖 {msg['content']}
                        {product_html}
                        <div class="timestamp">{msg['timestamp']}</div>
                    </div>
                </div>
            """
            st.markdown(ai_html, unsafe_allow_html=True)

            # 最后一条 AI 消息显示反馈按钮
            if idx == len(st.session_state.messages) - 1 and products:
                with st.container():
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("👍 满意", key=f"like_{idx}"):
                            new_data = call_feedback_api("like", products)
                            if new_data:
                                # 追加用户反馈消息
                                st.session_state.messages.append({
                                    "role": "user",
                                    "content": "👍 满意",
                                    "timestamp": datetime.now().strftime("%H:%M")
                                })
                                # 追加 AI 新推荐
                                st.session_state.messages.append({
                                    "role": "assistant",
                                    "content": new_data.get("recommendation_note", ""),
                                    "products": new_data.get("products", []),
                                    "timestamp": datetime.now().strftime("%H:%M")
                                })
                                st.rerun()
                    with col2:
                        if st.button("👎 不满意，换一批", key=f"dislike_{idx}"):
                            new_data = call_feedback_api("dislike", products)
                            if new_data:
                                st.session_state.messages.append({
                                    "role": "user",
                                    "content": "👎 不满意，换一批",
                                    "timestamp": datetime.now().strftime("%H:%M")
                                })
                                st.session_state.messages.append({
                                    "role": "assistant",
                                    "content": new_data.get("recommendation_note", ""),
                                    "products": new_data.get("products", []),
                                    "timestamp": datetime.now().strftime("%H:%M")
                                })
                                st.rerun()
    
    # 底部上传区
    with st.container():
        st.markdown('<div class="upload-area">', unsafe_allow_html=True)
        uploaded = st.file_uploader("点击上传商品图片", type=["jpg","jpeg","png"], label_visibility="collapsed")
        if uploaded:
            st.image(uploaded, width=80)
            data = call_recommend_api(uploaded)
            if data:
                st.session_state.messages.append({
                    "role": "user",
                    "content": "用户上传了一张图片",
                    "timestamp": datetime.now().strftime("%H:%M")
                })
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": data.get("recommendation_note", ""),
                    "products": data.get("products", []),
                    "timestamp": datetime.now().strftime("%H:%M")
                })
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        st.caption("💡 上传后 AI 会为你推荐相似商品，点击 👍/👎 可以优化推荐结果。")

# ========== 路由 ==========
if st.session_state.page == "home":
    show_home()
else:
    show_chat()