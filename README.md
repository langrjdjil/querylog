# querylog

**结论要能重跑，条件就得留下来。**

`querylog` 把一次检索的**查询条件、过滤规则、来源和结果清单**存成一份文件，
换台机器也能照着重跑一遍。

- 零依赖，Python 3.10+ 标准库即可运行
- 单文件，`querylog.py` 拷走就能用
- 存档只落在本地 `~/.querylog/`，不联网

<!-- ipos:install -->
## 安装

零依赖，Python 3.10+ 即可：

```bash
pip install langrjdjil-querylog
```

装完直接用命令名调用：

```bash
querylog --help
```

也可以不用安装，直接把 `querylog.py` 拷走用——它只依赖标准库。

## 为什么需要它

做过一点调研之后会发现一个规律：三个月后有人问「这个说法哪来的」，
能拿出来的往往只有一句「我搜过」——那不算数。

因为当时的查询条件没留下来。结果也一样：手里只有几条链接，
但不知道为什么是这几条、而不是另外几条。

`querylog` 做的事很朴素：**把条件和结果放在同一个文件里**。
它还有一条更重要的规定——**「没有」和「没查到」必须分开写**：

| 状态 | 含义 | 能下的结论 |
|---|---|---|
| `not_run` | 还没检索 | 无 |
| `has_results` | 检索到了结果 | 有这些结果 |
| `searched_empty` | 查下来没有 | **在当前条件下不存在**（这是结论） |
| `unavailable` | 没能完成检索 | **无结论**（这是工具的局限） |

把「没能查到」写成「没有」，是调研里最常见的一种自欺。

## 用法

```bash
# 建一条存档（查询条件是必填的，不填就存不成可复现的档案）
python querylog.py --new "查找零依赖 CSV 工具" --query "csv parser stdlib"

# 带过滤条件与来源
python querylog.py --new "查找文档结构检查工具" \
  --query "markdown linter structure" \
  --filter "star:>100" \
  --filter "language:python" \
  --source https://github.com/example/tool

# 追加一条结果
python querylog.py --add 2026-10-26-xxx.json \
  --result-title "csvprofile" --result-url https://github.com/example/csvprofile \
  --result-note "只做体检，不清洗，与我的需求最接近"

# 标记为「查下来没有」（结论）
python querylog.py --empty 2026-10-26-xxx.json --note "按当前条件没有找到符合的"

# 标记为「没能查到」（局限）
python querylog.py --unavailable 2026-10-26-xxx.json --reason "检索服务当时不可达"

# 查看
python querylog.py --list
python querylog.py --show 2026-10-26-xxx.json

# 检查这份存档能不能复现
python querylog.py --check 2026-10-26-xxx.json
```

输出：

```
已创建存档：C:\Users\louis\.querylog\2026-10-26-查找零依赖-csv-工具.json
  查询条件：csv parser stdlib
  条件指纹：a3f19c2b8e04
```

`--check` 的退出码：`0` 表示条件完整可复现，`1` 表示缺字段。

## 存档长什么样

```json
{
  "title": "查找零依赖 CSV 工具",
  "query": "csv parser stdlib",
  "filters": ["star:>100", "language:python"],
  "sources": ["https://github.com/example/tool"],
  "notes": "",
  "created_at": "2026-10-26T14:22:10",
  "condition_hash": "a3f19c2b8e04",
  "results": [
    {
      "title": "csvprofile",
      "url": "https://github.com/example/csvprofile",
      "note": "只做体检，不清洗，与我的需求最接近",
      "added_at": "2026-10-26T14:23:01"
    }
  ],
  "result_state": "has_results",
  "result_note": "已记录 1 条结果。"
}
```

`condition_hash` 是查询条件与过滤规则的哈希：条件相同则指纹相同，
可以用来判断两份存档是不是在同样的条件下做的。

## 已知局限

- **不执行检索**。它只负责记录，不替你联网搜索。条件写对了不代表查得到，
  真实的检索服务有它自己的索引、排序与覆盖范围。
- **不校验来源可达性**。链接是否还活着、指向的是不是预期页面，要另外用链接校验工具查。
- **不整理结果**。结果按添加顺序排列，不排序、不去重、不打标签。
- **不记录检索时间点的影响**。同一条件下，三个月后的结果集可能和当时不同——
  工具会在 `created_at` 里留下时间，但不会替你判断结果是否还代表「当下」。
- **只有本地存储**。不提供同步与多机共享，多台机器上的存档要自己同步。

## 跑测试

```bash
python test_querylog.py
```

测试用独立的临时目录，不写入真实的 `~/.querylog/`。

## 为什么还要做这个

笔记本、便签、聊天记录里都能放链接，但它们都不带「当时是怎么查的」这一层。
`querylog` 补的就是这一层。

它故意做得很笨：没有搜索集成、没有智能排序、没有云同步。
因为这个工具的价值不在于帮你找得快，而在于**让三个月后的自己或别人能重跑一遍**。

## 来源与参考

- GitHub 搜索语法文档：<https://docs.github.com/en/search-github/searching-on-github>
- RFC 3339 时间戳格式（存档里的时间戳口径）：<https://www.rfc-editor.org/rfc/rfc3339>
- Python `hashlib` 模块文档：<https://docs.python.org/3/library/hashlib.html>

---

## 关于作者

langrjdjil 做检索过程留痕。这个工具把查询条件和结果清单放在同一个文件里。

- 个人主页：<https://langrjdjil.github.io>
- 仓库：<https://github.com/langrjdjil/querylog>

## 许可

MIT，见 [LICENSE](LICENSE)。
