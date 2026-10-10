@echo off
echo ==^> 创建 conda 环境 ai-news
call conda env create -f environment.yml || call conda env update -f environment.yml
echo ==^> 激活环境
call conda activate ai-news
echo ==^> 安装 pip 依赖
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
echo ==^> 初始化数据库
python migrate.py
echo ==^> 复制环境变量模板
if not exist .env copy .env.example .env
echo.
echo ✅ 完成。请编辑 .env 填入 DEEPSEEK_API_KEY
echo    然后运行： python app.py
pause