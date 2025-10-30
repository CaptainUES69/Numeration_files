import unittest
import tempfile, os, csv
from main import read_data, clean_filename, range_of_numbers, group_by_operator


class test_main(unittest.TestCase):
    
    def test_read_data(self):
        # arrange
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_file = os.path.join(temp_dir, "test.csv")
            with open(temp_file, 'w', encoding='utf-8', newline='') as f:
                lines = [
                    ['ABC/ DEF', 'От', 'До', 'Емкость', 'Оператор', 'Регион', 'Территория', 'ИНН'],
                    ['933', '1630000', '1649999', '20000', 'ООО "Т2 МОБАЙЛ"', 'Алтайский край', 'Алтайский край', '7743895280'],
                    ['906', '9600000', '9699999', '100000', 'ПАО "ВЫМПЕЛКОМ"', 'Алтайский край', 'Алтайский край', '7713076301'],
                    ['923', '5680000', '5699999', '20000', 'ПАО "МЕГАФОН"', 'Алтайский край', 'Алтайский край', '7812014560']
                ]

                writer = csv.writer(f, delimiter = ";")
                writer.writerows(lines)

            # act
            generator = read_data(temp_file, columns = [0, 1, 2, 3, 4, 5, 6, 7]) # Читаем все данные в строке
            data = list(generator)

            # assert
            # Сравниваем длину итоговых данных с тем что должно получиться
            self.assertEqual(len(data), len(lines) - 1, msg = f"Кол-во строк в итоговых данных неккоректно") # - 1 т.к. мы пропускаем заголовок

            # Поскольку в функции мы пропускаем заголовок, то сравниваем со сдвигом на 1 (пропускаем строку заголовка)
            self.assertEqual(data[0], lines[1], msg = f"Строки не совпадают") 
            self.assertEqual(data[1], lines[2], msg = f"Строки не совпадают") 
            self.assertEqual(data[2], lines[3], msg = f"Строки не совпадают")  

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
        self.assertEqual(data, "I_Hate_Wrong_Names")

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
            ['_[78]9337704444', 'ООО "ТЕСТ 1"', '1111111111'],
            ['_[78]9337704343', 'ООО "ТЕСТ 2"', '2222222222'],
            ['_[78]9337704XXX', 'ООО "ТЕСТ 2"', '2222222222'],
            ['_[78]93377[6-7]XXXX', 'ООО "ТЕСТ 3"', '3333333333'],
            ['_[78]933820555', 'ООО "ТЕСТ 3"', '3333333333']
        ]

        expected = ['_[78]93377[6-7]XXXX', '_[78]933820555']

        # act
        with tempfile.TemporaryDirectory() as temp_dir:
            group_by_operator(test_data, temp_dir)
            
            content: str
            files = os.listdir(temp_dir)
            try:
                with open(os.path.join(temp_dir, 'ООО_ТЕСТ_3.conf'), 'r') as f:
                    content = f.read()
                    for i in expected:
                        self.assertIn(i, content)

            except FileNotFoundError:
                ...

            # assert
            self.assertEqual(len(files), 3)
            self.assertEqual(['ООО_ТЕСТ_1.conf', 'ООО_ТЕСТ_2.conf', 'ООО_ТЕСТ_3.conf'], files, msg = f"Названия файлов не соответствуют нужным")
