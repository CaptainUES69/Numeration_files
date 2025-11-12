import argparse
import base64
import csv
import json
import os
import re
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from io import TextIOWrapper
from typing import Any, Generator

import requests
from requests.exceptions import ConnectionError, Timeout

from cfg import (DEFAULT_FILENAME, DOWNLOAD_URL, GITEA_URL, OUTPUT_DIR_NAME,
                 OWNER, REPO, TOKEN, CriticalError, PatternLine, RowData,
                 SkipError, WarningError, get_default_operators,
                 inn_to_operator, logger)


def main(selected_operators: list[str], filename: str = DEFAULT_FILENAME):
    try:
        if os.path.exists(OUTPUT_DIR_NAME):
            shutil.rmtree(OUTPUT_DIR_NAME)
        
        if selected_operators == None:
            logger.error('Selected_operators = None')
            raise CriticalError

        logger.info(f'Downloading file: {filename} from: {DOWNLOAD_URL}')
        file = download_file(filename = filename)

        logger.info(f'Reading file: {filename}')
        raw_data = read_data(file)

        logger.info('Parsing lines from raw_data')
        all_data = parsing_rows(raw_data)
  
        logger.info('Grouping all lines')
        grouped_data = grouping_lines(all_data)

        logger.info('Editing and writing in files')
        write_operator_config(grouped_data)

        logger.info('Upload data into gitea')
        current_time = datetime.now(timezone.utc).isoformat()
        upload_multiple_files_to_gitea(
            GITEA_URL,
            TOKEN,
            OWNER,
            REPO,
            dates = {"author": current_time, "committer": current_time},
        )

    except CriticalError:
        raise  # Прерываем выполнение если произошла критическая ошибка

    finally:
        logger.info('Deleting file')
        if os.path.exists(filename):
            os.remove(filename)
            pass


def download_file(filename: str, url: str = DOWNLOAD_URL) -> str | None:
    try:
        headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/csv,application/csv',
        'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
        'Referer': 'https://opendata.digital.gov.ru/',
        }
        req = requests.get(url, stream = True, headers = headers, timeout = 30)
        req.raise_for_status()

        with open(filename, "wb") as file:
            file.write(req.content)

        return filename

    except ConnectionError as e:
        logger.critical(f"ConnectionError {e}")
        raise CriticalError from e

    except Timeout as e:
        logger.critical(f"TimeoutError {e}")
        raise CriticalError from e

    except Exception as e:
        logger.critical(f"Unknown Exception {e}", exc_info = True)
        raise CriticalError from e


def read_data(path: str, columns: list[int] = [0, 1, 2, 4, 7]) -> Generator[list[str], Any, None]:
    try:
        with open(path, "r", encoding = "utf-8-sig") as file:
            reader = csv.reader(file, delimiter=";")
            next(reader)

            for row in reader:
                yield list(row[i] for i in columns)

    except IOError as e:
        logger.critical(f'Can`t read file on path: {path}, check accessability', exc_info = True)
        raise CriticalError from e


def parsing_rows(raw_data: Generator[list[str], Any, None]) -> list[PatternLine]:
    all_data = []
    selected_inns = []
    operators_names = default_operators.keys()

    logger.debug(f'{default_operators.keys()}')
    for op_name in selected_operators:

        logger.debug(f'{op_name=}')
        if op_name in operators_names:
            logger.debug(f'in opers: {op_name=}')
            selected_inns.append(default_operators.get(op_name))

    logger.debug(f'{selected_inns=}')
    for row in raw_data:
        
        logger.debug(f'{row[4]=}')
        if row[4] not in selected_inns:
            continue

        logger.debug(f'Row data: {row}')
        current_row = RowData(row[0], row[1], row[2], row[3], row[4])
        
        try:
            result = range_of_numbers(current_row)
            logger.debug(f'Row data: {current_row}')
            for i in result:
                all_data.append(i)

        except SkipError:  # Продолжаем т.к. ошибка произошла в одном конкретном случае
            logger.error(
                f'Error while processing data: {current_row}',
                exc_info = True,
            )
            continue
    
    return all_data


