FROM php:8.4-fpm-alpine
RUN apk add --no-cache msmtp ca-certificates \
 && echo "sendmail_path = \"/usr/bin/msmtp -t -i\"" > /usr/local/etc/php/conf.d/mail.ini \
 && echo "expose_php = Off" > /usr/local/etc/php/conf.d/security.ini
