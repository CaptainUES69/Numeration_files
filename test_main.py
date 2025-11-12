import csv
import os
import tempfile
import unittest
from unittest import mock

from main import (add_ending_to_files, clean_filename, group_by_operator,
                  range_of_numbers, read_data, upload_multiple_files_to_gitea)


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
            generator = read_data(temp_file, columns = [0, 1, 2, 3, 4, 5, 6, 7]) # Читаем все данные в строке
            data = list(generator)

            # assert
            # Сравниваем длину итоговых данных с тем что должно получиться
            self.assertEqual(len(data), len(lines) - 1, msg = f'Кол-во строк в итоговых данных неккоректно') # - 1 т.к. мы пропускаем заголовок

            # Поскольку в функции мы пропускаем заголовок, то сравниваем со сдвигом на 1 (пропускаем строку заголовка)
            self.assertEqual(data[0], lines[1], msg = f'Строки не совпадают') 
            self.assertEqual(data[1], lines[2], msg = f'Строки не совпадают') 
            self.assertEqual(data[2], lines[3], msg = f'Строки не совпадают')  

            # # Сравниваем итоговые данные с нужными нам (abc/ def, от, до, оператор, инн) 
            # self.assertEqual(data[0], [lines[1][i] for i in [0, 1, 2, 4, 7]], msg = f"Строки не совпадают") 
            # self.assertEqual(data[1], [lines[2][i] for i in [0, 1, 2, 4, 7]], msg = f"Строки не совпадают") 
            # self.assertEqual(data[2], [lines[3][i] for i in [0, 1, 2, 4, 7]], msg = f"Строки не совпадают")  

    def test_clean_filename(self):
        # arrange
        filename = 'I <Hate>: Wrong"/\\ Names|?*'
        # act
        data = clean_filename(filename)
        # assert
        self.assertEqual(data, 'I_Hate_Wrong_Names')

    def test_range_of_numbers(self):
        # arrange
        expected_static = [['_[78]9337704444', 'Оператор', '1234567890']]
        expected_range = [['_[78]933770400[0-2]', 'Оператор', '1234567890']]
        expected_many = [
            ['_[78]90034[0-4]XXXX', 'Оператор', '1234567890'],
            ['_[78]90033[6-9]XXXX', 'Оператор', '1234567890']
        ]

        # act
        one_static = range_of_numbers('933', '7704444', '7704444', 'Оператор', '1234567890')
        one_range = range_of_numbers('933', '7704000', '7704002', 'Оператор', '1234567890')
        many_range = range_of_numbers('900', '3360000', '3449999', 'Оператор', '1234567890')

        # assert
        self.assertEqual(expected_static, one_static, msg = f'Несовпадение статичного номера') # Одиночная строка
        self.assertEqual(expected_range, one_range, msg = f'Несовпадение среза') # Одиночный срез
        self.assertEqual(expected_many, many_range, msg = f'Несовпадение множества строк') # Несколько строк

    def test_group_by_operator(self):
        # arrange
        test_data = [
            ['_[78]9337704444', 'ООО "ТЕСТ 1"', '7740000076'],
            ['_[78]9337704343', 'ООО "ТЕСТ 2"', '7740000076'],
            ['_[78]9337704XXX', 'ООО "ТЕСТ 2"', '7740000076'],
            ['_[78]93377[6-7]XXXX', 'ООО "ТЕСТ 3"', '7713076301'],
            ['_[78]933820555', 'ООО "ТЕСТ 3"', '7713076301']
        ]
    
        expected = ['_[78]93377[6-7]XXXX', '_[78]933820555']

        # act
        with tempfile.TemporaryDirectory() as temp_dir:
            for data in test_data:
                group_by_operator(data, temp_dir)
            
            content: str
            files = os.listdir(temp_dir)

            with open(os.path.join(temp_dir, 'beeline_codes.conf'), 'r') as f:
                content = f.read()
                for i in expected:
                    self.assertIn(i, content)

            # assert
            self.assertEqual(len(files), 2)
            self.assertEqual(['beeline_codes.conf', 'mts_codes.conf'], files, msg = f"Названия файлов не соответствуют нужным")

    def test_add_ending_to_files(self):
        # arrange
        with tempfile.TemporaryDirectory() as temp_dir:
            # Создаем тестовые файлы
            test_files = [
                'mts_codes.conf',
                'beeline_codes.conf', 
                'megafon_codes.conf'
            ]
            
            for filename in test_files:
                filepath = os.path.join(temp_dir, filename)
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write('[_codes]\n')
                    f.write('exten = _[78]9123456789,1,GoSub(${ARG1},${EXTEN},1)\n')
            
            # act
            add_ending_to_files(temp_dir)
            
            # assert
            for filename in test_files:
                filepath = os.path.join(temp_dir, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Проверяем что добавились нужные строки в конец
                    self.assertIn('exten = _XXXX!,1,Return()', content)
                    self.assertIn('exten = _XXXX!,2,Hangup()', content)
                    # Проверяем что оригинальное содержимое осталось
                    self.assertIn('exten = _[78]9123456789,1,GoSub(${ARG1},${EXTEN},1)', content)

    def test_upload_multiple_files_to_gitea(self):
        # arrange
        with tempfile.TemporaryDirectory() as temp_dir:
            # Создаем тестовые файлы в директории operators
            operators_dir = os.path.join(temp_dir, 'operators')
            os.makedirs(operators_dir)
            
            test_files = {
                'mts_codes.conf': '[_codes]\nexten = _[78]9123456789,1,GoSub(${ARG1},${EXTEN},1)\n',
                'beeline_codes.conf': '[_codes]\nexten = _[78]9151234567,1,GoSub(${ARG1},${EXTEN},1)\n'
            }
            
            for filename, content in test_files.items():
                filepath = os.path.join(operators_dir, filename)
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
            
            # Мокаем requests для тестирования без реального API
            with mock.patch('main.requests') as mock_requests:
                # Настраиваем мок для проверки существования файлов (возвращаем 404 - файлы не существуют)
                mock_response_check = mock.Mock()
                mock_response_check.status_code = 404
                mock_requests.get.return_value = mock_response_check
                
                # Настраиваем мок для успешной загрузки
                mock_response_upload = mock.Mock()
                mock_response_upload.status_code = 201
                mock_requests.post.return_value = mock_response_upload
                
                # act
                with mock.patch('main.os.listdir') as mock_listdir:
                    mock_listdir.return_value = list(test_files.keys())
                    
                    # Вызываем функцию с тестовыми параметрами
                    upload_multiple_files_to_gitea(
                        gitea_url='https://test-gitea.com',
                        token='test_token',
                        owner='test_owner',
                        repo='test_repo',
                        branch='main'
                    )
                
                # assert
                # Проверяем что был вызов POST для загрузки файлов
                self.assertTrue(mock_requests.post.called)
                
                # Проверяем что был вызов GET для проверки существования файлов
                self.assertEqual(mock_requests.get.call_count, len(test_files))
                
                # Получаем аргументы вызова POST
                call_args = mock_requests.post.call_args
                request_data = call_args[1]['json']  # данные в формате JSON
                
                # Проверяем структуру данных
                self.assertIn('files', request_data)
                self.assertEqual(len(request_data['files']), len(test_files))
                self.assertIn('message', request_data)
                self.assertIn('branch', request_data)
                
                # Проверяем что все файлы присутствуют в запросе
                uploaded_filenames = [file_data['path'] for file_data in request_data['files']]
                for filename in test_files.keys():
                    self.assertIn(filename, uploaded_filenames)
