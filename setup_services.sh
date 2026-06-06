#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICES_DIR="${PROJECT_DIR}/services"
VENV_PYTHON="${PROJECT_DIR}/.venv/bin/python"
ENV_FILE="${PROJECT_DIR}/.env"

mkdir -p "${SERVICES_DIR}"

if [[ ! -x "${VENV_PYTHON}" ]]; then
  echo "Expected virtualenv python at ${VENV_PYTHON}"
  echo "Create it first: python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}. Copy .env.example to .env and set values first."
  exit 1
fi

cat > "${SERVICES_DIR}/roboplace-server.service" <<EOF
[Unit]
Description=RoboPlace Server
After=network.target

[Service]
Type=simple
User=${USER}
WorkingDirectory=${PROJECT_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${VENV_PYTHON} -m uvicorn server.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

cat > "${SERVICES_DIR}/roboplace-connector.service" <<EOF
[Unit]
Description=RoboPlace ESP Serial Connector
After=network.target
Requires=roboplace-server.service

[Service]
Type=simple
User=${USER}
WorkingDirectory=${PROJECT_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${VENV_PYTHON} -m uvicorn connector.main:app --host 0.0.0.0 --port 8001
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

cat > "${SERVICES_DIR}/roboplace-webapp.service" <<EOF
[Unit]
Description=RoboPlace Web Viewer
After=network.target
Requires=roboplace-server.service

[Service]
Type=simple
User=${USER}
WorkingDirectory=${PROJECT_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${VENV_PYTHON} -m uvicorn webapp.main:app --host 0.0.0.0 --port 8002
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

cat > "${SERVICES_DIR}/roboplace-painter.service" <<EOF
[Unit]
Description=RoboPlace Manual Painter
After=network.target
Requires=roboplace-server.service

[Service]
Type=simple
User=${USER}
WorkingDirectory=${PROJECT_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${VENV_PYTHON} -m uvicorn painter.main:app --host 0.0.0.0 --port 8003
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

cat > "${SERVICES_DIR}/roboplace-logviewer.service" <<EOF
[Unit]
Description=RoboPlace Log Viewer
After=network.target
Requires=roboplace-server.service

[Service]
Type=simple
User=${USER}
WorkingDirectory=${PROJECT_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${VENV_PYTHON} -m uvicorn logviewer.main:app --host 0.0.0.0 --port 8004
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

echo "Generated service files in ${SERVICES_DIR}"

if [[ "${1:-}" == "--install" ]] || [[ "${2:-}" == "--install" ]]; then
  sudo cp "${SERVICES_DIR}"/*.service /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable roboplace-server roboplace-connector roboplace-webapp roboplace-painter roboplace-logviewer
  sudo systemctl restart roboplace-server roboplace-connector roboplace-webapp roboplace-painter roboplace-logviewer
  echo "Installed and started services."
  [[ "${1:-}" == "--install" && "${2:-}" != "--nginx" ]] && exit 0
  [[ "${2:-}" == "--install" && "${1:-}" != "--nginx" ]] && exit 0
fi

if [[ "${1:-}" == "--nginx" ]] || [[ "${2:-}" == "--nginx" ]]; then
  if ! command -v nginx >/dev/null 2>&1; then
    echo "nginx not found on this machine. Install it first or skip --nginx."
    exit 1
  fi
  NGINX_SRC="${PROJECT_DIR}/nginx/roboplace.conf"
  if [[ ! -f "${NGINX_SRC}" ]]; then
    echo "Missing ${NGINX_SRC}"
    exit 1
  fi
  sudo cp "${NGINX_SRC}" /etc/nginx/sites-available/roboplace
  if [[ ! -e /etc/nginx/sites-enabled/roboplace ]]; then
    sudo ln -s /etc/nginx/sites-available/roboplace /etc/nginx/sites-enabled/roboplace
  fi
  sudo nginx -t && sudo systemctl reload nginx
  echo "Installed nginx site and reloaded nginx."
  exit 0
fi

echo "Usage:"
echo "  ./setup_services.sh --install    # install systemd services"
echo "  ./setup_services.sh --nginx      # install nginx site config"
echo "  ./setup_services.sh --install --nginx  # do both"
