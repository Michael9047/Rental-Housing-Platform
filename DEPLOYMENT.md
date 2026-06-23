# Deployment Guide

Complete production deployment guide for the Rental Housing Matching System.

## Server Requirements

- Ubuntu 22.04/24.04 LTS, 4+ GB RAM, 20+ GB SSD
- Docker 26+, Docker Compose v2
- Public IP with ports 80/443 open

## Quick Start

```bash
# Clone and configure
git clone <repo-url> /opt/rental-housing
cd /opt/rental-housing
cp .env.prod .env.prod.local
# Edit .env.prod.local with real passwords and API keys

# Start services
docker compose -f docker-compose.prod.yml --env-file .env.prod.local up -d

# Run migrations
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head

# Create indexes (first deploy only)
docker compose -f docker-compose.prod.yml exec backend python -c "
import asyncio
from app.db.session import async_session_maker
from app.db.indexes import create_all_indexes
async def run():
    async with async_session_maker() as s:
        await create_all_indexes(s)
asyncio.run(run())
"

# Verify
curl http://localhost:80/api/v1/health
```

## SSL/HTTPS with Let's Encrypt

```bash
# Install certbot
sudo apt install certbot -y

# Obtain certificate
docker compose -f docker-compose.prod.yml stop nginx
sudo certbot certonly --standalone -d your-domain.com -d www.your-domain.com
docker compose -f docker-compose.prod.yml start nginx

# Auto-renewal cron (add to crontab)
echo "0 3,15 * * * certbot renew --quiet --post-hook 'docker compose -f /opt/rental-housing/docker-compose.prod.yml restart nginx'" | sudo crontab -
```

Mount certificates by adding to `docker-compose.prod.yml` nginx service:
```yaml
volumes:
  - /etc/letsencrypt:/etc/letsencrypt:ro
```

Update `frontend/nginx/nginx.conf` to serve HTTPS and redirect HTTP → HTTPS.

## DNS Configuration

| Type | Name | Value |
|------|------|-------|
| A | @ | server-ip |
| A | www | server-ip |

## Backup & Recovery

### Database Backup
```bash
docker compose -f docker-compose.prod.yml exec postgres \
  pg_dump -U rental rental_housing | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz
```

Automated cron: `0 2 * * * /opt/rental-housing/scripts/backup.sh`

### Restore
```bash
gunzip -c backup.sql.gz | docker compose -f docker-compose.prod.yml exec -T postgres psql -U rental rental_housing
```

## Monitoring

- Prometheus metrics at `/metrics` (request counts, latency, Celery tasks, DB pool)
- Structured JSON logging in production
- Health check at `/api/v1/health`
- View logs: `docker compose -f docker-compose.prod.yml logs -f <service>`

## Maintenance

### Database Migrations
```bash
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
docker compose -f docker-compose.prod.yml exec backend alembic revision --autogenerate -m "description"
```

### Scale Horizontally
```bash
docker compose -f docker-compose.prod.yml up -d --scale backend=3 --scale celery-worker=2
```

### Rotate Secrets
Update `.env.prod.local` with new values, then:
```bash
docker compose -f docker-compose.prod.yml restart backend
```

## Troubleshooting

| Issue | Command |
|-------|---------|
| Service won't start | `docker compose -f docker-compose.prod.yml logs <service>` |
| DB connection errors | `docker compose -f docker-compose.prod.yml exec postgres pg_isready` |
| Redis errors | `docker compose -f docker-compose.prod.yml exec redis redis-cli -a <pw> ping` |
| Disk space low | `docker system prune -af --filter "until=24h"` |
| Celery stuck | `docker compose -f docker-compose.prod.yml logs celery-worker` |

## Security Checklist

- [ ] Change all default passwords
- [ ] Generate strong AUTH_SECRET_KEY (64+ chars)
- [ ] Set DEBUG=false and ENVIRONMENT=production
- [ ] Set CORS_ORIGINS to actual domain(s)
- [ ] Enable UFW (ports 22, 80, 443 only)
- [ ] Set up SSL with Let's Encrypt
- [ ] Disable SSH root login
- [ ] Install fail2ban for SSH protection
- [ ] Rotate secrets quarterly
- [ ] Review admin audit logs regularly
