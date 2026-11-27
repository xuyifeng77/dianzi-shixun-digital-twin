# bridge_host_pc.ps1 —— ① 模式的 PC 侧串口宿主（B-8）
#
# 链路（A/05 §1.4 落 ①）：
#   UNO ──USB──> PC(本脚本,COM11) ──HTTP──> 看板 /ingest
#
# 为什么用 PowerShell：这台 PC 上没装 Python（`python --version` 报 9009），
# 而 .NET 自带的 System.IO.Ports 够用，无需安装任何东西。
#
# 用法（参数都可配）：
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\bridge_host_pc.ps1
#   powershell ... -File .\bridge_host_pc.ps1 -Com COM11 -Url http://192.168.5.20:8000/ingest -Node milky-a
#   powershell ... -File .\bridge_host_pc.ps1 -ListCom          # 先看有哪些串口
#
# 帧协议（契约 1，ASCII 行帧，与 Duo 侧实现一致）：
#   收 @E,t,h,smoke,flame,light[,sound[,rst]]   → env
#   收 @A,<lv>,<src>                            → alarm  (args:[lv,src])
#   收 @C,<passes>                              → count
#   收 @D,<open>                                → door
#   收 @R,<UID>                                 → rfid（白名单判定，回 @L,<ms>）
#   每 10 s 发 @Q（心跳），收不到任何行 35 s 判链路死（只打印，不停）

param(
    [string]$Com   = "COM11",
    [int]$Baud     = 115200,
    [string]$Url   = "http://192.168.5.20:8000/ingest",
    [string]$Node  = "milky-a",
    [string]$Cards = "A1B2C3D4",
    [int]$LockMs   = 3000,
    [switch]$ListCom
)

if ($ListCom) {
    [System.IO.Ports.SerialPort]::GetPortNames() | ForEach-Object { $_ }
    exit 0
}

# ---- node 归一（与 duo_bridge_v1_5.py 同规则）----
$canon = @("milky-a","milky-b","milky-c","milky-d")
$alias = @{ "nodea"="milky-a"; "nodeb"="milky-b"; "nodec"="milky-c"; "noded"="milky-d" }
$n = $Node.Trim().ToLower()
if ($canon -contains $n) { $Node = $n }
elseif ($alias.ContainsKey($n)) {
    Write-Host ("[WARN] NODE={0} 是旧别名，归一为 {1}" -f $Node, $alias[$n]) -ForegroundColor Yellow
    $Node = $alias[$n]
} else {
    Write-Host ("NODE='{0}' 不在白名单 {1} 内，退出" -f $Node, ($canon -join "/")) -ForegroundColor Red
    exit 2
}

$cardSet = @{}
foreach ($c in $Cards.Split(",")) { if ($c.Trim()) { $cardSet[$c.Trim().ToUpper()] = $true } }

Write-Host "[cfg] COM=$Com  BAUD=$Baud" -ForegroundColor Cyan
Write-Host "[cfg] URL=$Url" -ForegroundColor Cyan
Write-Host "[cfg] NODE=$Node  CARDS=$($cardSet.Keys -join ',')" -ForegroundColor Cyan

# ---- 打开串口 ----
$sp = New-Object System.IO.Ports.SerialPort $Com, $Baud, "None", 8, "One"
$sp.ReadTimeout = 300
$sp.NewLine = "`n"
try { $sp.Open() } catch {
    Write-Host ("[错误] 打不开 {0}：{1}" -f $Com, $_.Exception.Message) -ForegroundColor Red
    Write-Host "  先跑 -ListCom 看端口名；确认 UNO 已插上、没被别的程序占用（Arduino 串口监视器最常占）"
    exit 1
}
Write-Host "[serial] 已打开 $Com" -ForegroundColor Green
Start-Sleep -Milliseconds 2000          # 等 UNO 复位
$sp.DiscardInBuffer()
$sp.WriteLine("@M,0")
$sp.WriteLine("@Q")

# ---- 工具函数 ----
$logFile = Join-Path $PSScriptRoot ("bridge_pc_{0:yyyyMMdd_HHmmss}.log" -f (Get-Date))
function Log([string]$s) {
    $line = "{0}  {1}" -f (Get-Date -Format "HH:mm:ss.fff"), $s
    Write-Host $line
    Add-Content -Path $logFile -Value $line -Encoding UTF8
}

function PostJson($obj) {
    $body = $obj | ConvertTo-Json -Compress -Depth 4
    try {
        Invoke-RestMethod -Uri $Url -Method Post -Body $body -ContentType "application/json" -TimeoutSec 2 | Out-Null
        return $true
    } catch {
        Log ("[post] " + $_.Exception.Message)
        return $false
    }
}

