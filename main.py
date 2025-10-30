import csv, os
from collections import defaultdict
import requests
import logging


logging.basicConfig(
    level = logging.INFO,
    filename="py_log.log",
    filemode="w",
    encoding="utf-8",
    format = "%(asctime)s %(levelname)s -- %(funcName)s(%(lineno)d) - %(message)s"
)

def main():
    all_data = []

    test = read_data("data.csv")
    for data in test:
        result = range_of_numbers(data[0], data[1], data[2], data[3], data[4])
        all_data.extend(result)

    group_by_operator(all_data)

def download_data(url: str = "https://opendata.digital.gov.ru/downloads/DEF-9xx.csv", filename: str = "data.csv") -> str | None:
    req = requests.get(url)

    with open("data.csv", "wb") as file:
        file.write(req.content)
    
        return file.name
        
def read_data(path: str, columns: list[int] = [0, 1, 2, 4, 7]):
    with open(path, 'r', encoding="utf-8-sig") as file:
        # Отмечаем нужные столбцы, по дефолту: abc/ def, от, до, оператор, ИНН [0, 1, 2, 4, 7]
        reader = csv.reader(file, delimiter = ";")
        next(reader)

        for row in reader:
            yield list(row[i] for i in columns)

def clean_filename(filename: str) -> str:
    forbidden_chars = '<>:"/\\|?*'

    for char in forbidden_chars:
        filename = filename.replace(char, '')

    filename = filename.replace('"', '').replace(' ', '_')

    return filename

def range_of_numbers(def_code: str, start_input: str, end_input: str, operator_name: str, inn: str) -> list[list[str]] | list[str]:
    start = start_input.zfill(7)
    end = end_input.zfill(7)

    # Возвращаем данные если номер единичный
    if start == end: 
        return [[f"_[78]{def_code}{start}", operator_name, inn]]
    
    # Тут находим общую часть
    same_numbers = []
    for i in range(7):
        if start[i] == end[i]:
            same_numbers.append(start[i])

        else:
            break
    
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

        if not s_rest: # Если начальная часть пуста - добавляем общую часть как готовый шаблон
            patterns.append(current_common)
            continue

        if not e_rest: # Если конечная часть пуста - добавляем общую часть + оставшуюся начальную часть
            patterns.append(current_common + s_rest)
            continue
    
        # Проверяет, можно ли заменить оставшиеся цифры на X
        # Все цифры после первой в начальном номере = 0
        # Все цифры после первой в конечном номере = 9
        if s_rest[1:] == "0" * len(s_rest[1:]) and e_rest[1:] == "9" * len(e_rest[1:]):
            start_current = s_rest[0]
            end_current = e_rest[0]

            if start_current == end_current:
                pattern = current_common + start_current + 'X' * len(s_rest[1:])
            else:
                pattern = current_common + f"[{start_current}-{end_current}]" + 'X' * len(s_rest[1:])
            patterns.append(pattern)
        
        # Рекурсивное разбиение диапазона
        else:
            start_current = int(s_rest[0])
            end_current = int(e_rest[0])
            
            if start_current != 9:
                new_s_rest = s_rest[1:]
                new_e_rest = '9' * len(s_rest[1:])
                stack.append((current_common + str(start_current), new_s_rest, new_e_rest))
            
            for d in range(start_current + 1, end_current):
                new_s_rest = '0' * len(s_rest[1:])
                new_e_rest = '9' * len(s_rest[1:])
                stack.append((current_common + str(d), new_s_rest, new_e_rest))
            
            if end_current != 0:
                new_s_rest = '0' * len(s_rest[1:])
                new_e_rest = e_rest[1:]
                stack.append((current_common + str(end_current), new_s_rest, new_e_rest))
    
    result = []
    for pattern in patterns:
        pattern = pattern.replace('[0-9]', 'X')
        result.append([f"_[78]{def_code}{pattern}", operator_name, inn])
    
    return result

def group_by_operator(all_data: list, output_dir_name: str = "operators") -> None:
    os.makedirs(output_dir_name, exist_ok=True)

    grouped = defaultdict(list)
    
    for data in all_data:
        if len(data) != 3:
            logging.info(f"Пропущены некорректные данные: {data}")
            continue
            
        pattern, operator, inn = data[0], data[1], data[2]
        
        if not pattern.startswith("_[78]"):
            logging.info(f"Пропущен некорректный шаблон: {pattern}")
            continue

        if not operator or len(operator.strip()) < 2:
            logging.info(f"Пропущено некорректное имя оператора: {operator}")
            continue
            
        grouped[inn].append({
            "pattern": pattern,
            "operator": operator
        })

    for inn, patterns_data in grouped.items():
        operator_name = patterns_data[0]['operator']

        filename = f"{clean_filename(operator_name)}.conf"
        filepath = os.path.join(output_dir_name, filename)    

        patterns = [item['pattern'] for item in patterns_data]

        with open(filepath, 'w', encoding='utf-8') as f:
            for pattern in patterns:
                f.write(f"exten = {pattern},1,GoSub(${{ARG1}},${{EXTEN}},1)\n")
        

if __name__ == "__main__":
    download_data()
    main()