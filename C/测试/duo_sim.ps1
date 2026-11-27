# duo_sim.ps1 —— Duo 侧最小替身
#
# 用途：B 的 duo_bridge.py 还没到位时，先用它验证"UNO ↔ Duo"这条链路和刷卡开锁。
#       它只做三件事，正好覆盖 D5 验收：
#         1. 打印 UNO 发来的每一帧（证明 @E 能被对端收到）
#         2. 每 10 s 发一次 @Q 心跳（证明心跳能被响应）
#         3. 收到 @R,<uid> 后回 @L,3000（证明刷卡→开锁闭环通）
#
# 用法（需先关掉 Arduino 串口监视器，否则端口被占用）：
#     powershell -NoProfile -ExecutionPolicy Bypass -File duo_sim.ps1 -Port COM7
#
# 退出：Ctrl + C

param(
  [string]$Port = "COM7",
  [int]$Baud = 115200,
  [int]$LockMs = 3000
)

$ErrorActionPreference = "Stop"

$sp = New-Object System.IO.Ports.SerialPort $Port, $Baud,
      [System.IO.Ports.Parity]::None, 8, [System.IO.Ports.StopBits]::One
$sp.NewLine = "`n"
$sp.ReadTimeout = 300
$sp.Open()

Write-Host "[duo_sim] $Port @ $Baud 已打开，Ctrl+C 退出" -ForegroundColor Cyan
Write-Host "[duo_sim] 等待 UNO 的 @E ...`n" -ForegroundColor DarkGray

$lastHb = Get-Date
try {
  while ($true) {
    try {
      $line = $sp.ReadLine().Trim()
      if ($line) {
        Write-Host ("[{0:HH:mm:ss}] {1}" -f (Get-Date), $line)

        # 刷卡 → 模拟白名单通过，回开锁
        if ($line -like "@R,*") {
          Start-Sleep -Milliseconds 300
          $sp.WriteLine("@L,$LockMs")
          Write-Host "[duo_sim] -> @L,$LockMs  (白名单通过)" -ForegroundColor Green
        }
      }
    } catch [System.TimeoutException] {
      # 没数据是正常的，继续循环
    }

    # 心跳：每 10 s 问一次，UNO 应立即回 @E
    if (((Get-Date) - $lastHb).TotalSeconds -ge 10) {
      $lastHb = Get-Date
      $sp.WriteLine("@Q")
      Write-Host "[duo_sim] -> @Q  (心跳)" -ForegroundColor DarkCyan
    }
  }
} finally {
  $sp.Close()
  Write-Host "`n[duo_sim] 端口已释放" -ForegroundColor Yellow
}
