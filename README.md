# 同簿 · 通讯录

软件工程（FZU–MU）极限编程作业。支持联系人新增、编辑、删除、搜索、收藏，多条联系方式，以及 Excel 导入和导出。

## 本地运行

需要 Python 3.10 或更高版本。在仓库目录打开 PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m flask --app app run --port 8765
```

在浏览器访问 [本地通讯录](http://127.0.0.1:8765)。默认数据保存在 `instance/contacts.sqlite3`，首次启动时自动创建。

如需录制演示，可在启动前使用单独的数据库：

```powershell
$env:ADDRESS_BOOK_DB = 'instance/demo.sqlite3'
.\.venv\Scripts\python.exe -m flask --app app seed-demo
.\.venv\Scripts\python.exe -m flask --app app run --port 8765
```

演示名录包含四位虚构联系人。首次填充后，直接启动即可继续使用该演示库。

## Excel 使用方式

1. 点击「导入 Excel」→「下载模板」，在第 2 行起每行填写一位联系人。第一行是表头，`姓名` 必填。
2. 同类型的多条联系方式使用 `电话1`、`电话2` 等独立列。邮箱、社交账号和地址采用同样的编号规则。需要保留开头的零时，请在 Excel 中以文本格式录入。
3. 「收藏」填「是」或「否」。上传后新增联系人，姓名相同的记录也会保留。如果任何一行未通过检查，程序会提示行号，整次导入不会写入数据库。
4. 「导出 Excel」导出全部联系人及其联系方式。导出的文件也可以作为导入文件。

导入支持 `.xlsx` 文件的第一个工作表。单次导入文件不超过 4 MB，最多 5,000 行联系人，每位联系人最多 30 项联系方式。

## 模块划分

| 模块 | 职责 |
| --- | --- |
| `app.py` | 页面路由、接收表单、搜索筛选和操作反馈 |
| `store.py` | SQLite 存储及联系人与联系方式的关系 |
| `contacts.py` | 联系人字段、类型和长度校验 |
| `excel.py` | Excel 表头和行校验、导入解析及导出格式 |
| `templates/`、`static/` | 通讯录、编辑和导入页面 |

参见[代码规范](CODE_STYLE.md)和[作业帖](https://bbs.csdn.net/topics/620593436)。
