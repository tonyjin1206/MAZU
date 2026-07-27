const { app, BrowserWindow, dialog } = require('electron')
const path = require('path')
const { spawn } = require('child_process')
const http = require('http')

let mainWindow = null
let backendProcess = null
const PORT = 18788
const DATA_DIR = path.join(app.getPath('userData'), 'data')
const DB_PATH = path.join(DATA_DIR, 'erp.db')

function startBackend() {
  const isDev = process.env.NODE_ENV === 'development'
  let serverPath
  if (isDev) {
    serverPath = path.join(__dirname, '../../backend/run.py')
  } else {
    serverPath = path.join(process.resourcesPath, 'backend/server')
  }

  const env = { ...process.env, PORT: String(PORT), ERP_DATA_DIR: DATA_DIR }

  if (isDev) {
    backendProcess = spawn('python3', [serverPath], { env, stdio: 'pipe' })
  } else {
    backendProcess = spawn(serverPath, [], { env, stdio: 'pipe', detached: true })
  }

  backendProcess.stderr.on('data', (data) => {
    const msg = data.toString()
    if (msg.includes('Application startup complete') || msg.includes('Uvicorn running')) {
      createWindow()
    }
    console.log('[backend]', msg)
  })

  backendProcess.on('error', (err) => {
    console.error('Backend start failed:', err)
    dialog.showErrorBox('启动失败', '无法启动后端服务，请检查安装是否完整。')
    app.quit()
  })

  backendProcess.on('exit', () => {
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
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1200,
    minHeight: 700,
    title: '外贸ERP系统',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
    titleBarStyle: 'hiddenInset',
    trafficLightPosition: { x: 15, y: 15 },
  })

  mainWindow.loadURL(`http://127.0.0.1:${PORT}`)
  mainWindow.on('closed', () => { mainWindow = null })
}

app.whenReady().then(async () => {
  // 确保数据目录存在
  const fs = require('fs')
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
  if (backendProcess) backendProcess.kill()
  app.quit()
})

app.on('activate', () => {
  if (mainWindow === null) {
    createWindow()
  }
})
