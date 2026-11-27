# clock_skew.ps1 —— 测 PC 与 Duo 的时钟偏差（对应待交清单 B-7）
#
# 用法：
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\clock_skew.ps1
#   powershell ... -File .\clock_skew.ps1 -Boards 192.168.5.9 -Samples 10
#
# 原理（NTP 式四点法，只取两端）：
#   t1 = PC 发请求前
#   t2 = 板子返回的时间（date +%s.%N）
#   t4 = PC 收到后
#   offset = t2 - (t1 + t4)/2      ← 板子比 PC 快多少秒（正数=板子快）
#   rtt    = t4 - t1
#   精度约 ±rtt/2；取 rtt 最小的那次作为结果，抗网络抖动。
#
# 输出可直接填进 A/14 的 [B-7]：两组数（校时前 / 校时后）+ 校时方法一行。
#
# 前置：能 ssh root@<IP> 免交互或手动输密码（每台板每次都要输，脚本会提示）。

param(
    [string[]]$Boards  = @("192.168.5.9", "192.168.5.10"),
    [int]$Samples      = 10,
    [string]$User      = "root"
)

function NowEpoch {
    # 返回 UTC epoch 秒（双精度）
    return [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() / 1000.0
}

foreach ($ip in $Boards) {
    Write-Host ""
    Write-Host "===== $ip =====" -ForegroundColor Cyan

    $best = $null
    for ($i = 1; $i -le $Samples; $i++) {
        $t1 = NowEpoch
        # 只取板子返回的数字，去掉 ssh 的提示与警告
        $out = & ssh -o StrictHostKeyChecking=accept-new "$User@$ip" "date +%s.%N" 2>$null
        $t4 = NowEpoch

        $line = ($out | Where-Object { $_ -match '^\d+\.\d+$' } | Select-Object -Last 1)
        if (-not $line) {
            Write-Host ("  第 {0} 次：没拿到时间（检查 ssh 能否登录）" -f $i) -ForegroundColor Yellow
            continue
        }

        $t2   = [double]$line
        $rtt  = $t4 - $t1
        $skew = $t2 - ($t1 + $t4) / 2.0

        Write-Host ("  第 {0,2} 次：rtt = {1,6:N1} ms   skew = {2,8:N1} ms" -f $i, ($rtt*1000), ($skew*1000))

        if ($null -eq $best -or $rtt -lt $best.rtt) {
            $best = [pscustomobject]@{ rtt = $rtt; skew = $skew; ip = $ip }
        }
    }

    if ($best) {
        Write-Host ("  ---> 取 rtt 最小的一次：rtt = {0:N1} ms，skew = {1:N1} ms（误差约 ±{2:N1} ms）" -f `
            ($best.rtt*1000), ($best.skew*1000), ($best.rtt*1000/2)) -ForegroundColor Green
        Write-Host ("  填表写法：{0}  skew_s = {1:N3} s（rtt {2:N1} ms）" -f $ip, $best.skew, ($best.rtt*1000))
    }
}

Write-Host ""
Write-Host "说明：" -ForegroundColor Cyan
Write-Host "  · skew > 0 表示板子比 PC 快；skew < 0 表示板子慢。"
Write-Host "  · 两板都跑 ntpd（公网校时），正常情况下 skew 应在几十毫秒内。"
Write-Host "  · '校时前/后各一组'：先在两块板上 systemctl restart ntpd 或 reboot 后立刻测一组（后），"
Write-Host "    隔 10 分钟再测一组（稳）；若两组差异大，说明 NTP 未收敛，报告里要写清。"
Write-Host "  · 本脚本只测 PC↔板；契约 3 第 9 条要求的 ts_rx/ts_node 偏差由看板侧记录，口径一致即可。"

