# Fail2Ban Setup - API Attack Protection

## 🛡️ What This Does

Automatically blocks IPs that make suspicious requests targeting:
- `.env` files
- `.git` directories
- `config.json`
- AWS credentials
- Other sensitive paths

**Protection Rules:**
- **Max retries:** 5 suspicious requests
- **Time window:** 5 minutes
- **Ban duration:** 1 hour (auto-unban after)

---

## ✅ **Automated Setup**

**Fail2Ban is now part of your automated deployment!** 🎉

### For New EC2 Instances
Fail2Ban is automatically installed and configured via Terraform user_data when the instance is created.

### For Existing Instances
Fail2Ban is automatically set up/updated every time you deploy:

```bash
# Just run your normal deployment
./scripts/dev/deploy-to-production.sh
# or
./scripts/dev/push-and-deploy.sh
```

The deployment script will:
1. ✅ Install fail2ban (if not already installed)
2. ✅ Create custom filter for API attacks
3. ✅ Configure jail rules
4. ✅ Set up Docker log monitoring
5. ✅ Enable and start all services

**No manual steps required!** The setup is idempotent, so it's safe to run multiple times.

---

## 🔧 Manual Installation (Optional)

If you need to set up Fail2Ban manually or on a different server:

### Step 1: SSH to EC2 Instance
```bash
ssh ubuntu@3.82.8.27  # or ec2-user for Amazon Linux
```

### Step 2: Run Setup Script
```bash
# Pull latest code
cd /opt/zivohealth
git pull origin main

# Run the setup script
./scripts/dev/setup-fail2ban.sh
```

---

## 📊 Monitoring Commands

### Check Fail2Ban Status
```bash
sudo fail2ban-client status
```

### Check API Protection Jail
```bash
sudo fail2ban-client status api-env-scan
```

**Example output:**
```
Status for the jail: api-env-scan
|- Filter
|  |- Currently failed: 0
|  |- Total failed:     12
|  `- File list:        /var/log/docker/zivohealth-api.log
`- Actions
   |- Currently banned: 2
   |- Total banned:     2
   `- Banned IP list:   192.168.1.100 45.76.33.21
```

### View Banned IPs
```bash
sudo fail2ban-client status api-env-scan | grep "Banned IP"
```

### View Fail2Ban Logs
```bash
sudo tail -f /var/log/fail2ban.log
```

### View Docker API Logs
```bash
sudo tail -f /var/log/docker/zivohealth-api.log
```

---

## 🔓 Unban an IP

If you accidentally ban a legitimate IP:

```bash
# Unban specific IP
sudo fail2ban-client set api-env-scan unbanip 192.168.1.100

# Unban all IPs
sudo fail2ban-client unban --all
```

---

## 🔧 Configuration Files

### Filter (Pattern Matching)
**Location:** `/etc/fail2ban/filter.d/api-env-scan.conf`
```ini
[Definition]
failregex = ^.*"(HEAD|GET|POST) /\.env[^"]*" 401.*$
            ^.*"(HEAD|GET|POST) /\.git[^"]*" 401.*$
            ...
```

### Jail (Rules)
**Location:** `/etc/fail2ban/jail.d/api-protection.conf`
```ini
[api-env-scan]
enabled = true
maxretry = 5
findtime = 300
bantime = 3600
...
```

---

## 🧪 Testing

### Simulate an Attack
```bash
# From another machine, make 6 requests to trigger ban
for i in {1..6}; do
  curl -I http://3.82.8.27/.env
  sleep 1
done
```

### Verify IP Was Banned
```bash
sudo fail2ban-client status api-env-scan
```

You should see your IP in the "Banned IP list".

---

## 📈 What Happens When IP is Banned

1. **Detection:** Fail2Ban sees 5+ failed requests in 5 minutes
2. **Action:** IP is added to iptables firewall rules
3. **Effect:** All traffic from that IP is blocked (not just HTTP)
4. **Duration:** IP remains banned for 1 hour
5. **Auto-Unban:** After 1 hour, IP is automatically unbanned

### Firewall Rule Added
```bash
# View iptables rules
sudo iptables -L f2b-API-ATTACK -n -v

# Example output:
Chain f2b-API-ATTACK (1 references)
pkts bytes target  prot opt in out source        destination
   0     0 REJECT  all  --  *  *   45.76.33.21   0.0.0.0/0     reject-with icmp-port-unreachable
