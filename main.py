import csv, os, shutil
import requests
import argparse

from requests.exceptions import ConnectionError, Timeout

from cfg import logger, SkipError, WarningError, CriticalError
from cfg import DEFAULT_FILENAME, DOWNLOAD_URL, OUTPUT_DIR_NAME
from cfg import operators_list, default_operators, inn_to_operator

from cfg import GITEA_URL, OWNER, REPO, TOKEN
import base64

from datetime import datetime, timezone
import json

def main(filename: str = DEFAULT_FILENAME, selected_operators: list[str] | None = None):
    try:
        if os.path.exists(OUTPUT_DIR_NAME):
            shutil.rmtree(OUTPUT_DIR_NAME)

        logger.info('Downloading data')
        file = download_data(filename = filename)

        logger.info('Reading data')
        raw_data = read_data(file)

        logger.info('Parsing data')
        all_data = []
        for data in raw_data:
            try:
                inn = data[4]

                if selected_operators:
                    selected_inns = []

                    for op_name in selected_operators:

                        if op_name in operators_list:
                            selected_inns.extend(operators_list[op_name])

                    if inn not in selected_inns:
                        continue
                
                result = range_of_numbers(data[0], data[1], data[2], data[3], data[4]) # abc/def, от, до, Название, ИНН
                logger.debug(f'{data[0], data[1], data[2], data[3], data[4]}')
                all_data.extend(result)

            except SkipError: # Продолжаем т.к. ошибка произошла в одном конкретном случае
                logger.error(f'Error while processing data: {data[0], data[1], data[2], data[3], data[4]}', exc_info = True)
                continue
        
        logger.info('Grouping data')
        for data in all_data:
            try:
                group_by_operator(data)

            except SkipError:
                logger.error(f'Error while proccesing data: {data[0], data[1], data[2]}', exc_info = True)
                continue
        
        logger.info('Editing files')
        add_ending_to_files()

    except CriticalError:
        raise # Прерываем выполнение если произошла критическая ошибка

    finally:
        logger.info('Deleting file')
        if os.path.exists(filename):
            os.remove(filename)

def download_data(filename: str, url: str = DOWNLOAD_URL) -> str | None:
    try:
        req = requests.get(url, timeout = 10)
        req.raise_for_status()

        with open(filename, 'wb') as file:
            file.write(req.content)
        
        return filename

    except ConnectionError as e:
        if os.path.exists('DEF-9xx.csv'):
            logger.critical(f'ConnectionError {e} returning DEF-9xx.csv')
            return 'DEF-9xx.csv'
        
        elif os.path.exists(filename):
            logger.critical(f'ConnectionError {e} returning {filename}')
            return filename    

        else:
            logger.critical(f'ConnectionError {e}')
            raise CriticalError from e
    
    except Timeout as e:
        if os.path.exists('DEF-9xx.csv'):
            logger.critical(f'ConnectionError {e} returning DEF-9xx.csv')
            return 'DEF-9xx.csv'
        
        elif os.path.exists(filename):
            logger.critical(f'ConnectionError {e} returning {filename}')
            return filename  
        
        else:
            logger.critical(f'TimeoutError {e}')
            raise CriticalError from e

    except Exception as e:
        logger.critical(f'Unknown Exception {e}', exc_info = True)
        raise CriticalError from e
        
def read_data(path: str, columns: list[int] = [0, 1, 2, 4, 7]):
    try:
        with open(path, 'r', encoding='utf-8-sig') as file:
            # Отмечаем нужные столбцы, по дефолту: abc/ def, от, до, оператор, ИНН [0, 1, 2, 4, 7]
            reader = csv.reader(file, delimiter = ';')
            next(reader)

            for row in reader:
                yield list(row[i] for i in columns)
    
    except IOError as e:
        logger.critical(f'Can`t read file on path: {path}, check accessability', exc_info = True)
        raise CriticalError from e

