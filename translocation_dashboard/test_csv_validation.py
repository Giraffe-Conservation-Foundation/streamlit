"""
Quick CSV validation test - no credentials needed
"""
import pandas as pd

CSV_FILE = r"G:\My Drive\Data management\streamlit\Historical event push\GCF_translocations_260114.csv"

print("="*80)
print("QUICK CSV VALIDATION")
print("="*80)

try:
    df = pd.read_csv(CSV_FILE)
    print(f"\n[OK] Loaded CSV: {len(df)} rows, {len(df.columns)} columns")
    
    print(f"\nColumns: {list(df.columns)}")
    
    # Check required fields
    required = ['capture_date', 'origin_country', 'destination_country', 'species']
    missing = [c for c in required if c not in df.columns]
    if missing:
        print(f"\n[ERROR] Missing required columns: {missing}")
    else:
        print(f"\n[OK] All required columns present")
    
    # Check data completeness
    print(f"\nData completeness:")
    print(f"  - Total rows: {len(df)}")
    print(f"  - Rows with capture dates: {df['capture_date'].notna().sum()}")
    print(f"  - Rows with release dates: {df['release_date'].notna().sum()}")
    print(f"  - Rows with origin coords: {df['origin_latitude'].notna().sum()}")
    print(f"  - Rows with dest coords: {df['destination_latitude'].notna().sum()}")
    print(f"  - Rows with species: {df['species'].notna().sum()}")
    
    # Species list
    print(f"\nUnique species ({df['species'].nunique()}):")
    for species in df['species'].dropna().unique():
        count = (df['species'] == species).sum()
        print(f"  - {species}: {count} events")
    
    # Translocation types
    if 'trans_type' in df.columns:
        print(f"\nTranslocation types:")
        for ttype in df['trans_type'].dropna().unique():
            count = (df['trans_type'] == ttype).sum()
            print(f"  - {ttype}: {count} events")
    
    # Countries
    print(f"\nOrigin countries:")
    for country in df['origin_country'].dropna().unique()[:10]:
        count = (df['origin_country'] == country).sum()
        print(f"  - {country}: {count} events")
    
    print(f"\nDestination countries:")
    for country in df['destination_country'].dropna().unique()[:10]:
        count = (df['destination_country'] == country).sum()
        print(f"  - {country}: {count} events")
    
    # Sample date parsing
    print(f"\nSample capture dates:")
    sample_dates = df['capture_date'].dropna().head(5)
    for date in sample_dates:
        print(f"  - {date}")
    
    print("\n[OK] CSV structure looks good!")
    print("\nNext step: Run with credentials to upload")
    print("Usage: python validate_and_upload_historical.py <username> <password>")
    
except Exception as e:
    print(f"\n[ERROR] {e}")
    import traceback
    traceback.print_exc()
