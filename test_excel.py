#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

from app import check_excel_structure, extract_positions_from_structured_excel

print('Testing structure detection...')
result = check_excel_structure('Data/2022-02_Leistungsverzeichnis_20251209.xlsx')
print(f'Structure detected: {result}')

if result:
    print('\nTesting extraction...')
    positions = extract_positions_from_structured_excel('Data/2022-02_Leistungsverzeichnis_20251209.xlsx')
    print(f'\nTotal extracted: {len(positions)} positions')

    if len(positions) > 0:
        print(f'\nFirst 5 positions:')
        for i, p in enumerate(positions[:5]):
            print(f"{i+1}. {p.get('ordnungszahl', 'N/A')}: {p.get('kurztext', 'N/A')[:60]}")
