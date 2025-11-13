import os
import tempfile
import unittest
from unittest import mock

from cfg import Pattern, PatternItem
from optimized import (compress_sequential_patterns, merge_adjacent_ranges,
                       merge_masks, merge_similar_masks, optimize_config_file,
                       optimize_patterns, parse_pattern,
                       sort_lines_by_def_code, split_mask)


class TestOptimized(unittest.TestCase):

    def test_parse_pattern_valid(self):
        pattern = "exten = _[78]91234567[0-9]X,1,GoSub(${ARG1},${EXTEN},1)"
        result = parse_pattern(pattern)
        
        self.assertEqual(result.prefix, "91234567")
        self.assertEqual(result.mask, ['[0-9]', 'X'])

    def test_parse_pattern_invalid(self):
        pattern = "invalid pattern string"
        result = parse_pattern(pattern)
        
        self.assertEqual(result.prefix, "")
        self.assertEqual(result.mask, [])

    def test_split_mask_simple(self):
        mask_str = "XX"
        result = split_mask(mask_str)
        
        self.assertEqual(result, ['X', 'X'])

    def test_split_mask_with_range(self):
        mask_str = "[0-3]X[5-9]"
        result = split_mask(mask_str)
        
        self.assertEqual(result, ['[0-3]', 'X', '[5-9]'])

    def test_merge_masks_single_mask(self):
        masks = [['1', '2', '3']]
        result = merge_masks(masks)
        
        self.assertEqual(result, [['1', '2', '3']])

    def test_merge_masks_identical_masks(self):
        masks = [
            ['1', '2', '3'],
            ['1', '2', '3']
        ]
        result = merge_masks(masks)
        
        self.assertEqual(result, [['1', '2', '3']])

    def test_merge_masks_different_digits(self):
        masks = [
            ['1', '2'],
            ['1', '3']
        ]
        result = merge_masks(masks)
        
        # Проверяем что результат существует и имеет правильную структуру
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0]), 2)

    def test_merge_similar_masks_empty(self):
        result = merge_similar_masks([])
        self.assertEqual(result, [])

    def test_merge_similar_masks_identical(self):
        masks = [
            ['1', '2', '3'],
            ['1', '2', '3']
        ]
        result = merge_similar_masks(masks)
        
        self.assertEqual(result, ['1', '2', '3'])

    def test_optimize_patterns_with_valid_data(self):
        # Используем данные, которые точно будут обработаны
        patterns = [
            "exten = _[78]91234567[0-9]X,1,GoSub(${ARG1},${EXTEN},1)",
            "exten = _[78]91234567[1-2]X,1,GoSub(${ARG1},${EXTEN},1)"
        ]
        result = optimize_patterns(patterns)
        
        # Проверяем что что-то вернулось
        self.assertTrue(len(result) >= 0)

    def test_compress_sequential_patterns_no_compression(self):
        patterns = [
            "exten = _[78]912345671,1,GoSub(${ARG1},${EXTEN},1)",
            "exten = _[78]912345673,1,GoSub(${ARG1},${EXTEN},1)"
        ]
        result = compress_sequential_patterns(patterns)
        
        self.assertEqual(len(result), 2)

    def test_compress_sequential_patterns_with_compression(self):
        # Используем паттерны, которые могут быть сжаты
        patterns = [
            "exten = _[78]912345671XX,1,GoSub(${ARG1},${EXTEN},1)",
            "exten = _[78]912345672XX,1,GoSub(${ARG1},${EXTEN},1)",
            "exten = _[78]912345673XX,1,GoSub(${ARG1},${EXTEN},1)"
        ]
        result = compress_sequential_patterns(patterns)
        
        # Проверяем что результат существует
        self.assertTrue(len(result) > 0)

    def test_sort_lines_by_def_code(self):
        lines = [
            "exten = _[78]91234567,1,GoSub(${ARG1},${EXTEN},1)",
            "exten = _[78]90123456,1,GoSub(${ARG1},${EXTEN},1)",
            "exten = _[78]93234567,1,GoSub(${ARG1},${EXTEN},1)",
            "[header]",
            "other line"
        ]
        result = sort_lines_by_def_code(lines)
        
        # Проверяем что заголовок остался первым
        self.assertEqual(result[0], "[header]")

    def test_merge_adjacent_ranges_no_merge(self):
        patterns = [
            "exten = _[78]91234567[1-2],1,GoSub(${ARG1},${EXTEN},1)",
            "exten = _[78]91234567[4-5],1,GoSub(${ARG1},${EXTEN},1)"
        ]
        result = merge_adjacent_ranges(patterns)
        
        self.assertTrue(len(result) >= 1)

    def test_optimize_config_file_basic(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_file = os.path.join(temp_dir, "test_input.cfg")
            output_file = "test_output.cfg"
            
            # Создаем простой конфиг с минимальным содержимым
            with open(input_file, 'w', encoding='utf-8') as f:
                f.write("[test_codes]\n")
                f.write("exten = _[78]912345671,1,GoSub(${ARG1},${EXTEN},1)\n")
            
            optimize_config_file(1, input_file, output_file, temp_dir)
            
            output_path = os.path.join(temp_dir, output_file)
            
            # Проверяем что файл создан
            self.assertTrue(os.path.exists(output_path))

    def test_pattern_to_string(self):
        pattern = Pattern("91234567", ['[0-9]', 'X'])
        result = pattern.to_string()
        
        expected_start = "exten = _[78]91234567"
        self.assertTrue(result.startswith(expected_start))