function ToNum($s, [switch]$Float) {
    if ($null -eq $s) { return $null }
    $t = "$s".Trim()
    if ($t -eq "" -or $t -match '^(?i)(nan|na|null|-|inf|-inf)$') { return $null }
    $d = 0.0
    if (-not [double]::TryParse($t, [ref]$d)) { return $null }
    if ([double]::IsNaN($d) -or [double]::IsInfinity($d)) { return $null }
    if ($Float) { return [math]::Round($d, 1) }
    return [int][math]::Round($d)
}

function Ts { return [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() / 1000.0 }

# ---- 主循环 ----
$lastRx  = Get-Date
$lastHb  = Get-Date
$dead    = $false
$dropped = 0
$failed  = 0

Log ("[start] 监听中，Ctrl+C 结束；日志 {0}" -f $logFile)

try {
    while ($true) {
        $now = Get-Date

        # 心跳：10 s 发一次 @Q（契约 4）
        if (($now - $lastHb).TotalSeconds -ge 10) {
            $lastHb = $now
            if (($now - $lastRx).TotalSeconds -gt 35 -and -not $dead) {
                Log ("[LINK] DEAD  ({0:N0}s 无回执)" -f ($now - $lastRx).TotalSeconds)
                $dead = $true
            }
            try { $sp.WriteLine("@Q") } catch { Log "[send] 写串口失败" }
            PostJson @{ type="heartbeat"; node=$Node; ts=(Ts); link=$(if($dead){"dead"}else{"ok"}); dropped=$dropped; failed=$failed } | Out-Null
        }

        # 读一行
        $raw = $null
        try { $raw = $sp.ReadLine() } catch [System.TimeoutException] { }
        catch { Start-Sleep -Milliseconds 300 }
        if (-not $raw) { continue }
        $raw = $raw.Trim()
        if (-not $raw -or -not $raw.StartsWith("@")) { continue }

        $lastRx = Get-Date
        $dead = $false
        Log "[rx] $raw"

        $f = $raw.Substring(1).Split(",")
        $tag = $f[0]

        switch ($tag) {
            "E" {
                if ($f.Count -ge 6) {
                    $ev = [ordered]@{ type="env"; node=$Node; ts=(Ts)
                        t=(ToNum $f[1] -Float); h=(ToNum $f[2] -Float)
                        smoke=(ToNum $f[3]); flame=(ToNum $f[4]); light=(ToNum $f[5]) }
                    if ($f.Count -ge 7) { $ev["sound"] = ToNum $f[6] }
                    if ($f.Count -ge 8) { $ev["rst"]   = ToNum $f[7] }
                    if (-not (PostJson $ev)) { $failed++ }
                }
            }
            "A" {
                $lv = 0; [int]::TryParse($f[1], [ref]$lv) | Out-Null
                if ($lv -lt 0 -or $lv -gt 2) { $lv = 0 }
                $src = "$($f[2])".Trim().ToUpper()
                if (@("NONE","SMOKE","FLAME","TEMP") -notcontains $src) { $src = "NONE" }
                if (-not (PostJson ([ordered]@{ type="alarm"; node=$Node; ts=(Ts); args=@($lv,$src) }))) { $failed++ }
            }
            "C" {
                $v = ToNum $f[1]
                if ($null -ne $v) { if (-not (PostJson ([ordered]@{ type="count"; node=$Node; ts=(Ts); passes=$v }))) { $failed++ } }
            }
            "D" {
                $v = ToNum $f[1]
                if (-not (PostJson ([ordered]@{ type="door"; node=$Node; ts=(Ts); open=$v }))) { $failed++ }
            }
            "R" {
                $uid = "$($f[1])".Trim().ToUpper()
                $ok  = $cardSet.ContainsKey($uid)
                Log ("[RFID] {0} {1}" -f $uid, $(if($ok){"ALLOW"}else{"DENY"}))
                try { $sp.WriteLine($(if($ok){"@L,$LockMs"}else{"@L,0"})) } catch { Log "[send] @L 失败" }
                $ev = [ordered]@{ type="rfid"; node=$Node; ts=(Ts); uid=$uid; ok=$ok }
                if (-not $ok) { $ev["buzzer_level"]="deny"; $ev["pattern_ms"]="80x2/400" }
                if (-not (PostJson $ev)) { $failed++ }
            }
            default {
                Log "[warn] 未知帧类型 '$tag'（忽略）"
            }
        }
    }
}
finally {
    try { $sp.Close() } catch { }
    Log ("[bye] failed={0}" -f $failed)
}

