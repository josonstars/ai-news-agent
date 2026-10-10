#!/usr/bin/env bash
set -e
echo "==> 创建 conda 环境 ai-news"
conda env create -f environment.yml || conda env update -f environment.yml
echo "==> 激活环境并安装 pip 依赖"
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate ai-news
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
echo "==> 初始化数据库"
python migrate.py
echo "==> 复制环境变量模板"
[ -f .env ] || cp .env.example .env
echo "✅ 完成。请编辑 .env 填入 DEEPSEEK_API_KEY"
echo "   然后运行： conda activate ai-news && python app.py"