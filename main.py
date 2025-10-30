import csv, os
from collections import defaultdict
import requests
from cfg import logger, SkipError


def main():
    all_data = []

    test = read_data("data.csv")
    for data in test:
        try:
            result = range_of_numbers(data[0], data[1], data[2], data[3], data[4])

        except SkipError as e:
            logger.error(f"Error while processing data: {data[0], data[1], data[2], data[3], data[4]}", exc_info = True)
            continue
        all_data.extend(result)

    group_by_operator(all_data)

def download_data(url: str = "https://opendata.digital.gov.ru/downloads/DEF-9xx.csv", filename: str = "data.csv") -> str | None:
    try:
        logger.info("Requesting data...")
        req = requests.get(url)

        with open("data.csv", "wb") as file:
            logger.info("Write data in .csv file...")
            file.write(req.content)
        
            return file.name

    except TimeoutError:
        logger.warning(f"Timeout error, trying read downloaded manualy file")
        return "DEF-9xx.csv" # Используем дефолтное название на тот случай если файл уже есть локально
    
    except ConnectionError:
        logger.warning(f"Connection error, trying read downloaded manualy file")
        return "DEF-9xx.csv" # Используем дефолтное название на тот случай если файл уже есть локально

    except IOError:
        logger.error(f"Can`t write file {filename}, check accessability")
        raise IOError.add_note(f"Error while proccesing {__name__}")

    except PermissionError:
        logger.error(f"Can`t access to file {filename}, check access rights, and no other proccess using file {filename}")
        raise PermissionError
    
    except Exception:
        logger.critical(f"Unknown Error while proccesing {__name__}")
        raise Exception.add_note(f"Unknown Error while proccesing {__name__}")
        
def read_data(path: str, columns: list[int] = [0, 1, 2, 4, 7]):
    try:
        with open(path, 'r', encoding="utf-8-sig") as file:
            logger.info("Reading data from file")
            # Отмечаем нужные столбцы, по дефолту: abc/ def, от, до, оператор, ИНН [0, 1, 2, 4, 7]
            reader = csv.reader(file, delimiter = ";")
            next(reader)

            for row in reader:
                yield list(row[i] for i in columns)
    
    except IOError:
        logger.error(f"Can`t read file on path: {path}, check accessability")
        raise IOError.add_note(f"Error while proccesing {__name__}")
    
    except FileNotFoundError:
        logger.critical(f"File doesn`t exist check filename or path")
        raise FileNotFoundError
    
    except Exception:
        logger.critical(f"Unknown Error while proccesing {__name__}")
        raise Exception.add_note(f"Unknown Error while proccesing {__name__}")

def clean_filename(filename: str) -> str:
    try:
        forbidden_chars = '<>:"/\\|?*'
        
        logger.info("Deleting chars")
        for char in forbidden_chars:
            filename = filename.replace(char, '')

        filename = filename.replace('"', '').replace(' ', '_')

        logger.debug(f"{filename=}")
        return filename
    
    except TypeError:
        logger.error("Error in filename type")
        raise TypeError
    
    except Exception:
        logger.critical(f"Unknown Error while proccesing {__name__}")
        raise Exception.add_note(f"Unknown Error while proccesing {__name__}")

