搜-easy (SearchEasy) - 前端界面

多模态电商智能导购 Agent 前端子模块。

## 负责同学

C 同学（前端开发）

## 核心职责

- 设计并实现用户交互界面（首页 + 对话式导购界面）
- 调用后端 Agent 推荐接口（/recommend）和反馈接口（/feedback）
- 展示 AI 推荐语、相似商品卡片（含图片和相似度分数）
- 绘制相似度对比柱状图、相似度分布直方图
- 实现满意/不满意反馈功能，动态追加对话记录
- 响应式布局，适配手机/平板/电脑
- 集成 B 同学提供的公网图片 URL，正确显示商品图

## 技术栈

- **框架**：Streamlit (Python)
- **HTTP 客户端**：requests
- **数据可视化**：Plotly Express
- **样式**：自定义 CSS（毛玻璃效果、渐变背景、动画）

## 本地运行

```bash
# 克隆仓库
git clone https://github.com/magic-bear/SearchEasy-Frontend.git
cd SearchEasy-Frontend

# 安装依赖
pip install streamlit requests plotly pillow

# 启动应用
streamlit run app.py
应用将在 http://localhost:8501 打开。

接口依赖
推荐接口：POST https://yunyunwaifu-flora-ai-shop-agent.hf.space/api/agent/recommend

反馈接口：POST https://yunyunwaifu-flora-ai-shop-agent.hf.space/api/agent/feedback

图片托管：https://whisper1234-ai-shop-agent-api.hf.space/images/（由 B 同学提供）

项目结构
text
SearchEasy-Frontend/
├── app.py               # 主程序
├── README.md
└── .gitignore

团队成员
A 同学：Agent 智能体（推荐 + 反馈大模型）

B 同学：以图搜图后端（向量检索 + 图片托管）

C 同学：前端界面（本项目）
