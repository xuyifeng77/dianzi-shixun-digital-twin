# 证据目录（每天的东西都存在这里）

> 规则：**产出 = 文件变化或一条实测数据。** 所以每天收工前，这里必须多出至少一个文件。
> 板子上的东西断电就没了，**一定要拷回电脑**。

## 建议的目录结构（按天建）

```
证据\
  D1\   ssh成功.png          板子实物.jpg      D1记录.md
  D2\   样张.png              d2_camera.log    nodeA-interfaces.txt
  D3\   d3_probe.log          camera-test脚本内容.txt
  D4\   soak.csv              soak_cam.log     D4结论.md
  D5\   d5_bridge.log         json样例.txt     三项自测记录.md
  D6\   双板在线.png          nodeA-d6.log     nodeB-d6.log
  D7\   beta链路.png          net_bw_beta_*.txt
  D8\   d8_alpha.log          net_bw_alpha_*.txt
  D9\   exp1_alpha_n1_run01.csv ...
  D10\  节点实现章节.md
```

## 每份证据要能回答三个问题

1. **这是什么**（文件名要能自解释，别叫 `1.png`）
2. **什么时候、在哪台机器上做的**
3. **口径是什么**（例如"带宽 = eth0 tx_bytes 60s 差值 ÷ 60"）

## 拷回电脑的通用命令（在电脑的 PowerShell 里执行）

```powershell
# 单个文件
scp root@192.168.1.101:/root/soak.csv "D:\DSHworkspace\B岗-上手指导\证据\D4\"

# 整个目录
scp -r root@192.168.1.101:/root/logs "D:\DSHworkspace\B岗-上手指导\证据\D5\"
```

> 别忘了把 IP 换成当天实际的地址。

## 一句话提醒

`07-分工与文档责任.md` §一 的第 3 条铁律：**"产出 = 文件变化或一条实测数据，不是'今天研究了'。"**
答辩时你能拿出的东西，就是这些文件。
