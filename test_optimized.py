import unittest

from optimized import (
    compress_sequential_patterns, 
    merge_adjacent_ranges,
    merge_masks, 
    merge_similar_masks, 
    parse_pattern,
    sort_lines_by_def_code, split_mask
)


class TestOptimized(unittest.TestCase):
    def test_parse_pattern(self):
        # arrange
        pattern = "exten = _[78]91234567[0-9]X,1,GoSub"
        
        # act
        result = parse_pattern(pattern)
        
        # assert
        self.assertEqual(result.prefix, "91234567")
        self.assertEqual(result.mask, ['[0-9]', 'X'])


    def test_parse_pattern_invalid(self):
        # arrange
        pattern = "invalid pattern string"
        
        # act
        result = parse_pattern(pattern)
        
        # assert
        self.assertEqual(result.prefix, "")
        self.assertEqual(result.mask, [])


    def test_split_mask_simple(self):
        # arrange
        mask_str = "XX"
        
        # act
        result = split_mask(mask_str)
        
        # assert
        self.assertEqual(result, ['X', 'X'])


    def test_split_mask_with_range(self):
        # arrange
        mask_str = "[0-9]X"
        
        # act
        result = split_mask(mask_str)
        
        # assert
        self.assertEqual(result, ['[0-9]', 'X'])


    def test_split_mask_complex(self):
        # arrange
        mask_str = "[0-9]X[1-3]"
        
        # act
        result = split_mask(mask_str)
        
        # assert
        self.assertEqual(result, ['[0-9]', 'X', '[1-3]'])


    def test_merge_masks_single(self):
        # arrange
        masks = [['1', '2']]
        
        # act
        result = merge_masks(masks)
        
        # assert
        self.assertEqual(result, [['1', '2']])


    def test_merge_masks_multiple(self):
        # arrange
        masks = [['1', '2'], ['1', '3']]
        
        # act
        result = merge_masks(masks)
        
        # assert
        self.assertEqual(result, [['1', '[2-3]']])


    def test_merge_masks_with_x(self):
        # arrange
        masks = [['X', '2'], ['X', '3']]
        
        # act
        result = merge_masks(masks)
        
        # assert
        self.assertEqual(len(result), 1)


    def test_merge_similar_masks_empty(self):
        # arrange
        masks = []
        
        # act
        result = merge_similar_masks(masks)
        
        # assert
        self.assertEqual(result, [])


    def test_merge_similar_masks_single(self):
        # arrange
        masks = [['1', '2', '3']]
        
        # act
        result = merge_similar_masks(masks)
        
        # assert
        self.assertEqual(result, ['1', '2', '3'])


    def test_merge_similar_masks_different(self):
        # arrange
        masks = [['1', '2', '3'], ['1', '5', '3']]
        
        # act
        result = merge_similar_masks(masks)
        
        # assert
        self.assertEqual(result, ['1', 'X', '3'])


    def test_compress_sequential_patterns_empty(self):
        # arrange
        patterns = []
        
        # act
        result = compress_sequential_patterns(patterns)
        
        # assert
        self.assertEqual(result, [])


    def test_compress_sequential_patterns_single(self):
        # arrange
        patterns = ["exten = _[78]123XX,1,GoSub"]
        
        # act
        result = compress_sequential_patterns(patterns)
        
        # assert
        self.assertEqual(result, patterns)


    def test_compress_sequential_patterns_sequential(self):
        # arrange
        patterns = [
            "exten = _[78]1234XX,1,GoSub",
            "exten = _[78]1235XX,1,GoSub",
            "exten = _[78]1236XX,1,GoSub"
        ]
        
        # act
        result = compress_sequential_patterns(patterns)
        
        # assert
        self.assertEqual(len(result), 1)


    def test_sort_lines_by_def_code(self):
        # arrange
        lines = [
            "exten = _[78]999XXX,1,GoSub",
            "exten = _[78]111XXX,1,GoSub",
            "exten = _[78]555XXX,1,GoSub"
        ]
        
        # act
        result = sort_lines_by_def_code(lines)
        
        # assert
        self.assertEqual(result[0], "exten = _[78]111XXX,1,GoSub")
        self.assertEqual(result[1], "exten = _[78]555XXX,1,GoSub")
        self.assertEqual(result[2], "exten = _[78]999XXX,1,GoSub")


    def test_sort_lines_with_headers(self):
        # arrange
        lines = [
            "[context1]",
            "exten = _[78]999XXX,1,GoSub",
            "exten = _[78]111XXX,1,GoSub",
            "other line"
        ]
        
        # act
        result = sort_lines_by_def_code(lines)
        
        # assert
        self.assertEqual(result[0], "[context1]")
        self.assertEqual(result[1], "exten = _[78]111XXX,1,GoSub")
        self.assertEqual(result[2], "exten = _[78]999XXX,1,GoSub")
        self.assertEqual(result[3], "other line")


    def test_merge_adjacent_ranges_empty(self):
        # arrange
        patterns = []
        
        # act
        result = merge_adjacent_ranges(patterns)
        
        # assert
        self.assertEqual(result, [])


    def test_merge_adjacent_ranges_single(self):
        # arrange
        patterns = ["exten = _[78]123[1-3]X,1,GoSub"]
        
        # act
        result = merge_adjacent_ranges(patterns)
        
        # assert
        self.assertEqual(result, patterns)


    def test_merge_adjacent_ranges_mergeable(self):
        # arrange
        patterns = [
            "exten = _[78]123[1-2]X,1,GoSub",
            "exten = _[78]123[3-4]X,1,GoSub"
        ]
        
        # act
        result = merge_adjacent_ranges(patterns)
        
        # assert
        self.assertEqual(len(result), 1)
