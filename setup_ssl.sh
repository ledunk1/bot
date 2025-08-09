#!/bin/bash
# Optional SSL setup with Let's Encrypt

echo "🔐 SSL Certificate Setup (Optional)"
echo "=================================="

# Check if domain is provided
if [ -z "$1" ]; then
    echo "Usage: ./setup_ssl.sh your-domain.com"
    echo ""
    echo "📝 Steps to setup SSL:"
    echo "1. Point your domain to this server IP"
    echo "2. Run: ./setup_ssl.sh your-domain.com"
    echo ""
    echo "⚠️ Note: SSL requires a valid domain name"
    echo "For IP-only access, SSL is not required"
    exit 1
fi

DOMAIN=$1

echo "🌐 Setting up SSL for domain: $DOMAIN"

# Install Certbot
echo "📦 Installing Certbot..."
sudo apt update
sudo apt install -y certbot python3-certbot-apache

# Get SSL certificate
echo "🔐 Obtaining SSL certificate..."
sudo certbot --apache -d $DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN

# Setup auto-renewal
echo "🔄 Setting up auto-renewal..."
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer

# Test renewal
echo "🧪 Testing renewal..."
sudo certbot renew --dry-run

echo ""
echo "✅ SSL setup completed!"
echo "🌐 Your site is now available at: https://$DOMAIN"
echo "🔄 Auto-renewal is configured"