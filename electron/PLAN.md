# ERP Electron 封装方案

## 目标
将MTS打包成 macOS .dmg 安装包，双击即用。

## 架构
```
Electron App
├── main.js          # 主进程：启动Python后端 + 打开窗口
├── preload.js       # 预加载脚本
├── renderer/        # 前端构建产物（Vite build）
└── backend/         # Python后端（PyInstaller打包）
    ├── server       # 可执行文件
    └── data/erp.db  # 数据库
```

## 步骤
1. 修改 FastAPI 支持静态文件服务（生产模式下直接serve前端）
2. 构建 Vue 前端 → dist/
3. 创建 Electron 主进程（启动后端、打开窗口）
4. PyInstaller 打包 Python 后端
5. electron-builder 打包成 .dmg

## 数据库
用户数据保存在 ~/Library/Application Support/ERP/erp.db
首次启动自动复制空数据库模板
