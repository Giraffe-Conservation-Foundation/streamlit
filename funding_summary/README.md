# Funding Summary Dashboard

Secure financial donation analysis and reporting dashboard for Giraffe Conservation Foundation.

## Features

### 🔐 Security
- Password-protected access to sensitive financial data
- Secure authentication required before accessing dashboard
- Session-based access control

### 📊 Data Analysis
- **Multi-sheet Excel Processing**: Upload Excel files with multiple tabs (each representing different payment modes)
- **Funding Type Analysis**: Categorizes donations by type (zoo, private, corporate, etc.)
- **Payment Mode Analysis**: Analyzes donations by payment method (PayPal, Cheque, Wire, etc.)
- **Donor Analysis**: Comprehensive donor information and contribution patterns

### 📈 Visualizations
- **Pie Charts**: Funding distribution by type
- **Bar Charts**: Funding breakdown by payment mode
- **Trend Analysis**: Monthly funding trends over time
- **Top Donors**: Ranking of largest contributors

### 📋 Reporting
- **Summary Tables**: Detailed breakdowns of all funding metrics
- **Export Functionality**: Download comprehensive Excel reports
- **Raw Data Viewer**: Access to processed raw data

## Usage

### 1. Authentication
- Enter the secure password to access the dashboard
- Contact administrator for access credentials

### 2. Upload Data
- Upload an Excel (.xlsx) file with multiple sheets
- Each sheet represents a different payment mode (e.g., "PayPal", "Cheque", "Wire Transfer")
- Columns should include:
  - **Donor/Name**: Name of the donor
  - **Amount**: Donation amount (numbers only)
  - **Type**: Funding type (zoo, private, corporate, etc.)
  - **Date**: Date of donation (optional)
  - **Description**: Purpose or notes (optional)

### 3. Analysis
The dashboard will automatically:
- Process all sheets and combine the data
- Standardize column names and data formats
- Generate comprehensive analysis and visualizations
- Provide export options for reports

## Expected Excel Format

### Sheet Structure
```
Sheet Name: PayPal
| Donor Name    | Amount | Type     | Date       | Description        |
|---------------|--------|----------|------------|--------------------|
| John Smith    | 500.00 | Private  | 2024-01-15 | General support    |
| City Zoo      | 2000.00| Zoo      | 2024-01-20 | Giraffe program    |

Sheet Name: Cheque
| Donor         | Amount | Type     | Date       | Notes              |
|---------------|--------|----------|------------|--------------------|
| Jane Doe      | 1000.00| Private  | 2024-02-01 | Memorial donation  |
| Corp Inc      | 5000.00| Corporate| 2024-02-15 | CSR initiative     |
```

### Flexible Column Names
The system accepts various column naming conventions:
- **Donor**: donor, donor_name, name, from, contributor
- **Amount**: amount, donation, value, sum, total
- **Type**: type, funding_type, donor_type, category, source
- **Date**: date, donation_date, received_date, timestamp
- **Description**: description, notes, memo, purpose, project

## Security Configuration

### Password Management
The password is hashed using SHA-256 for security. To change the password:

1. Generate a new hash for your desired password:
   ```python
   import hashlib
   password = "your_new_password"
   hash_value = hashlib.sha256(password.encode()).hexdigest()
   print(hash_value)
   ```

2. Update the `FUNDING_PASSWORD_HASH` variable in `app.py` with the new hash

⚠️ **Important**: The password should be strong and kept confidential.

## Dependencies

- streamlit>=1.28.0
- pandas>=1.5.0
- plotly>=5.15.0
- openpyxl>=3.1.0
- xlrd>=2.0.0

## File Structure

```
funding_summary/
├── app.py              # Main dashboard application
├── requirements.txt    # Python dependencies
└── README.md          # This documentation
```

## Installation

1. Ensure all dependencies are installed:
   ```bash
   pip install -r funding_summary/requirements.txt
   ```

2. The dashboard is automatically available as page 9 in the Streamlit app

## Support

For technical support or access requests, contact the system administrator.
