# SM HR

人力资源管理：入转调离、考勤、绩效、培训与组织人员。

```powershell
git clone https://github.com/luoshitianchen/SM-HR.git
cd SM-HR
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8500
```

接口：`/health`、`/readyz`、`/api/overview`、`/api/items`、`/api/ops/metrics`、`/api/crypto/status`。
