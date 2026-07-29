const { app, BrowserWindow, dialog } = require('electron')
const path = require('path')
const { spawn } = require('child_process')
const http = require('http')
const fs = require('fs')

let mainWindow = null
let backendProcess = null
const PORT = 18788
const DATA_DIR = path.join(app.getPath('userData'), 'data')
const DB_PATH = path.join(DATA_DIR, 'erp.db')

/** 检测当前平台 */
const IS_WIN = process.platform === 'win32'
/** 获取 Python 可执行文件名 */
function pythonBin() {
  return IS_WIN ? 'python' : 'python3'
}

function startBackend() {
  const isDev = process.env.NODE_ENV === 'development'
  let serverPath

  if (isDev) {
    serverPath = path.join(__dirname, '../../backend/run.py')
  } else {
    // 生产模式：使用 PyInstaller 打包后的可执行文件
    const ext = IS_WIN ? '.exe' : ''
    serverPath = path.join(process.resourcesPath, `backend/server${ext}`)
  }

  const env = { ...process.env, PORT: String(PORT), ERP_DATA_DIR: DATA_DIR }

  if (isDev) {
    backendProcess = spawn(pythonBin(), [serverPath], { env, stdio: 'pipe' })
  } else {
    backendProcess = spawn(serverPath, [], { env, stdio: 'pipe', detached: !IS_WIN })
  }

  backendProcess.stderr.on('data', (data) => {
    const msg = data.toString()
    if (msg.includes('Application startup complete') || msg.includes('Uvicorn running')) {
      createWindow()
    }
    console.log('[backend]', msg)
  })

  backendProcess.stdout.on('data', (data) => {
    const msg = data.toString()
    console.log('[backend]', msg)
  })

  backendProcess.on('error', (err) => {
    console.error('Backend start failed:', err)
    dialog.showErrorBox('启动失败', '无法启动后端服务，请检查安装是否完整。')
    app.quit()
  })

  backendProcess.on('exit', (code) => {
    console.log(`[backend] exited with code ${code}`)
    if (mainWindow) {
      mainWindow.webContents.executeJavaScript(`
        document.body.innerHTML = '<div style="text-align:center;padding:80px;font-size:18px;color:#999;">服务已停止</div>'
      `)
    }
  })
}

function waitForBackend(retries = 30) {
  return new Promise((resolve, reject) => {
    const check = () => {
      http.get(`http://127.0.0.1:${PORT}/api/health`, (res) => {
        resolve()
      }).on('error', () => {
        if (retries <= 0) return reject(new Error('Backend timeout'))
        setTimeout(check, 500)
        retries--
      })
    }
    check()
  })
}

function createWindow() {
  const winOptions = {
    width: 1440,
    height: 900,
    minWidth: 1200,
    minHeight: 700,
    title: 'MTS — Mazu Trade System',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    },
  }

  // 跨平台标题栏样式
  if (!IS_WIN) {
    winOptions.titleBarStyle = 'hiddenInset'
    winOptions.trafficLightPosition = { x: 15, y: 15 }
  }

  mainWindow = new BrowserWindow(winOptions)
  mainWindow.loadURL(`http://127.0.0.1:${PORT}`)
  mainWindow.on('closed', () => { mainWindow = null })
}

app.whenReady().then(async () => {
  // 确保数据目录存在
  if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true })

  startBackend()
  try {
    await waitForBackend()
    createWindow()
  } catch (e) {
    dialog.showErrorBox('启动超时', '后端服务启动超时，请重试。')
    app.quit()
  }
})

app.on('window-all-closed', () => {
  if (backendProcess) {
    if (IS_WIN) {
      backendProcess.kill('SIGTERM')
    } else {
      backendProcess.kill()
    }
  }
  app.quit()
})

app.on('activate', () => {
  if (mainWindow === null) {
    createWindow()
  }
})
