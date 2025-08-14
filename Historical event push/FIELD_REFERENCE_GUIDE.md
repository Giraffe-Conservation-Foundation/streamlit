# 📋 Genetic Dashboard CSV Field Reference Guide

## CSV Format Matching Genetic Dashboard Output Table

Your CSV file should use the **exact column names** from the genetic dashboard output table to ensure perfect compatibility:

### Required Fields
- **serial_number**: Sequential number for the event (1, 2, 3, etc.)
- **event_datetime**: Date and time of sample collection (YYYY-MM-DD HH:MM:SS)

### Core Location and Sample Information
- **details_girsam_iso**: 3-letter ISO country code (NAM, ZAF, BWA, ZWE, TZA, KEN, UGA, etc.)
- **details_girsam_site**: Collection site/location name
- **details_girsam_origin**: Sample origin (Wild, Captive, Semi-captive, Translocation, Unknown)
- **latitude**: Decimal degrees latitude (-90 to 90)
- **longitude**: Decimal degrees longitude (-180 to 180)

### Animal Information
- **details_girsam_age**: Age classification (Calf, Juvenile, Sub-adult, Adult, Elderly, Unknown)
- **details_girsam_sex**: Sex of animal (Male, Female, Unknown)

### Sample Details
- **details_girsam_type**: Type of biological sample (blood, tissue, hair, serum, plasma, saliva, feces, urine, skin)
- **details_girsam_smpid**: Primary sample identifier
- **details_girsam_subid**: Subject/individual identifier  
- **details_girsam_status**: Processing status (Collected, Processing, Analyzed, Shipped, Stored, Ready, etc.)
- **details_girsam_species**: Giraffe species/subspecies
- **details_girsam_notes**: Additional descriptive notes
- **details_girsam_smpid2**: Secondary/alternative sample identifier

## Field Value Examples

### Country Codes (details_girsam_iso)
- NAM (Namibia)
- ZAF (South Africa) 
- BWA (Botswana)
- ZWE (Zimbabwe)
- TZA (Tanzania)
- KEN (Kenya)
- UGA (Uganda)

### Site Names (details_girsam_site)
- Etosha National Park
- Kruger National Park
- Okavango Delta
- Hwange National Park
- Caprivi Strip
- Serengeti National Park
- Masai Mara
- Murchison Falls

### Species Names (details_girsam_species)
- Giraffa giraffa (Southern giraffe)
- Giraffa camelopardalis (Northern giraffe)
- Giraffa tippelskirchi (Masai giraffe)
- Giraffa reticulata (Reticulated giraffe)

### Sample Types (details_girsam_type)
- blood
- tissue
- hair
- serum
- plasma
- saliva
- feces
- urine
- skin

### Age Categories (details_girsam_age)
- Calf
- Juvenile
- Sub-adult
- Adult
- Elderly
- Unknown

### Origins (details_girsam_origin)
- Wild
- Captive
- Semi-captive
- Translocation
- Unknown

### Processing Status (details_girsam_status)
- Collected
- Processing
- Analyzed
- Shipped
- Stored
- Ready
- Pending

## Example CSV Row
```csv
serial_number,event_datetime,details_girsam_iso,details_girsam_site,details_girsam_origin,latitude,longitude,details_girsam_age,details_girsam_sex,details_girsam_type,details_girsam_smpid,details_girsam_subid,details_girsam_status,details_girsam_species,details_girsam_notes,details_girsam_smpid2
1,2024-01-15 10:30:00,NAM,Etosha National Park,Wild,-15.123456,28.456789,Adult,Female,blood,SAMP001,G001_NAM_2024,Collected,Giraffa giraffa,Healthy adult female with calf nearby,SAMP001_ALT
```

## Field Validation Notes

1. **Date Format**: Must be in YYYY-MM-DD HH:MM:SS format
2. **Coordinates**: Use decimal degrees, negative for South/West
3. **Text Fields**: Keep consistent spelling and formatting
4. **IDs**: Use consistent naming convention for sample and subject IDs
5. **Status Values**: Use standardized status terms from the examples above

## Compatibility with Genetic Dashboard

Using these exact column names ensures that:
- ✅ **Perfect Integration**: Events appear exactly as shown in genetic dashboard table
- ✅ **Filter Compatibility**: All filters (Country, Site, Sample Type, Species) work correctly
- ✅ **Display Consistency**: Column headers match dashboard output
- ✅ **Data Accuracy**: No field mapping issues or data loss

This format guarantees that your uploaded historical events will display identically to events already in the genetic dashboard.