def range_of_numbers(def_code: str, start_input: str, end_input: str, operator_name: str, inn: str) -> list[list[str]] | list[str]:
    try:
        start = start_input.zfill(7)
        end = end_input.zfill(7)

        # Возвращаем данные если номер единичный
        if start == end: 
            logger.debug([f"_[78]{def_code}{start}", operator_name, inn])
            return [[f"_[78]{def_code}{start}", operator_name, inn]]
        
        # Тут находим общую часть
        same_numbers = []
        for i in range(7):
            if start[i] == end[i]:
                same_numbers.append(start[i])

            else:
                break
        logger.debug(same_numbers)
        numbers = "".join(same_numbers)

        # Создаем срезы
        n = len(numbers)
        start_remaining = start[n:]
        end_remaining = end[n:]

        stack = [(numbers, start_remaining, end_remaining)]
        patterns = []

        # Last in First Out изменение
        while stack:
            current_common, s_rest, e_rest = stack.pop()
            logger.debug(f"{current_common=} {s_rest=} {e_rest=}")

            if not s_rest: # Если начальная часть пуста - добавляем общую часть как готовый шаблон
                patterns.append(current_common)
                continue

            if not e_rest: # Если конечная часть пуста - добавляем общую часть + оставшуюся начальную часть
                patterns.append(current_common + s_rest)
                continue
            logger.debug(f"{patterns=}")
        
            # Проверяет, можно ли заменить оставшиеся цифры на X если:
            # Все цифры после первой в начальном номере = 0
            # Все цифры после первой в конечном номере = 9
            if s_rest[1:] == "0" * len(s_rest[1:]) and e_rest[1:] == "9" * len(e_rest[1:]):
                start_current = s_rest[0]
                end_current = e_rest[0]

                logger.debug(f"{start_current=} {end_current=}")
                if start_current == end_current:
                    pattern = current_common + start_current + 'X' * len(s_rest[1:])
                else:
                    pattern = current_common + f"[{start_current}-{end_current}]" + 'X' * len(s_rest[1:])
                patterns.append(pattern)
                logger.debug(f"After checking X {patterns=}")
            
            # Рекурсивное разбиение диапазона
            else:
                start_current = int(s_rest[0])
                end_current = int(e_rest[0])
                logger.debug(f"{start_current=} {end_current=}")
                
                if start_current != 9:
                    new_s_rest = s_rest[1:]
                    new_e_rest = '9' * len(s_rest[1:])
                    stack.append((current_common + str(start_current), new_s_rest, new_e_rest))
                logger.debug(f'!=9 {stack=}')

                for d in range(start_current + 1, end_current):
                    new_s_rest = '0' * len(s_rest[1:])
                    new_e_rest = '9' * len(s_rest[1:])
                    stack.append((current_common + str(d), new_s_rest, new_e_rest))
                    logger.debug(f'{d=}')
                
                if end_current != 0:
                    new_s_rest = '0' * len(s_rest[1:])
                    new_e_rest = e_rest[1:]
                    stack.append((current_common + str(end_current), new_s_rest, new_e_rest))
                logger.debug(f'!=0 {stack=}')
        
        result = []
        for pattern in patterns:
            pattern = pattern.replace('[0-9]', 'X')
            result.append([f"_[78]{def_code}{pattern}", operator_name, inn])
        
        logger.debug(f"{result=}")
        return result
    
    except AttributeError:
        logger.warning(f"Value doesn`t have attribute: {e}")
        raise SkipError from e

    except ValueError as e:
        logger.warning(f"Invalid value: {e}")
        raise SkipError from e
    
    except IndexError as e:
        logger.warning(f"Index error: {e}")
        raise SkipError from e

    except TypeError as e:
        logger.warning(f"Invalid type of variable {e}")
        raise SkipError from e

    except Exception:
        logger.critical(f"Unknown Error while proccesing {__name__}")
        raise Exception.add_note(f"Unknown Error while proccesing {__name__}")

def group_by_operator(all_data: list, output_dir_name: str = "operators") -> None:
    try:
        logger.info("Starting grouping")
        os.makedirs(output_dir_name, exist_ok=True)

        grouped = defaultdict(list)
        
        for data in all_data:
            logger.debug(f"{data=}")
            if len(data) != 3: # Если данных меньше чем 3 (паттерн, оператор, ИНН)
                logger.debug(f"Пропущены некорректные данные: {data}")
                continue
                
            pattern, operator, inn = str(data[0]), str(data[1]), str(data[2])
            
            if not pattern.startswith("_[78]"): # Если паттерн неккоректно обработан и начинается не с _[78]
                logger.debug(f"Пропущен некорректный шаблон: {pattern=}")
                continue

            if not operator or len(operator.strip()) < 2: # Слишком короткое имя оператора 
                logger.debug(f"Пропущено некорректное имя оператора: {operator=}")
                continue

            if inn < 10 or inn > 10:
                logger.debug(f"Пропущено неккоректный ИНН оператора: {inn=}")
                continue
                
            grouped[inn].append({
                "pattern": pattern,
                "operator": operator
            })
        logger.debug(f"Final grouping {grouped=}")

        for inn, patterns_data in grouped.items():
            operator_name = patterns_data[0]['operator']

            filename = f"{clean_filename(operator_name)}.conf"
            filepath = os.path.join(output_dir_name, filename)
            logger.debug(f"{filepath=} ___ {filename=}")    

            patterns = [item['pattern'] for item in patterns_data]

            logger.info(f"Writing data in file: {filename}...")
            with open(filepath, 'w', encoding='utf-8') as f:
                for pattern in patterns:
                    logger.debug(f'Writing {pattern=} in {filename}')
                    f.write(f"exten = {pattern},1,GoSub(${{ARG1}},${{EXTEN}},1)\n")

    except:
        ...
        

if __name__ == "__main__":
    logger.info("Starting...")
    try:
        download_data()
        main()
    
    except IOError:
        logger.critical(f"Check access rights for file", exc_info = True)
    