#!/usr/bin/env bash
# ============================================================================
# Deploy genes camellia app to DMZ server behind Cloudflare proxy
#
# Prerequisites:
#   1. Debian/Ubuntu DMZ server with SSH access as root (or sudo user)
#   2. Domain added to Cloudflare with DNS managed there
#   3. Cloudflare Origin CA certificate + key (see STEP 0 below)
#
# Usage:
#   1. Edit deploy.conf with your settings
#   2. Generate the Cloudflare Origin CA cert (see STEP 0)
#   3. Run: sudo -E bash deploy-dmz.sh
# ============================================================================

set -euo pipefail

# ── Load configuration ────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONF_FILE="${SCRIPT_DIR}/deploy.conf"

if [[ ! -f "$CONF_FILE" ]]; then
    echo "ERROR: Config file not found: ${CONF_FILE}" >&2
    echo "Copy deploy.conf.example to deploy.conf and edit it." >&2
    exit 1
fi

source "$CONF_FILE"

# Environment variables override config file values
ADMIN_PASSWORD="${ADMIN_PASSWORD:-}"
SECRET_KEY="${SECRET_KEY:-$(openssl rand -hex 32)}"

# ── STEP 0: Cloudflare Origin CA Certificate ───────────────────────────────
#
# Before running this script, generate an Origin CA certificate in the
# Cloudflare dashboard:
#
#   1. Log in to dash.cloudflare.com → select your domain
#   2. SSL/TLS → Origin Server → Create Certificate
#   3. Choose:
#      - Private key type: RSA (2048)
#      - Hostnames: your domain
#      - Validity: 15 years (default)
#   4. Cloudflare will show the Origin Certificate and Private Key
#   5. Save them to the paths configured in deploy.conf (SSL_CERT / SSL_KEY)
#
# Then in Cloudflare dashboard:
#   6. SSL/TLS → Overview → set mode to "Full (strict)"
#   7. DNS → ensure the A/AAAA record for the domain is Proxied (orange cloud)
#
# ── HELPER ─────────────────────────────────────────────────────────────────

log() { echo -e "\n\033[1;32m>>> $1\033[0m"; }
err() { echo -e "\033[1;31mERROR: $1\033[0m" >&2; exit 1; }

# ── PRE-FLIGHT CHECKS ─────────────────────────────────────────────────────

[[ $EUID -eq 0 ]] || err "Run this script as root (sudo -E bash deploy-dmz.sh)"

if [[ ! -f "$SSL_CERT" ]] || [[ ! -f "$SSL_KEY" ]]; then
    err "Cloudflare Origin CA cert not found.\n\
Place certificate at: ${SSL_CERT}\n\
Place private key at: ${SSL_KEY}\n\
See STEP 0 in this script for instructions."
fi

if [[ -z "$ADMIN_PASSWORD" ]]; then
    echo ""
    echo "No ADMIN_PASSWORD set. You can either:"
    echo "  export ADMIN_PASSWORD='your-password' before running, or"
    read -rp "  Enter admin password now: " ADMIN_PASSWORD
    [[ -n "$ADMIN_PASSWORD" ]] || err "Admin password is required"
fi

log "Configuration:"
echo "  Domain:       ${DOMAIN}"
echo "  App dir:      ${APP_DIR}"
echo "  Database:     ${DATABASE_URL}"
echo "  Service:      ${SERVICE_NAME}"
echo "  Workers:      ${GUNICORN_WORKERS}"
echo "  SSL cert:     ${SSL_CERT}"

# ── STEP 1: Install system packages ───────────────────────────────────────

log "Installing system packages"
apt-get update -qq
apt-get install -y -qq nginx python3 python3-venv python3-pip git

# ── STEP 2: Clone or update the repository ────────────────────────────────

log "Setting up application at ${APP_DIR}"
if [[ -d "${APP_DIR}/.git" ]]; then
    cd "$APP_DIR"
    git pull --ff-only
else
    git clone "$REPO_URL" "$APP_DIR"
    cd "$APP_DIR"
fi

# ── STEP 3: Python virtual environment and dependencies ───────────────────

log "Setting up Python venv and installing dependencies"
python3 -m venv "${APP_DIR}/venv"
"${APP_DIR}/venv/bin/pip" install --upgrade pip -q
"${APP_DIR}/venv/bin/pip" install -r "${APP_DIR}/requirements.txt" -q

# ── STEP 4: Create data directory and set permissions ─────────────────────

log "Setting up data directory and permissions"
mkdir -p "${APP_DIR}/data"
chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"

# ── STEP 5: Create environment file ──────────────────────────────────────

