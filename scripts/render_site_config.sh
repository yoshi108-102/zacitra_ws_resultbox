#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 5 ]]; then
  echo "usage: $0 <region> <cognito-domain> <client-id> <cloudfront-domain> <documents-api-base-url>" >&2
  exit 1
fi

REGION="$1"
COGNITO_DOMAIN="$2"
CLIENT_ID="$3"
CF_DOMAIN="$4"
API_BASE_URL="$5"

sed \
  -e "s/REPLACE_WITH_COGNITO_DOMAIN/${COGNITO_DOMAIN}/g" \
  -e "s/REPLACE_WITH_COGNITO_CLIENT_ID/${CLIENT_ID}/g" \
  -e "s/REPLACE_WITH_CLOUDFRONT_DOMAIN/${CF_DOMAIN}/g" \
  -e "s#REPLACE_WITH_DOCUMENTS_API_BASE_URL#${API_BASE_URL}#g" \
  -e "s/ap-northeast-1/${REGION}/g" \
  /Users/yoshi/zacitra_ws_resultbox/site/config.template.js
