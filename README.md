# finance-miniprogram

微信小程序初始化项目（理财方向）。

当前仓库同时包含：
- 微信小程序前端
- Django 后端（`backend/`）

## 已包含内容

- 基础小程序入口：`app.js` `app.json` `app.wxss`
- 首页：`pages/index/*`
- 项目配置：`project.config.json` `sitemap.json`
- Django 后端：`backend/`
- Git 忽略规则：`.gitignore`

## 本地运行

1. 打开微信开发者工具
2. 导入当前目录
3. `AppID` 可先使用测试号，后续替换 `project.config.json` 中的 `appid`

## Django 后端运行

1. 进入后端目录：`cd backend`
2. 执行迁移：`D:/projects/理财项目设计/.venv/Scripts/python.exe manage.py migrate`
3. 启动服务：`D:/projects/理财项目设计/.venv/Scripts/python.exe manage.py runserver`
4. 健康检查接口：`http://127.0.0.1:8000/api/health/`

## 后续建议

- 增加登录态与用户资产模型
- 接入理财产品列表与收益测算
- 接入云开发或后端 API
