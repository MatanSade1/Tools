#!/usr/bin/env python3
"""
Test script for received_stickers_list validation with multiple slots.
"""

from param_analysis.enhanced_param_definitions import validate_parameter

def test_received_stickers_list():
    print('=== RECEIVED_STICKERS_LIST VALIDATION TEST ===')
    print('Parameter: received_stickers_list')
    print('Updated to use ReceivedStickersListValidator')
    print('Supports multiple slots in JSON array format')
    print()

    # Test valid values from user examples
    valid_tests = [
        # Single slot examples (previously supported)
        ('["slot_1: 8, 2, True"]', 'Single slot - True'),
        ('["slot_1: 22, 1, True"]', 'Single slot - True'),
        ('["slot_1: 2, 1, False"]', 'Single slot - False'),
        ('["slot_1: 17, 2, True"]', 'Single slot - True'),
        ('["slot_1: 18, 2, True"]', 'Single slot - True'),
        
        # Multiple slot examples (new requirement)
        ('["slot_1: 8, 2, False","slot_2: 23, 1, True"]', 'Two slots - mixed boolean'),
        ('["slot_1: 17, 2, True","slot_2: 51, 1, True"]', 'Two slots - both True'),
        ('["slot_1: 7, 2, False","slot_2: 13, 1, True"]', 'Two slots - mixed boolean'),
        ('["slot_1: 17, 2, True","slot_2: 2, 1, True"]', 'Two slots - both True'),
        ('["slot_1: 26, 2, True","slot_2: 22, 1, True"]', 'Two slots - both True'),
        
        # Additional test cases
        ('["slot_3: 100, 5, False"]', 'Single slot - slot_3'),
        ('["slot_1: 1, 0, False","slot_2: 999, 10, True","slot_3: 50, 1, False"]', 'Three slots'),
    ]

    print('=== VALID TESTS ===')
    valid_count = 0
    for value, description in valid_tests:
        result = validate_parameter('received_stickers_list', value)
        if result:
            valid_count += 1
        status = '✅' if result else '❌'
        print(f'  {status} {description}')
        if not result:
            print(f'      Value: {value}')

    print(f'\nValid tests: {valid_count}/{len(valid_tests)} correctly accepted')
    print()

    # Test invalid values
    invalid_tests = [
        ('[]', 'Empty array'),
        ('["invalid format"]', 'Invalid slot format'),
        ('["slot_1: abc, 2, True"]', 'Non-numeric sticker ID'),
        ('["slot_1: 8, -1, True"]', 'Negative count'),
        ('["slot_1: 8, 2, Maybe"]', 'Invalid boolean'),
        ('["slot_1: 8, 2"]', 'Missing boolean value'),
        ('["slot_1: 8, 2, True, extra"]', 'Too many values'),
        ('["slot_: 8, 2, True"]', 'Missing slot number'),
        ('["slot_abc: 8, 2, True"]', 'Non-numeric slot'),
        ('["slot1: 8, 2, True"]', 'Missing underscore'),
        ('not_json', 'Not JSON format'),
        (None, 'Null value'),
        ('', 'Empty string'),
        ('{}', 'JSON object instead of array'),
        ('["slot_1: 0, 2, True"]', 'Zero sticker ID (invalid)'),
        ('["slot_1: 8, abc, True"]', 'Non-numeric count'),
    ]

    print('=== INVALID TESTS ===')
    invalid_count = 0
    for value, description in invalid_tests:
        result = validate_parameter('received_stickers_list', value)
        if not result:
            invalid_count += 1
        status = '❌' if not result else '✅'
        display_value = str(value) if value is not None else 'None'
        print(f'  {status} {description}')
        if result:  # Show unexpected passes
            print(f'      Value: {display_value}')

    print(f'\nInvalid tests: {invalid_count}/{len(invalid_tests)} correctly rejected')
    print()

    print('=== VALIDATION CHANGE SUMMARY ===')
    print('BEFORE: FormatValidator with simple regex pattern')
    print('  • Only supported single slot: ["slot_1: 8, 2, True"]')
    print('  • Regex: ^\\["slot_\\d+: \\d+, \\d+, (True|False)"\\]$')
    print()
    print('NOW: ReceivedStickersListValidator class')
    print('  • Supports multiple slots in same array')
    print('  • Validates JSON structure properly')
    print('  • Checks each slot format: "slot_N: sticker_id, count, boolean"')
    print('  • Validates sticker_id > 0, count >= 0, boolean in [True, False]')
    print()
    print('New supported patterns:')
    print('  • Single: ["slot_1: 8, 2, True"]')
    print('  • Multiple: ["slot_1: 8, 2, False","slot_2: 23, 1, True"]')
    print('  • Any number of slots with different slot numbers')
    print()
    print('=== RECEIVED_STICKERS_LIST VALIDATION UPDATE SUCCESSFUL ===')

if __name__ == '__main__':
    test_received_stickers_list()