```

---

## 🔄 Service Management

### Start/Stop/Restart Fail2Ban
```bash
sudo systemctl start fail2ban
sudo systemctl stop fail2ban
sudo systemctl restart fail2ban
```

### Check Service Status
```bash
sudo systemctl status fail2ban
sudo systemctl status docker-api-logs
```

### Enable/Disable Auto-Start
```bash
sudo systemctl enable fail2ban   # Start on boot
sudo systemctl disable fail2ban  # Don't start on boot
```

---

## 🎛️ Adjust Settings

### Change Ban Duration (1 hour → 24 hours)
```bash
sudo vim /etc/fail2ban/jail.d/api-protection.conf

# Change:
bantime = 86400  # 24 hours in seconds

# Restart:
sudo systemctl restart fail2ban
```

### Change Max Retries (5 → 3)
```bash
sudo vim /etc/fail2ban/jail.d/api-protection.conf

# Change:
maxretry = 3  # Ban after 3 attempts

# Restart:
sudo systemctl restart fail2ban
```

### Change Time Window (5 min → 10 min)
```bash
sudo vim /etc/fail2ban/jail.d/api-protection.conf

# Change:
findtime = 600  # 10 minutes in seconds

# Restart:
sudo systemctl restart fail2ban
```

---

## 📊 Statistics

### View All-Time Stats
```bash
# Total bans
sudo fail2ban-client status api-env-scan | grep "Total banned"

# Currently banned
sudo fail2ban-client status api-env-scan | grep "Currently banned"
```

### View Ban History
```bash
# Recent bans
sudo grep "Ban" /var/log/fail2ban.log | tail -20

# Recent unbans
sudo grep "Unban" /var/log/fail2ban.log | tail -20
```

---

## 🚨 Troubleshooting

### Fail2Ban Not Banning IPs

**Check 1: Is service running?**
```bash
sudo systemctl status fail2ban
```

**Check 2: Is log file being written?**
```bash
ls -lh /var/log/docker/zivohealth-api.log
tail /var/log/docker/zivohealth-api.log
```

**Check 3: Is pattern matching?**
```bash
sudo fail2ban-regex /var/log/docker/zivohealth-api.log /etc/fail2ban/filter.d/api-env-scan.conf
```

**Check 4: Is jail enabled?**
```bash
sudo fail2ban-client status | grep api-env-scan
```

### Docker Logs Not Forwarding

**Restart log monitoring service:**
```bash
sudo systemctl restart docker-api-logs
sudo systemctl status docker-api-logs
```

**Check if logs are being written:**
```bash
sudo tail -f /var/log/docker/zivohealth-api.log
```

### Accidentally Banned Yourself

**Quick unban:**
```bash
sudo fail2ban-client set api-env-scan unbanip $(curl -s ifconfig.me)
```

---

## 🎯 Expected Results

After setup, you should see:

**Before Fail2Ban:**
```
zivohealth-api | HEAD /.env HTTP/1.1" 401
zivohealth-api | HEAD /.env HTTP/1.1" 401
zivohealth-api | HEAD /.env HTTP/1.1" 401
... (continues indefinitely from same IP)
```

**After Fail2Ban:**
```
zivohealth-api | HEAD /.env HTTP/1.1" 401
zivohealth-api | HEAD /.env HTTP/1.1" 401
zivohealth-api | HEAD /.env HTTP/1.1" 401
zivohealth-api | HEAD /.env HTTP/1.1" 401
zivohealth-api | HEAD /.env HTTP/1.1" 401
[FAIL2BAN] Ban 45.76.33.21
... (no more requests from that IP for 1 hour)
```

---

## ✅ Success Checklist

- [ ] Fail2Ban installed
- [ ] Custom filter created
- [ ] Jail configured
- [ ] Log monitoring active
- [ ] Service started and enabled
- [ ] Test ban/unban works
- [ ] Monitor for 24 hours

---

## 💡 Pro Tips

1. **Whitelist your office IP:**
   ```bash
   sudo vim /etc/fail2ban/jail.d/api-protection.conf
   # Add under [api-env-scan]:
   ignoreip = 127.0.0.1/8 YOUR.OFFICE.IP.ADDRESS
   ```

2. **Email notifications on ban:**
   ```bash
   sudo vim /etc/fail2ban/jail.d/api-protection.conf
   # Add:
   destemail = admin@zivohealth.com
   action = %(action_mwl)s
   ```

3. **Permanent ban for repeat offenders:**
   ```bash
   # Ban for 1 week if banned 3+ times
   bantime = 604800
   ```

---

## 🎉 You're Protected!

Once installed, Fail2Ban will automatically:
- ✅ Detect attack patterns
- ✅ Block malicious IPs
- ✅ Auto-unban after timeout
- ✅ Log all activity
- ✅ Protect your API 24/7

**No manual intervention required!** 🛡️

