# Stock & Orders Tracking

## Overview
The Stock & Orders tab in the Unit Check Dashboard provides a simple inventory management system for tracking GPS tracking units at different stages.

## Features

### 1. **Not Switched On** 📴
Track equipment you have physically but haven't activated yet.

**Fields:**
- Manufacturer (required)
- Model/Type (required)
- Serial Number
- Notes
- Date Added (automatic)

**Use case:** Units sitting in storage, unopened boxes, or units waiting to be configured.

### 2. **Switched On (Available)** ✅
Track activated equipment that's in EarthRanger but not currently attached to any subject/animal.

**Fields:**
- Manufacturer (required)
- Model/Type (required)
- Serial Number
- Collar Key (in ER)
- EarthRanger Source ID
- Notes
- Date Added (automatic)

**Use case:** Units that are active in the system and ready for deployment. These can be checked in the main Unit Check tab using their collar key or source ID.

### 3. **Future Orders** 🔮
Track planned purchases and orders in process.

**Fields:**
- Manufacturer (required)
- Model/Type (required)
- Quantity
- Status (Planned/Ordered/In Transit/Expected Soon)
- Expected Date
- Notes (supplier, PO number, etc.)
- Date Added (automatic)

**Use case:** Units on order, in planning stages, or in transit from suppliers.

## Data Storage

Stock data is persisted in a JSON file (`unit_stock_data.json`) in the same directory as the app. This means:
- Data survives app restarts
- Easy to backup (just copy the JSON file)
- Can be manually edited if needed
- Portable across deployments

## Usage

1. **Login** to EarthRanger using your credentials
2. **Navigate** to "Stock & Orders" using the sidebar radio button
3. **Add items** using the "➕ Add New" expander in each tab
4. **View** your inventory in the tables below
5. **Delete items** using the delete dropdown and button at the bottom of each section
6. **Monitor summary** metrics at the bottom showing total counts

## Tips

- Use the "Notes" field to add any relevant information (condition, location, deployment history, etc.)
- For "Switched On" units, include the Collar Key and ER Source ID so you can quickly check them in the Unit Check tab
- For "Future Orders", use Notes to track supplier info, PO numbers, and shipping details
- Regular updates keep your inventory accurate and useful for planning

## Integration with Unit Check

Units in the "Switched On (Available)" category should also appear in your main Unit Check dashboard if you search for them by collar key. This helps you:
- Verify a unit is active and reporting
- Check battery levels before deployment
- Confirm GPS functionality

## Backup & Recovery

To backup your stock data:
```bash
# Copy the JSON file
copy unit_stock_data.json unit_stock_data_backup.json
```

To restore from backup:
```bash
# Restore from backup
copy unit_stock_data_backup.json unit_stock_data.json
```

## Future Enhancements

Possible additions:
- Export to CSV
- Import from CSV
- Search/filter functionality
- Move units between categories (e.g., "Not Switched On" → "Switched On")
- Attach images/documents
- Track warranty/service dates
- Historical audit trail