def range_of_numbers(def_code: str, start_input: str, end_input: str, operator_name: str, inn: str) -> list[list[str]] | list[str]:
    try:
        start = start_input.zfill(7)
        end = end_input.zfill(7)

        # Возвращаем данные если номер единичный
        if start == end: 
            logger.debug([f'_[78]{def_code}{start}', operator_name, inn])
            return [[f'_[78]{def_code}{start}', operator_name, inn]]
        
        # Тут находим общую часть
        same_numbers = []
        for i in range(7):
            if start[i] == end[i]:
                same_numbers.append(start[i])

            else:
                break
        logger.debug(same_numbers)
        numbers = ''.join(same_numbers)

        # Создаем срезы
        n = len(numbers)
        start_remaining = start[n:]
        end_remaining = end[n:]

        stack = [(numbers, start_remaining, end_remaining)]
        patterns = []

        # Last in First Out изменение
        while stack:
            current_common, s_rest, e_rest = stack.pop()
            logger.debug(f'{current_common=} {s_rest=} {e_rest=}')

            if not s_rest: # Если начальная часть пуста - добавляем общую часть как готовый шаблон
                patterns.append(current_common)
                continue

            if not e_rest: # Если конечная часть пуста - добавляем общую часть + оставшуюся начальную часть
                patterns.append(current_common + s_rest)
                continue
            logger.debug(f'{patterns=}')
        
            # Проверяет, можно ли заменить оставшиеся цифры на X если:
            # Все цифры после первой в начальном номере = 0
            # Все цифры после первой в конечном номере = 9
            if s_rest[1:] == '0' * len(s_rest[1:]) and e_rest[1:] == '9' * len(e_rest[1:]):
                start_current = s_rest[0]
                end_current = e_rest[0]

                logger.debug(f'{start_current=} {end_current=}')
                if start_current == end_current:
                    pattern = current_common + start_current + 'X' * len(s_rest[1:])

                else:
                    pattern = current_common + f'[{start_current}-{end_current}]' + 'X' * len(s_rest[1:])

                patterns.append(pattern)
                logger.debug(f'After checking X {patterns=}')
            
            # Рекурсивное разбиение диапазона
            else:
                start_current = int(s_rest[0])
                end_current = int(e_rest[0])
                logger.debug(f'{start_current=} {end_current=}')
                
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
            result.append([f'_[78]{def_code}{pattern}', operator_name, inn])
        
        logger.debug(f'{result=}')
        return result
    
    except Exception as e:
        raise SkipError from e

def clean_filename(filename: str) -> str:
    try:
        forbidden_chars = "<>:'/\\|?*"
        
        for char in forbidden_chars:
            filename = filename.replace(char, '')

        filename_clean = filename.replace('"', '').replace(' ', '_')

        logger.debug(f'{filename=} {filename_clean=}')
        return filename_clean
    
    except TypeError:
        logger.error(f'Error in filename type {filename}')
        raise WarningError
    
    except Exception:
        logger.critical(f'Unknown Error while proccesing clean_filename', exc_info = True)
        raise CriticalError

def group_by_operator(data: list, output_dir_name: str = OUTPUT_DIR_NAME) -> None:
    try:
        os.makedirs(output_dir_name, exist_ok=True)

        pattern, operator, inn = str(data[0]), str(data[1]), str(data[2])
        
        logger.debug(f'{data=}')
        logger.debug(f'{pattern=}, {operator=}, {inn=}')
        if len(data) != 3:
            logger.warning(f'Пропущены некорректные данные: {data}')
            raise SkipError
        
        if not pattern.startswith('_[78]'):
            logger.warning(f'Пропущен некорректный шаблон: {pattern=}')
            raise SkipError

        if not operator or len(operator.strip()) < 2:
            logger.warning(f'Пропущено некорректное имя оператора: {operator=}')
            raise SkipError

        if len(inn) < 10 or len(inn) > 10:
            logger.warning(f'Пропущен неккоректный ИНН оператора: {inn=}')
            raise SkipError
        
        operator_key = inn_to_operator.get(inn) # Получаем инн оператора для фильтрации
        
        if not operator_key:
            logger.warning(f'Не найден ключ для оператора: {operator}')
            raise SkipError

        filename = f'{operator_key}_codes.conf'
        filepath = os.path.join(output_dir_name, filename)
        
        write_header = not os.path.exists(filepath)
        
        with open(filepath, 'a', encoding='utf-8-sig') as f:
            if write_header:
                f.write(f'[{operator_key}_codes]\n')
            
            f.write(f'exten = {pattern},1,GoSub(${{ARG1}},${{EXTEN}},1)\n')

    except IndexError as e:
        logger.warning(f'IndexError while proccesing group_by_operator')
        raise SkipError from e
    
    except TypeError as e:
        logger.warning(f'TypeError while proccesing group_by_operator')
        raise SkipError from e 
    
    except AttributeError as e:
        logger.warning(f'AttributeError while proccesing group_by_operator')
        raise SkipError from e
    
    except OSError as e:
        logger.critical(f'OSError while proccesing group_by_operator', exc_info = True)
        raise CriticalError from e

    except Exception as e:
        logger.critical(f'Unknown Error while proccesing group_by_operator', exc_info = True)
        raise CriticalError from e
    
