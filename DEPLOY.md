# Deploy (manual, pull-to-deploy)

VPS `87.99.136.82`, served at `scibowl.djiang.xyz`. systemd unit reads the API
key from `/opt/mit-scibowl/.env`.

## Redeploy after a push
```
ssh root@87.99.136.82
cd /opt/mit-scibowl && git pull && systemctl restart mit-scibowl
# if requirements.txt changed: .venv/bin/pip install -r requirements.txt
```

## Enable the "Explain approach" feature
Put your Anthropic key in the env file, then restart:
```
echo 'ANTHROPIC_API_KEY=sk-ant-...' > /opt/mit-scibowl/.env
systemctl restart mit-scibowl
```
Explanations are cached to `data/explanations.json` (gitignored) so each
question only costs one API call ever.

## One-time infra (already done)
- Deploy key `vps-scibowl-deploy` on the repo; SSH alias `github-scibowl` in `~/.ssh/config`.
- systemd unit `/etc/systemd/system/mit-scibowl.service` → uvicorn on `127.0.0.1:7792`.
- Caddy block for `scibowl.djiang.xyz` → `reverse_proxy 127.0.0.1:7792`.
