# GAEB Format Documentation

## Overview
GAEB (Gemeinsamer Ausschuss Elektronik im Bauwesen) is the German standard for electronic data exchange in construction. This document describes all supported GAEB format variations.

## Format Types

### 1. D-Format (Text-Based)
**Extensions:** `.d81`, `.d82`, `.d83`, `.d84`, `.d85`, `.d86`, `.d90`

**Encoding:** ISO-8859-1 (Latin-1)

**Structure:** Fixed-width text format with record types

**Record Types:**
- **Numeric Records:**
  - `52`, `53`, `54`, `55`, `DP`: Position records (item descriptions)
  - `56`, `57`, `TX`: Text continuation
  - `60`, `61`, `QT`: Quantity records
  - `62`, `63`, `PR`: Price records

- **T-Records (Modern variant used in DA83+):**
  - `T0`: Header/Section markers
  - `T1`: Item descriptions (position numbers and text)
  - `T2`: Quantity and unit information
  - `T3`: Price information

**Example D83 Structure:**
```
T0Abschnitt 01 - Baustelleneinrichtung
T10010    Einrichten und Räumen der Baustelle
T2        4.000 St
T3        125.00 EUR
```

### 2. X-Format (XML-Based)
**Extensions:** `.x81`, `.x82`, `.x83`, `.x84`, `.x85`, `.x86`, `.x90`

**Encoding:** UTF-8

**Structure:** XML files with namespaced elements

**XML Schema Variations:**

#### DA83/3.3 (Common in X83 files)
```xml
<GAEB xmlns="http://www.gaeb.de/GAEB_DA_XML/DA83/3.3">
  <GAEBInfo>
    <Version>3.3</Version>
  </GAEBInfo>
  <Award>
    <BoQ>
      <BoQInfo>...</BoQInfo>
      <BoQBody>
        <BoQCtgy ID="..." RNoPart="01">
          <LblTx>Section Title</LblTx>
          <BoQBody>
            <Itemlist>
              <Item ID="..." RNoPart="0010">
                <Qty>4.000</Qty>
                <QU>St</QU>
                <Description>
                  <CompleteText>
                    <OutlineText>
                      <OutlTxt>
                        <TextOutlTxt>Short description</TextOutlTxt>
                      </OutlTxt>
                    </OutlineText>
                    <DetailTxt>
                      <Text>
                        <p>Detailed description</p>
                      </Text>
                    </DetailTxt>
                  </CompleteText>
                </Description>
              </Item>
            </Itemlist>
          </BoQBody>
        </BoQCtgy>
      </BoQBody>
    </BoQ>
  </Award>
</GAEB>
```

#### DA84/3.2 (Simplified structure)
```xml
<GAEB xmlns="http://www.gaeb.de/GAEB_DA_XML/DA84/3.2">
  <Award>
    <BoQ>
      <BoQBody>
        <Itemlist>
          <Item RNoPart="0010">
            <Qty>4.000</Qty>
            <QU>St</QU>
            <Description>...</Description>
          </Item>
        </Itemlist>
      </BoQBody>
    </BoQ>
  </Award>
</GAEB>
```

#### DA90 (May use alternative element names)
- Elements: `Position`, `BoQItem`, or `Item`
- May have different namespace URIs

**Key Elements:**
- `<Item>` or `<Position>`: Individual line items
- `RNoPart`: Position number (attribute)
- `<Qty>`: Quantity
- `<QU>`: Unit (e.g., "St", "m", "m²")
- `<Description>`: Item description (may have nested structure)
- `<OutlineText>`: Short description
- `<DetailTxt>`: Detailed description

### 3. P-Format (Price Format)
**Extensions:** `.p81`, `.p82`, `.p83`, `.p84`, `.p85`, `.p86`, `.p90`

**Encoding:** ISO-8859-1 (Latin-1)

**Structure:** Similar to D-format but includes detailed pricing information

**Features:**
- Contains unit prices
- May include total prices
- Price breakdown information
- Similar record types to D-format

## Version History

| Version | Year | Description |
|---------|------|-------------|
| DA81 | 1981 | Original GAEB format |
| DA83 | 1983 | Extended format with T-records, XML support |
| DA84 | 1984 | Enhanced XML structure |
| DA85 | 1985 | Additional features |
| DA86 | 1986 | Improved data exchange capabilities |
| DA90 | 1990 | Current standard with full XML support |

## Parser Implementation

### Detection Strategy
1. Check file extension (`.d*`, `.x*`, `.p*`)
2. For X-format: Parse XML and extract namespace
3. For D/P-format: Read with ISO-8859-1 encoding and detect record types

### Extraction Strategy

#### X-Format
1. Parse XML with ElementTree
2. Extract namespace from root element
3. Search for `<Item>` elements using recursive search (`.//Item`)
4. Extract:
   - Position number from `RNoPart` attribute or `<ID>` element
   - Description from `<OutlineText>` or `<DetailTxt>`
   - Quantity from `<Qty>` (direct child)
   - Unit from `<QU>` (direct child)
   - Price from `<UP>` or `<Price>` (if available)

#### D-Format & P-Format
1. Read file with ISO-8859-1 encoding
2. Identify record types (T0, T1, T2, T3 or numeric codes)
3. For T-records:
   - T0: Section headers
   - T1: Position numbers and descriptions
   - T2: Quantities and units
   - T3: Prices
4. For numeric records:
   - 52-55: Position data
   - 60-61: Quantities
   - 62-63: Prices
5. Accumulate multi-line descriptions
6. Associate quantities/units/prices with positions

## Common Pitfalls

### X-Format
- **Single-line XML:** Many X-format files have the entire XML on one line
- **Namespace handling:** Always extract and use the namespace for XPath queries
- **Nested descriptions:** Descriptions may be deeply nested (OutlineText > OutlTxt > TextOutlTxt)
- **Mixed content:** Text may contain HTML-like tags (`<p>`, `<span>`) that need to be stripped

### D-Format
- **Character encoding:** Must use ISO-8859-1, not UTF-8
- **Record type variations:** Files may use T-records, numeric codes, or both
- **Fixed-width fields:** Position data may be in specific column ranges
- **Multi-line descriptions:** Descriptions span multiple T1 or continuation records

### P-Format
- **Price precision:** Prices may use comma as decimal separator
- **Currency symbols:** May include "EUR", "€", or other currency codes

## Testing Strategy

1. **Format Detection:** Verify correct format is detected from extension
2. **Encoding:** Ensure ISO-8859-1 is used for D/P formats
3. **Record Parsing:** Test with files containing all record types
4. **Multi-line Handling:** Verify descriptions spanning multiple lines
5. **Namespace Handling:** Test XML files with different namespace versions
6. **Edge Cases:** Empty fields, missing quantities, unusual characters

## Future Enhancements

1. **GAEB DA91+:** Support for newer GAEB versions if released
2. **Validation:** Verify data integrity and completeness
3. **Export:** Generate GAEB files from internal data
4. **Error Recovery:** Better handling of malformed files
5. **Performance:** Optimize for large files (10,000+ positions)

## References

- GAEB Official Documentation: https://www.gaeb.de/
- GAEB XML Schema: http://www.gaeb.de/GAEB_DA_XML/
- ISO-8859-1 Encoding: Latin-1 character set for German text
