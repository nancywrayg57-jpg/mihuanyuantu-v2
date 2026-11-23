# 黄志松家族记忆档案馆

Vue 3 + PocketBase + Caddy，部署于 `huangzhisong.com`。

## 本地

```bash
cd frontend && npm install && npm run build
cd .. && docker compose up --build
```

## 部署

```bash
bash deploy.sh
```

## 端测

```bash
node tests/e2e_verify.mjs
```

账号见家族登录页点选列表；管理员为黄祥财。