log "Writing environment file"
cat > "${APP_DIR}/.env" <<ENVEOF
SECRET_KEY=${SECRET_KEY}
ADMIN_PASSWORD=${ADMIN_PASSWORD}
DATABASE_URL=${DATABASE_URL}
ENVEOF
chmod 600 "${APP_DIR}/.env"
chown "${APP_USER}:${APP_USER}" "${APP_DIR}/.env"

# ── STEP 6: Create systemd service ───────────────────────────────────────

log "Creating systemd service: ${SERVICE_NAME}"
cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<SVCEOF
[Unit]
Description=Gene's Camellias gunicorn app
After=network.target

[Service]
User=${APP_USER}
Group=${APP_USER}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${APP_DIR}/venv/bin/gunicorn \\
    --workers ${GUNICORN_WORKERS} \\
    --bind unix:${APP_DIR}/${SERVICE_NAME}.sock \\
    --timeout ${GUNICORN_TIMEOUT} \\
    -m 007 \\
    run:app
ExecReload=/bin/kill -HUP \$MAINPID
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}.service"
systemctl restart "${SERVICE_NAME}.service"

# ── STEP 7: Configure nginx with Cloudflare Origin CA SSL ─────────────────

log "Configuring nginx site: ${SERVICE_NAME}"
cat > "/etc/nginx/sites-available/${SERVICE_NAME}" <<NGXEOF
# Redirect HTTP to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN};
    return 301 https://\$server_name\$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name ${DOMAIN};

    # Cloudflare Origin CA certificate
    ssl_certificate     ${SSL_CERT};
    ssl_certificate_key ${SSL_KEY};
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    # Only allow connections from Cloudflare IPs (optional but recommended)
    # Uncomment and update these periodically from:
    # https://www.cloudflare.com/ips-v4 and https://www.cloudflare.com/ips-v6
    #
    # allow 173.245.48.0/20;
    # allow 103.21.244.0/22;
    # allow 103.22.200.0/22;
    # allow 103.31.4.0/22;
    # allow 141.101.64.0/18;
    # allow 108.162.192.0/18;
    # allow 190.93.240.0/20;
    # allow 188.114.96.0/20;
    # allow 197.234.240.0/22;
    # allow 198.41.128.0/17;
    # allow 162.158.0.0/15;
    # allow 104.16.0.0/13;
    # allow 104.24.0.0/14;
    # allow 172.64.0.0/13;
    # allow 131.0.72.0/22;
    # deny all;

    # Pass real client IP from Cloudflare
    set_real_ip_from 173.245.48.0/20;
    set_real_ip_from 103.21.244.0/22;
    set_real_ip_from 103.22.200.0/22;
    set_real_ip_from 103.31.4.0/22;
    set_real_ip_from 141.101.64.0/18;
    set_real_ip_from 108.162.192.0/18;
    set_real_ip_from 190.93.240.0/20;
    set_real_ip_from 188.114.96.0/20;
    set_real_ip_from 197.234.240.0/22;
    set_real_ip_from 198.41.128.0/17;
    set_real_ip_from 162.158.0.0/15;
    set_real_ip_from 104.16.0.0/13;
    set_real_ip_from 104.24.0.0/14;
    set_real_ip_from 172.64.0.0/13;
    set_real_ip_from 131.0.72.0/22;
    real_ip_header CF-Connecting-IP;

    location / {
        proxy_pass http://unix:${APP_DIR}/${SERVICE_NAME}.sock;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /static/ {
        alias ${APP_DIR}/app/static/;
        expires 1d;
        add_header Cache-Control "public, immutable";
    }
}
NGXEOF

# Enable site, remove default if present
ln -sf "/etc/nginx/sites-available/${SERVICE_NAME}" "/etc/nginx/sites-enabled/${SERVICE_NAME}"
rm -f /etc/nginx/sites-enabled/default

nginx -t || err "Nginx config test failed"
systemctl reload nginx

# ── STEP 8: SSL directory setup ───────────────────────────────────────────

log "Setting SSL cert permissions"
chmod 600 "$SSL_KEY"
chmod 644 "$SSL_CERT"

# ── DONE ──────────────────────────────────────────────────────────────────

log "Deployment complete!"
echo ""
echo "  Domain:    https://${DOMAIN}"
echo "  App dir:   ${APP_DIR}"
echo "  Service:   systemctl status ${SERVICE_NAME}"
echo "  Nginx:     /etc/nginx/sites-available/${SERVICE_NAME}"
echo "  SSL cert:  ${SSL_CERT}"
echo ""
echo "Cloudflare checklist:"
echo "  [ ] Origin CA cert + key placed at paths above"
echo "  [ ] SSL/TLS mode set to 'Full (strict)' in Cloudflare dashboard"
echo "  [ ] DNS A record for ${DOMAIN} points to this server's public IP"
echo "  [ ] DNS record is Proxied (orange cloud icon)"
echo ""
