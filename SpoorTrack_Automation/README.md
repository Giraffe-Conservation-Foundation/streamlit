# SpoorTrack Automated Reporting System

**Secure, isolated, test-first automation for quarterly SpoorTrack performance reports**

## 🗂️ Directory Structure

```
SpoorTrack_Automation/
├── config/          # Secure configuration storage (encrypted credentials)
├── reports/         # Generated reports and charts
├── logs/           # System logs and audit trail
├── secure_setup.py # Initial secure configuration setup
├── test_report.py  # Generate test report for review
└── enable_automation.py # Enable full automation after testing
```

## 🚀 Quick Start

### 1. Initial Setup
```bash
python secure_setup.py
```
- Configure EarthRanger credentials securely
- Set up email delivery (optional for testing)
- Test EarthRanger connection

### 2. Generate Test Report
```bash
python test_report.py
```
- Pulls live data from EarthRanger
- Generates sample quarterly report
- Shows exactly what automated reports will look like
- **Review the output before enabling automation**

### 3. Enable Full Automation
```bash
python enable_automation.py
```
- Activates quarterly automation
- Creates Windows Task Scheduler entry
- Sets up comprehensive reporting system

## 🔐 Security Features

- **Encrypted credential storage** - No plain text passwords
- **Isolated directory** - Separate from other projects
- **Secure file permissions** - User-only access
- **Audit logging** - Complete activity trail
- **Test-first approach** - Verify before automating

## 📊 What Reports Include

### Test Reports (30-day sample)
- Limited to 5 units for quick testing
- Basic performance metrics
- Connection verification

### Full Quarterly Reports
- **ALL SpoorTrack units** analyzed
- **3 months of data** per quarter
- **Comprehensive metrics:**
  - Battery voltage trends
  - Transmission success rates
  - Location accuracy
  - Performance scoring
- **Interactive charts** and visualizations
- **Automatic email delivery**

## ⏰ Automation Schedule

- **Frequency:** Quarterly (every 3 months)
- **Timing:** First day of quarter at 9:00 AM
- **Data:** Live pulls from EarthRanger
- **Delivery:** Automatic email with attachments
- **No manual intervention required**

## 🔧 Configuration Files

- `config/spoortrack_config.json` - Main configuration (encrypted)
- `logs/` - Detailed operation logs
- `reports/` - All generated reports and charts

## 📧 Email Setup

For automated email delivery:
1. Use Gmail with App Password (recommended)
2. Enable 2-Step Verification in Google Account
3. Generate App Password in Security settings
4. Use App Password (not regular Gmail password)

## 🛡️ Security Best Practices

- Credentials are encrypted with system-specific keys
- Config files have restricted permissions
- Complete audit trail in logs
- No network transmission of credentials except to Gmail/EarthRanger
- Local storage only

## 🔍 Troubleshooting

### Connection Issues
- Check EarthRanger server URL
- Verify API token/credentials
- Review logs in `logs/` directory

### Email Issues
- Confirm Gmail App Password setup
- Check SMTP settings (smtp.gmail.com:587)
- Verify recipient email addresses

### Automation Issues
- Check Windows Task Scheduler
- Review `logs/` for error details
- Run test report first to verify setup

## 📝 Manual Operations

### Run Single Report
```bash
python quarterly_reporter.py
```

### Check Configuration
```bash
python test_report.py
```

### View Logs
```bash
# Latest log files in logs/ directory
type logs\*.log
```

## 🎯 Success Indicators

✅ **Setup Complete:** secure_setup.py runs without errors
✅ **Connection Working:** test_report.py generates sample report  
✅ **Automation Active:** enable_automation.py creates scheduler
✅ **Quarterly Running:** Reports appear in reports/ directory

## 📞 Support

- Check `logs/` directory for detailed error information
- All operations are logged with timestamps
- Test reports help verify setup before automation
- Manual override available for all operations

---

**This system provides truly "set and forget" automation while maintaining complete security and giving you full control over the process.**
