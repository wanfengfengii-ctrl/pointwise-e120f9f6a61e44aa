# 回用水试验站复测能力台账

试验员从台架测量单录入有向流路和逐段容量。核定员按全批量确认各站能交付或接收多少水。夜班值守员在试验台下线后，凭两站的固定材料决定某个公开口是否能安排复测。次班支路发生改接时，旧报告仍可用于核对当时采用的材料。

## 一班工作

1. 白班在两站登记同一批号、全批量与四个公共口。两库可采用不同口序，口身份须一致。
2. 按台架测量单录入两站流路。每段端点、容量和测量出处固定在一个有编号的修订下。
3. 核定员用 `seal` 检查原修订是否有满批守恒分流。合格时取得固定能力件号。
4. 通过 `get_packet` 按号领取站件。站内端点、流路、逐段测量和原测行都保留在站库。
5. 中心接纳供给件与接收件，形成可独立选用的接纳号。两座站库此后可以关闭。
6. 夜班按两个接纳号和一个公开口发起核账。中心将精确范围或不可行判定连同两件出处及成功回执一次提交。
7. 次班按父修订录入改接测量，签发新件并与原接收件另行核账。
8. 重开中心后按旧报告号读回或导出旧请求、出处、判定及回执，使用新报告安排本次复测。

## 运行

使用 Python 3.11 标准库。从项目根目录运行完整业务回归和演示。

```text
python3 -B check_project.py
python3 -B run_station.py demo
```

标准核验脚本由运行平台物化。完整 unittest 套件在 `tests` 包中，也可用 `python3 -B -m unittest discover -s tests -t .` 执行。演示显式装载 `samples/shift.json`，在临时目录分别建立供给、接收与中心库。两次核账前均已关闭站库。演示从真实签发和重开记录输出结果。修订和站件使用不透明编号，样例业务量、报告顺序及演示输出固定。

## 公开 Python 接口

`run_station.open_station(path)` 与 `run_station.open_center(path)` 是带初始化的 SQLite 连接上下文。已有连接可调用相应 `initialize_station(db)` 或 `initialize_center(db)`。初始化只补建缺失模式。写入口管理各自的事务，调用时连接须处于空闲事务状态。两站和中心分别使用自己的库。

| 调用 | 模块 | 返回 |
| --- | --- | --- |
| `register(db, batch_id, ports, total)` | `station.batches` | `Batch`，含固定清册及全批量 |
| `get_batch(db, batch_id)` | `station.batches` | 原批次 |
| `revise(db, batch_id, side, root, measurements, parent_id=...)` | `station.revisions` | 新修订号 |
| `get_revision(db, revision_id)` | `station.revisions` | 含父号和原测行的修订 |
| `seal(db, revision_id)` | `issue.publish` | 原修订的固定站件号。重复封发领取同一编号 |
| `get_packet(db, packet_id)` | `issue.transfer` | 固定站件并记录本次领取 |
| `encode_packet(packet)` / `decode_packet(encoded)` | `issue.envelope` | 稳定 JSON / 固定件对象 |
| `admit(db, material)` | `review.admission` | 中心接纳号。材料可为固定件对象或其 JSON |
| `get_accepted(db, accepted_id)` | `review.admission` | 该次接纳的固定材料 |
| `review(db, supply_id, receive_id, port)` | `review.reconcile` | `Report`，含 `report_id`、`snapshot` 和 `receipt` |
| `get_report(db, report_id)` / `export(db, report_id)` | `reports.readback` / `reports.export` | 原定稿对象 / 稳定 JSON |

`Measurement(start, end, capacity, source)` 来自 `station.measurements`。站别取 `supply` 或 `receive`，`root` 是站内供水或集水节点，必须与四个公开口区分。流路段须有两个不同的非空端点。独立测量的平行段可以各自录入。公开口量是供给侧向外或接收侧向内的净交接量。内部节点守恒，每段流量在零到相应容量之间。允许有效有向环和分流。四口都须非负且合计为正的全批量。容量可以为零。升数接受整数、`Fraction` 或有理数字符串，例如 `3/2`，JSON 用约分后的字符串传输和保存。

站件 V1 外层固定件号、批号、站别、来源修订、公共口清册和全批量。能力正文保全指定修订在四个公开口上全部且仅有的满批可达向量。按站件自身清册解释正文口坐标，跨站按口身份比对。中心保存可信来源交付的已编码固定材料，并用所选两件核对同一四口向量。`snapshot.result.status` 为 `feasible` 时，上下界均为 `Fraction`，允许两端均为零或相同的分数。`infeasible` 时上下界均为 `None`，也会产生报告与成功回执。领取和导出读取已经持久化的快照及回执。

非法登记、测量、站件格式和选件抛出 `ValueError`，其中包括负量、空白必要字段、同号重复登记、跨批或跨站父号、错站别、混批、批量不一致、清册不一致和未知指定口。未知批号、修订号、站件号、接纳号或报告号抛出 `KeyError`。站内能力不足以完成整批时 `seal` 抛出 `ValueError`，无新增核定和站件。SQLite 写入或提交失败向调用方传播原异常，发行回滚站件和本次核定，签发回滚报告和回执。更正追加新修订，原件与原报告保留。

## 可人工复核的样例

- 全批 2 L。旧供给的 AB、CD 各占一条 1 L 支路。接收必须用 B 口 1 L 时，AB 已用满，A 的范围为 [0,0] L。改接为 AC、BD 后，A 的范围为 [0,1] L。
- 若接收同时要求 A=1 L、B=1 L，旧件无共同向量，改接件可行且 A=[1,1] L。
- 若接收要求 B=1/2 L、D=1 L，原两支路各须用满，唯一共同向量为 (1/2,1/2,0,1) L。
- 同比减半时，第一例旧件仍是 [0,0] L，改接后为 [0,1/2] L。对接收件换用合法口序时须保持同一判定。
