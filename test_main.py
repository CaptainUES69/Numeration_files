import csv
import os
import tempfile
import unittest
from unittest import mock

from cfg import PatternLine, RowData
from main import (
    grouping_lines, 
    range_of_numbers, 
    read_csv_file,
    write_operator_config
)


class TestMain(unittest.TestCase): 
    def test_read_data(self):
        # arrange
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_file = os.path.join(temp_dir, 'test.csv')
            with open(temp_file, 'w', encoding='utf-8', newline='') as f:
                lines = [
                    ['ABC/ DEF', 'От', 'До', 'Емкость', 'Оператор', 'Регион', 'Территория', 'ИНН'],
                    ['933', '1630000', '1649999', '20000', 'ООО "Т2 МОБАЙЛ"', 'Алтайский край', 'Алтайский край', '7743895280'],
                    ['906', '9600000', '9699999', '100000', 'ПАО "ВЫМПЕЛКОМ"', 'Алтайский край', 'Алтайский край', '7713076301'],
                    ['923', '5680000', '5699999', '20000', 'ПАО "МЕГАФОН"', 'Алтайский край', 'Алтайский край', '7812014560']
                ]

                writer = csv.writer(f, delimiter = ';')
                writer.writerows(lines)

            # act
            generator = read_csv_file(temp_file, columns = [0, 1, 2, 3, 4, 5, 6, 7]) # Читаем все данные в строке
            data = list(generator)

            # assert
            # Сравниваем длину итоговых данных с тем что должно получиться
            self.assertEqual(len(data), len(lines) - 1, msg = f'Кол-во строк в итоговых данных неккоректно') # - 1 т.к. мы пропускаем заголовок

            # Поскольку в функции мы пропускаем заголовок, то сравниваем со сдвигом на 1 (пропускаем строку заголовка)
            self.assertEqual(data[0], lines[1], msg = f'Строки не совпадают') 
            self.assertEqual(data[1], lines[2], msg = f'Строки не совпадают') 
            self.assertEqual(data[2], lines[3], msg = f'Строки не совпадают')  

    
    def test_range_of_numbers_single(self):
        row_data = RowData('933', '7704444', '7704444', 'Test Operator', '1234567890')
        
        result = range_of_numbers(row_data)
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].pattern, '_[78]9337704444')
        self.assertEqual(result[0].operator_name, 'Test Operator')
        self.assertEqual(result[0].inn, '1234567890')
    

    def test_range_of_numbers_range(self):
        row_data = RowData('933', '7704000', '7704002', 'Test Operator', '1234567890')
        
        result = range_of_numbers(row_data)
        
        self.assertEqual(len(result), 1)
        # Проверяем что паттерн содержит нужные элементы
        self.assertIn('933770400', result[0].pattern)
    

    def test_range_of_numbers_complex_range(self):
        row_data = RowData('900', '3360000', '3449999', 'Test Operator', '1234567890')
        
        result = range_of_numbers(row_data)
        
        self.assertGreater(len(result), 0)
        for pattern_line in result:
            self.assertTrue(pattern_line.pattern.startswith('_[78]900'))
    

    def test_grouping_lines(self):
        test_data = [
            PatternLine('_[78]9337704444', 'МТС', '7713076301'),
            PatternLine('_[78]9337704343', 'МТС', '7713076301'),
            PatternLine('_[78]9337704XXX', 'Билайн', '7740000076'),
            PatternLine('_[78]93377[6-7]XXXX', 'Билайн', '7740000076'),
        ]
        
        # Мокаем get_operator_to_inn
        with mock.patch('main.get_operator_to_inn') as mock_get_operator:
            mock_get_operator.side_effect = lambda inn: {
                '7713076301': 'mts',
                '7740000076': 'beeline'
            }.get(inn)
            
            result = grouping_lines(test_data)
            
            self.assertEqual(len(result), 2)
            self.assertIn('mts', result)
            self.assertIn('beeline', result)
            self.assertEqual(len(result['mts']), 2)
            self.assertEqual(len(result['beeline']), 2)
    

    def test_write_operator_config(self):
        test_data = {
            'mts': ['_[78]9337704444', '_[78]9337704343'],
            'beeline': ['_[78]9337704XXX', '_[78]93377[6-7]XXXX']
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch('main.OUTPUT_DIR_NAME', temp_dir):
                write_operator_config(test_data)
                
                files = os.listdir(temp_dir)
                self.assertEqual(len(files), 2)
                self.assertIn('mts_conf.cfg', files)
                self.assertIn('beeline_conf.cfg', files)
                
                # Проверяем что файлы созданы и не пустые
                with open(os.path.join(temp_dir, 'mts_conf.cfg'), 'r', encoding='utf-8-sig') as f:
                    content = f.read()
                    self.assertIn('[mts_codes]', content)
                    self.assertIn('_[78]9337704444', content)
    