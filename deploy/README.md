# Deploying ai-index on Hetzner CAX11

Designed to run as a **systemd --user** timer so it inherits your `~/.claude/` auth (the Max-subscription login).

## One-time setup on the server

```bash
# 1. Clone into your home dir (NOT /srv — needs your HOME for claude auth).
cd ~
git clone https://github.com/RTB007/ai-index.git
cd ai-index

# 2. Python venv + deps. Install uv if not present.
curl -LsSf https://astral.sh/uv/install.sh | sh
~/.local/bin/uv sync

# 3. One-off: verify `claude` CLI is authenticated under THIS user.
claude -p "say hi" --output-format json

# 4. Install systemd user units.
mkdir -p ~/.config/systemd/user
cp deploy/ai-index.service deploy/ai-index.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now ai-index.timer

# 5. Keep the timer running when you're not logged in.
sudo loginctl enable-linger $USER

# 6. Nginx vhost (as root).
sudo cp deploy/nginx-ai-index.conf /etc/nginx/sites-available/ai-index.lowlandcapital.com
# Edit the file: replace CHANGE_ME with your username so `root` points at ~/ai-index/web.
sudo ln -s /etc/nginx/sites-available/ai-index.lowlandcapital.com /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# 7. TLS via certbot.
sudo certbot --nginx -d ai-index.lowlandcapital.com

# 8. DNS: add an A record for ai-index.lowlandcapital.com pointing at 188.245.161.132.
```

## Backfill 12 months

```bash
cd ~/ai-index
# Indicators + stocks only (fast, ~10 min depending on Trends rate limiting):
.venv/bin/python -m scripts.backfill --days 365

# Add weekly Claude scores for the past year (~52 Claude calls):
.venv/bin/python -m scripts.backfill --days 365 --with-scores --score-step 7 --no-indicators --no-stocks

# Or every day (~365 Claude calls — much slower, uses real Max quota):
.venv/bin/python -m scripts.backfill --days 365 --with-scores --no-indicators --no-stocks
```

## Verifying the timer

```bash
systemctl --user list-timers ai-index.timer
journalctl --user -u ai-index.service -n 100
# Trigger a run by hand:
systemctl --user start ai-index.service
```

## Re-deploy after a code change

```bash
cd ~/ai-index && git pull
~/.local/bin/uv sync   # only if deps changed
# Timer picks up the new code on next fire; or trigger manually:
systemctl --user start ai-index.service
```