def add_ending_to_files(output_dir_name: str = OUTPUT_DIR_NAME) -> None:
    try:

        for filename in os.listdir(output_dir_name):

            if filename.endswith('_codes.conf'):
                filepath = os.path.join(output_dir_name, filename)

                with open(filepath, 'a', encoding='utf-8') as f:
                    f.write('exten = _XXXX!,1,Return()\n')
                    f.write('exten = _XXXX!,2,Hangup()\n')

    except Exception as e:
        logger.error(f'Error adding ending to files: {e}')

def upload_multiple_files_to_gitea(gitea_url: str, token: str, owner: str, repo: str, branch: str = "main", **optional_params) -> None:
    """
    **optional_params: Дополнительные параметры для API:
        - author: dict with name and email
        - committer: dict with name and email  
        - dates: dict with author and committer dates
        - signoff: boolean
        - message: общее сообщение коммита
    """
    headers = {
        "Authorization": f"token {token}",
        "Content-Type": "application/json"
    }
    
    api_url = f"{gitea_url}/api/v1/repos/{owner}/{repo}/contents"
    
    try:
        files_data = []
        
        for filename in os.listdir("operators"):
            if filename.endswith("_codes.conf"):
                file_path = os.path.join("operators", filename)
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                encoded_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')

                file_check_url = f"{api_url}/{filename}"
                check_response = requests.get(
                    file_check_url, 
                    headers = headers, 
                    params = {"ref": branch}
                )
                
                file_info = {
                    "path": filename,
                    "content": encoded_content,
                    "branch": branch
                }
                
                if check_response.status_code == 200:
                    existing_file = check_response.json()
                    file_info["sha"] = existing_file["sha"]
                    file_info["operation"] = "update"
                    logger.info(f"Will update existing file: {filename}")

                elif check_response.status_code == 404:
                    file_info["operation"] = "create"
                    logger.info(f"Will create new file: {filename}")
                
                elif check_response.status_code == 502:
                    logger.critical(f"Error with Gitea servers: {check_response.status_code}: {check_response.text}")
                    break

                else:
                    logger.error(f"Error checking file {filename}: {check_response.status_code}")
                    continue
                
                files_data.append(file_info)
        
        if not files_data:
            logger.warning("No files to upload")
            raise WarningError
        
        data = {
            "files": files_data,
            "message": optional_params.get("message", "Update operator codes"),
            "branch": branch,
        }
        
        optional_copy = optional_params.copy()
        optional_copy.pop("message", None)
        data.update(optional_copy)
        
        logger.debug(f"Request data: {json.dumps(data, indent = 2)}")
        
        response = requests.post(api_url, headers = headers, json = data)
        
        if response.status_code in [200, 201]:
            logger.info(f"Successfully processed {len(files_data)} files")
                
        else:
            logger.error(f"Failed to upload files: {response.status_code} - {response.text}")

    except requests.exceptions.RequestException as e:
        logger.error(f'Request error while upload with Gitea API: {e}')
        if hasattr(e, '__notes__'):
            for note in e.__notes__:
                logger.error(f"Context: {note}")
        raise CriticalError from e
    
    except (ValueError, TypeError) as e:
        logger.error(f"Error in params: {e}")
        e.add_note(f"Gitea URL: {gitea_url}")
        e.add_note(f"repo: {owner}/{repo}")
        e.add_note(f"branch: {branch}")
        raise CriticalError from e
    
    except Exception as e:
        logger.error(f"Error uploading multiple files to Gitea: {e}", exc_info = True)
        raise CriticalError from e


if __name__ == '__main__':
    try:
        parser = argparse.ArgumentParser(description = 'Generate phone number ranges for specific operators')
        parser.add_argument(
            '--names', 
            nargs = '+', 
            help = 'List of operators to Parse (--names mts megafon beeline)'
        )
        args = parser.parse_args()
        
        if args.names: # Вызов с флагом --names
            selected_operators = []

            for name in args.names:
                if name in operators_list:
                    selected_operators.append(name)

                else:
                    print(f'Warning: Operator {name} not found in operators_list')

        else: # Дефолтный вызов
            selected_operators = default_operators.copy()
                
            print(f'Generating for default operators: {', '.join(default_operators)}')
        
        main(selected_operators = selected_operators)

        current_time = datetime.now(timezone.utc).isoformat()
        upload_multiple_files_to_gitea(
            GITEA_URL,
            TOKEN,
            OWNER,
            REPO,
            dates = {
                "author": current_time,
                "committer": current_time
            }
        )
    
    except KeyboardInterrupt:
        print('________CLOSED________')

    except CriticalError as e:
        logger.critical(f'Critical error: {e}', exc_info = True)
        print('________ERROR________')
    
    except WarningError as e:
        logger.warning(f'Warning error: {e}', exc_info = True)
