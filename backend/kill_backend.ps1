# 强杀后端服务脚本

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  正在查找并停止后端服务..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 获取所有 Python 进程
$pythonProcesses = Get-Process python -ErrorAction SilentlyContinue

if ($pythonProcesses) {
    Write-Host "找到 $($pythonProcesses.Count) 个 Python 进程：" -ForegroundColor Yellow
    Write-Host ""
    
    # 显示进程信息
    $pythonProcesses | Format-Table Id, ProcessName, StartTime -AutoSize
    Write-Host ""
    
    # 强杀所有 Python 进程
    Write-Host "正在强杀所有 Python 进程..." -ForegroundColor Red
    $pythonProcesses | Stop-Process -Force
    Write-Host "✅ 已成功停止所有 Python 进程" -ForegroundColor Green
} else {
    Write-Host "✅ 没有找到正在运行的 Python 进程" -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  操作完成！" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "按任意键退出..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
