FROM nginx:1.27-alpine
COPY default.conf.template /etc/nginx/templates/default.conf.template
# Proměnné nginx ($uri…) nesmí envsubst přepsat, jen náš token.
ENV NGINX_ENVSUBST_FILTER=CLAUDE_CODE_OAUTH_TOKEN