def range_of_numbers(current_row: RowData) -> list[PatternLine]:
    try:
        start = current_row.start_input.zfill(7)
        end = current_row.end_input.zfill(7)

        # Единичный номер
        if start == end:
            return [PatternLine(f'_[78]{current_row.def_code}{start}', current_row.operator_name, current_row.inn)]

        # Находим общую часть
        same_numbers = []
        for i in range(7):
            if start[i] == end[i]:
                same_numbers.append(start[i])
            else:
                break
        
        numbers = ''.join(same_numbers)
        n = len(numbers)
        start_remaining = start[n:]
        end_remaining = end[n:]
        
        stack = [(numbers, start_remaining, end_remaining)]
        patterns = []

        while stack:
            current_common, s_rest, e_rest = stack.pop(0)

            # Если остатки пусты
            if not s_rest and not e_rest:
                patterns.append(current_common)
                continue

            if not s_rest:
                patterns.append(current_common + e_rest)
                continue

            if not e_rest:
                patterns.append(current_common + s_rest)
                continue

            # Проверка возможности замены на X
            if (s_rest[1:] == '0' * len(s_rest[1:]) and 
                e_rest[1:] == '9' * len(e_rest[1:])):
                
                start_current = s_rest[0]
                end_current = e_rest[0]

                if start_current == end_current:
                    pattern = current_common + start_current + 'X' * len(s_rest[1:])
                else:
                    pattern = (current_common + f'[{start_current}-{end_current}]' + 'X' * len(s_rest[1:]))
                patterns.append(pattern)

            else:
                start_current = int(s_rest[0])
                end_current = int(e_rest[0])

                # Левая часть
                if start_current != 9:
                    new_s_rest = s_rest[1:]
                    new_e_rest = '9' * len(s_rest[1:])
                    stack.append((current_common + str(start_current), new_s_rest, new_e_rest))

                # Средние части
                for d in range(start_current + 1, end_current):
                    new_s_rest = '0' * len(s_rest[1:])
                    new_e_rest = '9' * len(s_rest[1:])
                    stack.append((current_common + str(d), new_s_rest, new_e_rest))

                # Правая часть
                if end_current != 0:
                    new_s_rest = '0' * len(s_rest[1:])
                    new_e_rest = e_rest[1:]
                    stack.append((current_common + str(end_current), new_s_rest, new_e_rest))

        if not patterns:
            patterns = [start]

        # Преобразуем все patterns
        results = []
        for pattern in patterns:
            pattern = pattern.replace('[0-9]', 'X')
            results.append(PatternLine(f"_[78]{current_row.def_code}{pattern}", 
                                     current_row.operator_name, current_row.inn))

        return results

    except Exception as e:
        logger.error(f'Error processing range {current_row.start_input}-{current_row.end_input}: {e}')
        raise SkipError from e


def grouping_lines(all_lines: list[PatternLine]) -> dict[str: list[str]]:
    grouped = defaultdict(list)
    for line in all_lines: 
        operator_key: str = inn_to_operator.get(line.inn)

        if not operator_key:
            logger.debug(f'Не найден ключ для оператора: {line.operator_name}')
            continue
        
        grouped[operator_key].append(line.pattern)

    return dict(grouped)


def write_operator_config(grouped_lines: dict[str: str]) -> None:
    os.makedirs(OUTPUT_DIR_NAME, exist_ok = True)

    for operator in grouped_lines.keys():
        filepath = f'{os.path.join(OUTPUT_DIR_NAME, f'{operator}_conf.cfg')}'
        write_header = not os.path.exists(filepath)

        with open(filepath, 'a', encoding = 'utf-8-sig') as f:
            if write_header:
                f.write(f"[{operator}_codes]\n")

            for pattern in grouped_lines.get(operator):
                f.write(f'exten = {pattern},1,GoSub(${{ARG1}},${{EXTEN}},1)\n')

            f.write("exten = _XXXX!,1,Return()\n")
            f.write("exten = _XXXX!,2,Hangup()\n")


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

        for filename in os.listdir(OUTPUT_DIR_NAME):

            if not filename.endswith("_codes.conf"): 
                continue

            file_path = os.path.join(OUTPUT_DIR_NAME, filename)
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")

            file_check_url = f"{api_url}/{filename}"
            check_response = requests.get(file_check_url, headers = headers, params = {"ref": branch})

            file_info = {
                "path": filename,
                "content": encoded_content,
                "branch": branch,
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

        logger.debug(f"Request data: {json.dumps(data, indent=2)}")

        response = requests.post(api_url, headers=headers, json=data)

        if response.ok:
            logger.info(f"Successfully processed {len(files_data)} files")

        else:
            logger.error(f"Failed to upload files: {response.status_code} - {response.text}")

    except requests.exceptions.RequestException as e:
        logger.error(f"Request error while upload with Gitea API: {e}")

        if hasattr(e, "__notes__"):
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



if __name__ == "__main__":
    try:
        default_operators = get_default_operators()
        parser = argparse.ArgumentParser(
            description="Generate phone number ranges for specific operators"
        )
        parser.add_argument(
            "--names",
            nargs = "+",
            help = "List of operators to Parse (--names mts megafon beeline)",
        )
        args = parser.parse_args()

        if args.names:  # Вызов с флагом --names
            selected_operators = []

            for name in args.names:
                if name in default_operators.keys():
                    selected_operators.append(name)

                else:
                    print(f"Warning: Operator {name} not found in default_operators")

            print(f"Generating for: {selected_operators}")

        else:  # Дефолтный вызов
            selected_operators: list[str] = default_operators.keys()

            print(f"Generating for default operators: {', '.join(default_operators.keys())}")

        main(selected_operators = selected_operators)

    except KeyboardInterrupt:
        print("________CLOSED________")

    except CriticalError as e:
        logger.critical(f"Critical error: {e}", exc_info = True)
        print("________ERROR________")

    except WarningError as e:
        logger.warning(f"Warning error: {e}", exc_info = True)
