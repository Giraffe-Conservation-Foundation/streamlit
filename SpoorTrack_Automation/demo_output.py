#!/usr/bin/env python3
"""
Demo Output for SpoorTrack Performance Report
Shows what the actual report output would look like
"""

def show_demo_output():
    """Show sample output that the SpoorTrack report would generate"""
    
    print("🦒 SpoorTrack Performance Report Generator")
    print("=" * 45)
    print("Analyzes performance of all deployed SpoorTrack sources")
    print("Reports mean battery voltage and observations per day\n")
    
    print("🔑 Authenticating with EarthRanger...")
    print("✅ Authentication successful!")
    print("")
    
    print("🔍 Searching for SpoorTrack sources...")
    print("📊 Total sources found: 157")
    print("📊 Source columns: ['id', 'name', 'model', 'manufacturer', 'manufacturer_id', 'inactive', 'last_position_date']")
    print("📊 Available manufacturer_ids: ['SPOORTRACK-EARTAG-ST1249', 'VECTRONIC-GPS-COLLAR', 'LOTEK-GPS-COLLAR', 'AWT-GPS-COLLAR']")
    print("✅ Found 22 SpoorTrack sources (deployed)")
    print("")
    
    print("📊 Analyzing source: ST001-Twiga_Male_01...")
    print("📊 Analyzing source: ST002-Twiga_Female_03...")
    print("📊 Analyzing source: ST003-Twiga_Calf_07...")
    print("   ... (analyzing 22 sources)")
    print("")
    
    print("="*90)
    print("SPOORTRACK PERFORMANCE REPORT - LAST QUARTER (90 DAYS)")
    print("Giraffe Conservation Foundation")
    print("="*90)
    
    print("Report Generated: 2025-08-20 14:49:32")
    print("Analysis Period: 90 days")
    print("Total Sources Analyzed: 22")
    print("")
    
    # R-like data frame output
    print("Source Performance Data (n = 22):")
    print("")
    
    # Headers
    headers = "Source_Name              Source_ID    Total_Obs  Obs_Per_Day  Mean_Battery_V  Battery_Status  Location_Success_% Last_Transmission   "
    separator = "-" * len(headers)
    print(headers)
    print(separator)
    
    # Sample data rows in R-like format
    sample_data = [
        ("ST001-Twiga_Male_01    ", "12345       ", "2687      ", "29.9        ", "3.85V          ", "Good           ", "91.2%             ", "2025-08-20          "),
        ("ST002-Twiga_Female_03  ", "12346       ", "2278      ", "25.3        ", "3.72V          ", "Good           ", "88.7%             ", "2025-08-20          "),
        ("ST003-Twiga_Calf_07    ", "12347       ", "2156      ", "24.0        ", "3.68V          ", "Good           ", "85.4%             ", "2025-08-19          "),
        ("ST004-Twiga_Male_02    ", "12348       ", "2034      ", "22.6        ", "3.55V          ", "Good           ", "82.1%             ", "2025-08-20          "),
        ("ST005-Twiga_Female_01  ", "12349       ", "1923      ", "21.4        ", "3.49V          ", "Warning        ", "78.9%             ", "2025-08-19          "),
        ("ST006-Twiga_Juvenile_01", "12350       ", "1812      ", "20.1        ", "3.42V          ", "Warning        ", "75.3%             ", "2025-08-18          "),
        ("ST007-Twiga_Adult_03   ", "12351       ", "1701      ", "18.9        ", "3.38V          ", "Warning        ", "71.2%             ", "2025-08-17          "),
        ("ST008-Twiga_Female_04  ", "12352       ", "1589      ", "17.7        ", "3.33V          ", "Warning        ", "68.5%             ", "2025-08-16          "),
        ("ST009-Twiga_Male_03    ", "12353       ", "1456      ", "16.2        ", "3.28V          ", "Warning        ", "64.8%             ", "2025-08-15          "),
        ("ST010-Twiga_Calf_02    ", "12354       ", "1234      ", "13.7        ", "3.22V          ", "Critical       ", "58.2%             ", "2025-08-13          "),
        ("ST011-Twiga_Adult_01   ", "12355       ", "1123      ", "12.5        ", "3.18V          ", "Critical       ", "52.6%             ", "2025-08-11          "),
        ("ST012-Twiga_Female_02  ", "12356       ", "987       ", "11.0        ", "3.15V          ", "Critical       ", "47.3%             ", "2025-08-09          "),
        ("...                    ", "...         ", "...       ", "...         ", "...            ", "...            ", "...               ", "...                 ")
    ]
    
    for row in sample_data:
        print("".join(row))
    
    print("")
    print("[1] Data frame with 22 rows and 8 columns")
    print("[2] Analysis period: 90 days (Quarter: 2025 Q3)")
    print("[3] Generated: 2025-08-20 14:49:32")
    
    print("\n" + "="*90)
    print("SUMMARY STATISTICS")
    print("="*90)
    print("Total Observations: 46,230")
    print("Mean Observations/Day: 17.1")
    print("Mean Battery Voltage: 3.47V")
    print("Mean Location Success: 71.2%")
    print("")
    
    print("Battery Status Distribution:")
    print("  Good: 4 sources")
    print("  Warning: 5 sources")
    print("  Critical: 3 sources")
    print("  Unknown: 10 sources")
    
    print(f"\n📄 PDF report saved: spoortrack_performance_report_20250820_1449.pdf")
    print(f"\n✅ Report generation completed!")

if __name__ == "__main__":
    show_demo_output()
