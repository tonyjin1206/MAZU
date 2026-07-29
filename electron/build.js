#!/usr/bin/env node
/**
 * LTMP 跨平台打包脚本
 * 构建前端 → 打包后端 → Electron 打包 → 输出安装包
 *
 * 用法:
 *   node build.js            # 自动检测当前平台打包
 *   node build.js mac        # macOS 打包
 *   node build.js win        # Windows 打包
 *   node build.js all        # 全平台打包
 */

const { execSync } = require('child_process')
const path = require('path')
const fs = require('fs')

const ROOT = path.resolve(__dirname, '..')
const BACKEND = path.join(ROOT, 'backend')
const ELECTRON = __dirname
const IS_WIN = process.platform === 'win32'

function run(cmd, cwd) {
  console.log(`  $ ${cmd}`)
  execSync(cmd, { cwd, stdio: 'inherit', shell: true })
}

function banner(msg) {
  console.log(`\n${'='.repeat(50)}`)
  console.log(`  ${msg}`)
  console.log(`${'='.repeat(50)}`)
}

async function build(targets) {
  // Step 1: Build frontend
  banner('[1/4] 构建前端')
  run('npm run build', path.join(ROOT, 'frontend'))

  // Step 2: Copy frontend dist to backend
  banner('[2/4] 复制前端产物')
  const frontendDist = path.join(BACKEND, 'frontend_dist')
  if (fs.existsSync(frontendDist)) {
    fs.rmSync(frontendDist, { recursive: true })
  }
  fs.mkdirSync(frontendDist, { recursive: true })
  const viteDist = path.join(ROOT, 'frontend', 'dist')
  if (fs.existsSync(viteDist)) {
    fs.cpSync(viteDist, frontendDist, { recursive: true })
    console.log('  ✅ 前端产物已复制')
  }

  // Step 3: PyInstaller backend
  banner('[3/4] 打包后端')
  const venvPython = IS_WIN
    ? path.join(BACKEND, 'venv', 'Scripts', 'python.exe')
    : path.join(BACKEND, 'venv', 'bin', 'python')

  if (!fs.existsSync(venvPython)) {
    console.log('  ⚠️  未找到虚拟环境 Python，请先运行 python launcher.py install')
    process.exit(1)
  }

  // Install PyInstaller if needed
  run(`${venvPython} -m pip install pyinstaller -q`, BACKEND)

  // Clean old build
  const runDist = path.join(BACKEND, 'run_dist')
  if (fs.existsSync(runDist)) {
    fs.rmSync(runDist, { recursive: true })
  }

  // Platform-specific PyInstaller args
  const separator = IS_WIN ? ';' : ':'
  const pyInstallerCmd = [
    venvPython, '-m', 'PyInstaller', '--onefile',
    '--name', 'server',
    '--distpath', 'run_dist',
    `--add-data", "frontend_dist${separator}frontend_dist`,
    `--add-data", "data${separator}../data_template`,
    '--hidden-import', 'uvicorn.logging',
    '--hidden-import', 'uvicorn.loops.auto',
    '--hidden-import', 'uvicorn.protocols.http.auto',
    '--hidden-import', 'uvicorn.lifespan.on',
    'run.py',
  ].join(' ')

  run(pyInstallerCmd, BACKEND)
  console.log('  ✅ 后端打包完成')

  // Step 4: Electron builder
  banner('[4/4] 打包 Electron 应用')

  // Install Electron deps
  run('npm install', ELECTRON)

  // Build
  const targetFlag = targets.map(t => `--${t}`).join(' ')
  run(`npx electron-builder ${targetFlag}`, ELECTRON)

  banner('✅ 打包完成！')
  console.log(`  安装包在: ${path.join(ELECTRON, 'dist')}`)
}

// CLI
const targetArg = process.argv[2] || process.platform
const targetMap = {
  mac: ['mac'],
  win: ['win'],
  linux: ['linux'],
  all: ['mac', 'win', 'linux'],
  darwin: ['mac'],
  win32: ['win'],
}

const targets = targetMap[targetArg]
if (!targets) {
  console.log(`用法: node build.js [mac|win|linux|all]`)
  process.exit(1)
}

build(targets).catch(err => {
  console.error('打包失败:', err.message)
  process.exit(1)
})
