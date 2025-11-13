import os
import re
from collections import defaultdict

from cfg import OUTPUT_DIR_NAME, Pattern, PatternItem, logger


def optimize_config_file(optimization_lvl: int, input_file: str, output_file: str, output_dir: str = OUTPUT_DIR_NAME) -> None:
    logger.info(f"Starting optimization for file: {input_file}\n")
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

        optimized_lines = lines
        for i in range(0, optimization_lvl):
            logger.debug(f'Cicle number: {i}')
            optimized_lines = optimize_patterns(optimized_lines)
            optimized_lines = compress_sequential_patterns(optimized_lines)
            optimized_lines = sort_lines_by_def_code(optimized_lines)
            optimized_lines = merge_adjacent_ranges(optimized_lines)

    logger.info(f'Sort and write lines for file: {output_file}')
    optimized_lines = sort_lines_by_def_code(optimized_lines)

    os.makedirs(output_dir, exist_ok = True)
    output_path = f'{output_dir}/{output_file}'
    with open(output_path, 'w', encoding='utf-8') as f:
        for line in optimized_lines:
            f.write(line + '\n')


def optimize_patterns(patterns: list[str]) -> list[str]:
    logger.info('\nOptimizing patterns')
    parsed_patterns: list[Pattern] = []
    for pattern in patterns:
        # До: "exten = _[78]91234567[0-9]X,1,GoSub"
        # После: prefix="91234567", mask=['[0-9]', 'X']
        pattern_obj = parse_pattern(pattern)
        if pattern_obj.prefix and pattern_obj.mask:
            parsed_patterns.append(pattern_obj)

    logger.debug(f'{parsed_patterns=}')

    groups: dict[tuple[str, int], list[Pattern]]= {}
    for pattern in parsed_patterns:
        key = (pattern.prefix, len(pattern.mask)) # Группируем по префиксу и длине маски
        if key not in groups:
            groups[key] = []

        groups[key].append(pattern)

    logger.debug(f'{groups=}')

    merged_patterns: list[Pattern] = []
    for key, group_patterns in groups.items():
        if len(group_patterns) == 1:
            # Если не с чем объединять добавляем так
            merged_patterns.append(group_patterns[0])

        else:
            # Если несколько шаблонов объединяем
            merged_masks = merge_masks([pattern.mask for pattern in group_patterns])
            for mask in merged_masks:
                merged_patterns.append(Pattern(key[0], mask))

    logger.debug(f'{merged_patterns=}')

    # Заменяем диапазоны [0-9] на Х
    x_replaced: list[Pattern] = []
    for merg_pattern in merged_patterns:
        new_mask = []
        for char in merg_pattern.mask:

            if char.startswith('[') and char.endswith(']'):
                range_match = re.match(r'\[(\d)-(\d)\]', char)

                if range_match and int(range_match.group(1)) == 0 and int(range_match.group(2)) == 9:
                    new_mask.append('X')

                else:
                    new_mask.append(char)

            else:
                new_mask.append(char)
                
        x_replaced.append(Pattern(merg_pattern.prefix, new_mask))

    logger.debug(f'{x_replaced=}')

    # Группируем по шаблонам с Х
    x_groups: dict[tuple, list[Pattern]] = {}
    for pattern in x_replaced:
        # Создаем ключ, заменяя X на специальный маркер '_X_'
        key_parts = [pattern.prefix]
        for char in pattern.mask:
            key_parts.append('_X_' if char == 'X' else char)

        key = tuple(key_parts)
        
        if key not in x_groups:
            x_groups[key] = []

        x_groups[key].append(pattern)
    logger.debug(f'{x_groups=}')

    # Объединяем похожие маски в группах
    final_patterns: list[Pattern] = []
    for key, group_patterns in x_groups.items():
        # Один в группе добавляем в финальный вид
        if len(group_patterns) == 1: 
            final_patterns.append(group_patterns[0])

        # Объединяем маски, заменяя различающиеся позиции на X
        else:
            merged_mask = merge_similar_masks([pattern.mask for pattern in group_patterns])
            final_patterns.append(Pattern(group_patterns[0].prefix, merged_mask)) # 0 т.к. префикс у всех одинаков
    logger.debug(f'{final_patterns=}')


    # Собираем строку обратно
    result = [pattern.to_string() for pattern in final_patterns]
    logger.debug(f'{result=}')

    return result


def parse_pattern(pattern: str) -> Pattern:
    match = re.match(r'exten = _\[78\](\d+)(.*),1,GoSub', pattern)
    if match:
        prefix = match.group(1) # Извлекаем префикс - 9001234
        mask_str = match.group(2) # Извлекаем маску - XX
        mask = split_mask(mask_str) # Разбиваем на части
        logger.debug(f'Return data: {prefix, mask}')

        return Pattern(prefix, mask)
    
    logger.debug(f'Return data: None, None')
    return Pattern('', [])


def split_mask(mask_str: str) -> list[str]:
    elements = [] # Результат сохраняется сюда
    i = 0
    logger.debug('Starting spliting masks')
    while i < len(mask_str):
        logger.debug(f'Cicle number: {i}')
        if mask_str[i] == '[':
            # Нашли начало диапазона - ищем конец
            j = mask_str.find(']', i)
            if j != -1:
                logger.debug(f'j != -1; j = {j}')
                # Добавляем весь диапазон как один элемент
                elements.append(mask_str[i: j + 1])
                i = j + 1 # Перескакиваем на позицию после ]   

            else:
                logger.debug('j = -1')
                elements.append(mask_str[i])
                i += 1

        else:
            logger.debug(f'msk_str[i] = {mask_str[i]}')
            # Обычный символ - добавляем как есть
            elements.append(mask_str[i])
            i += 1

    return elements


def merge_masks(masks: list[list[str]]) -> list[list[str]]:
    logger.debug('Starting merging masks')
    if not masks:
        return []
    
    mask_length = len(masks[0]) # Предполагается что все маски одинаковой длины
    position_values: list[set[str]] = [] # Значение для каждой позиции
    
    # Для каждой позиции в маске собираем все возможные значения
    for i in range(mask_length):
        all_values = set() # собираем уникальные значения
        for mask in masks:
            char = mask[i]

            # Если символ X то добавляем все цифры что он заменяет
            if char == 'X': 
                all_values.update(str(d) for d in range(10)) 

            # Находим паттерн и все числа которые он собой представляет [1-3] = 1, 2, 3
            elif char.startswith('[') and char.endswith(']'):
                range_match = re.match(r'\[(\d)-(\d)\]', char)
                if range_match:
                    start, end = int(range_match.group(1)), int(range_match.group(2))
                    all_values.update(str(d) for d in range(start, end + 1))

            # Если символ 1 то просто добавляем его
            else:
                all_values.add(char)
        logger.debug(f'{all_values=}')

        position_values.append(all_values)
    logger.debug(f'{position_values=}')

    merged_mask = []
    for values in position_values:
        # Только одно возможное значение - используем его как есть
        if len(values) == 1:
            merged_mask.append(next(iter(values)))

        else:
            # Несколько значений - пытаемся создать диапазон
            digits = [int(v) for v in values if v.isdigit()]

            if not digits:
                # Нет цифровых значений или нельзя объединить - используем 'X'
                merged_mask.append('X')

            # Находим минимальную и максимальную цифру и создаем срез
            min_digit = min(digits)
            max_digit = max(digits)
            expected = set(str(i) for i in range(min_digit, max_digit + 1))
            # Проверяем, совпадает ли ожидаемый диапазон с фактическими значениями и создаем диапазон
            if expected == values:
                merged_mask.append(f"[{min_digit}-{max_digit}]")

            else:
                logger.debug(f'Can`t merge masks: {masks}')
                # Не можем объединить - возвращаем исходные маски
                return masks
            
    logger.debug(f'{merged_mask=}')
    return [merged_mask]


def merge_similar_masks(masks: list[list[str]]) -> list[str]:
    if not masks:
        return []
    
    mask_length = len(masks[0]) # Предполагаем что все маски одинаковой длины
    result_mask: list[str] = []
    
    # Для каждой позиции смотрим какие символы там встречаются
    for i in range(mask_length):
        position_chars = set(mask[i] for mask in masks)
        # Если в позиции разные символы - заменяем на X
        result_mask.append(
            'X' 
            if len(position_chars) > 1 
            else next(iter(position_chars))
        )

    logger.debug(f'{result_mask=}')
    return result_mask


def compress_sequential_patterns(patterns: list[str]) -> list[str]:
    if len(patterns) <= 1:
        return patterns
    
    logger.info(f"\nStarting compression of {len(patterns)} patterns")
    
    # Парсим паттерны более простым способом
    parsed_items: list[PatternItem] = []
    for pattern in patterns:
        # Извлекаем основную часть между _[78] и ,1,GoSub
        start_idx = pattern.find('_[78]') + 5
        end_idx = pattern.find(',1,GoSub')
        if start_idx == 4 or end_idx == -1:
            parsed_items.append(
                PatternItem(
                    pattern,
                    '',
                    0,
                    '')
                )
            continue
            
        pattern_body = pattern[start_idx:end_idx]
        
        # Считаем количество X в конце
        x_count = 0
        for char in reversed(pattern_body):
            if char == 'X':
                x_count += 1

            else:
                break
        
        # Извлекаем цифровую часть (все что до X)
        digit_part = pattern_body[:-x_count] if x_count > 0 else pattern_body
        
        parsed_items.append(
            PatternItem(
                pattern,
                digit_part,
                x_count,
                pattern_body
            )
        )
    logger.debug(f'{parsed_items=}')

    # Группируем по количеству X и по базовой части (без последней цифры)
    groups: dict[tuple[str, int], list[tuple[int, PatternItem]]] = {}
    for item in parsed_items:
        if item.x_count == 0 or not item.digit_part:
            continue
            
        digit_part = item.digit_part
        
        # Берем базовую часть без последней цифры
        if len(digit_part) > 1:
            base_part = digit_part[:-1]
            last_digit = digit_part[-1]

        else:
            base_part = ""
            last_digit = digit_part
        
        if last_digit.isdigit():
            key = (base_part, item.x_count)
            if key not in groups:
                groups[key] = []

            groups[key].append((int(last_digit), item))
    logger.debug(f'{groups=}')
    
    # Сжимаем последовательные цифры
    compressed_patterns: list[str] = []
    processed = set()
    for key, digit_items in groups.items():
        base_part, x_count = key
        
        # Сортируем по цифре
        digit_items.sort(key = lambda x: x[0]) # Лямбда для удобства вызова без вынесения микрофункции в отдельную
        
        # Находим последовательные диапазоны
        current_range = [digit_items[0]]
        ranges: list[list[tuple[int, PatternItem]]] = []
        
        for i in range(1, len(digit_items)):
            current_digit = digit_items[i][0]
            prev_digit = digit_items[i-1][0]
            
            if current_digit == prev_digit + 1:
                current_range.append(digit_items[i])

            else:
                if len(current_range) >= 2:  # Минимум 2 последовательных числа
                    ranges.append(current_range)
                current_range = [digit_items[i]]
        
        if len(current_range) >= 2:
            ranges.append(current_range)
        
        # Создаем сжатые паттерны для найденных диапазонов
        for range_items in ranges:
            if len(range_items) < 2:
                continue
                
            start_digit = range_items[0][0]
            end_digit = range_items[-1][0]
            
            # Создаем новый паттерн
            new_digit_part = f"{base_part}[{start_digit}-{end_digit}]"
            new_pattern_body = f"{new_digit_part}{'X' * x_count}"
            new_pattern = f"exten = _[78]{new_pattern_body},1,GoSub(${{ARG1}},${{EXTEN}},1)"
            
            compressed_patterns.append(new_pattern)
            
            # Помечаем исходные паттерны как обработанные
            for digit, item in range_items:
                processed.add(item.original)
        # logger.debug(f'{processed=}')

    # Добавляем необработанные паттерны
    for item in parsed_items:
        if item.original not in processed:
            compressed_patterns.append(item.original)
    
    logger.debug(f'{compressed_patterns=}')
    logger.info(f"Compression completed: {len(patterns)} -> {len(compressed_patterns)} patterns")
    return compressed_patterns


def sort_lines_by_def_code(lines: list[str]) -> list[str]:
    logger.info('\nStarting sorting all lines')
    # Разделяем строки на заголовочные и остальные
    header_lines = []
    pattern_lines = []
    other_lines = []
    
    for line in lines:
        if line.startswith('[') and line.endswith(']'):
            header_lines.append(line)

        elif line.startswith('exten = _[78]'):
            pattern_lines.append(line)

        else:
            other_lines.append(line)
    
    logger.debug(f'{len(pattern_lines)=}')
    # Сортируем паттерны по DEF-коду
    pattern_lines.sort(key = extract_def_code)
    logger.debug(f'{len(pattern_lines)=}')

    return header_lines + pattern_lines + other_lines


def extract_def_code(line: str) -> int:
    # Ищем DEF-код в формате _[78]XXX
    match = re.search(r'_\[78\](\d{3})', line)
    if match:
        return int(match.group(1))
    # Если DEF-код не найден, возвращаем максимальное значение для размещения в конце
    logger.debug('DEF not found return inf')
    return float('inf')


def merge_adjacent_ranges(patterns: list[str]) -> list[str]:
    if len(patterns) <= 1:
        return patterns
    
    logger.info(f"\nMerging adjacent ranges for {len(patterns)} patterns")
    
    # Группируем паттерны по базовой части (без диапазонов)
    pattern_groups = defaultdict(list)
    merged_patterns: list[str] = []
    
    for pattern in patterns:
        # Извлекаем основную часть
        match = re.match(r'exten = _\[78\](\d+)(.*),1,GoSub', pattern)
        if not match:
            # Если паттерн не соответствует формату, просто добавляем его как есть
            merged_patterns.append(pattern)
            continue
            
        prefix = match.group(1)
        mask_str = match.group(2)
        
        # Находим позиции диапазонов [x-y]
        range_positions: list[tuple[int, str]] = []
        clean_mask: list[str] = []
        i = 0
        while i < len(mask_str):
            if mask_str[i] != '[':
                clean_mask.append(mask_str[i])
                i += 1

            else:
                j = mask_str.find(']', i)
                if j != -1:
                    range_positions.append((len(clean_mask), mask_str[i:j+1]))
                    clean_mask.append('R')  # Заменяем диапазон на маркер
                    i = j + 1

                else:
                    clean_mask.append(mask_str[i])
                    i += 1      
        
        # Создаем ключ для группировки
        key = (prefix, ''.join(clean_mask))
        pattern_groups[key].append((pattern, range_positions))
    logger.debug(f'{pattern_groups.keys()=}')

    # Объединяем диапазоны в каждой группе
    for key, group_patterns in pattern_groups.items():
        prefix, mask_template = key
        
        # Если в группе только один паттерн, просто добавляем его
        if len(group_patterns) == 1:
            merged_patterns.append(group_patterns[0][0])
            continue
            
        # Собираем все диапазоны для каждой позиции
        position_ranges = defaultdict(list)
        for pattern, range_positions in group_patterns:
            for pos, range_str in range_positions:
                position_ranges[pos].append(range_str)
        
        # Пытаемся объединить диапазоны в каждой позиции
        merged_ranges = {}
        can_merge = True
        
        for pos, ranges in position_ranges.items():
            if len(ranges) == 1:
                merged_ranges[pos] = ranges[0]
                continue
                
            # Собираем все цифры из диапазонов
            all_digits = set()
            for range_str in ranges:
                range_match = re.match(r'\[(\d)-(\d)\]', range_str)
                if range_match:
                    start, end = int(range_match.group(1)), int(range_match.group(2))
                    all_digits.update(range(start, end + 1))

                else:
                    # Если не удалось распарсить диапазон, не можем объединить
                    can_merge = False
                    break
            
            if not all_digits or not can_merge:
                can_merge = False
                break

            min_digit = min(all_digits)
            max_digit = max(all_digits)
            expected_digits = set(range(min_digit, max_digit + 1))
            
            if all_digits == expected_digits:
                merged_ranges[pos] = f"[{min_digit}-{max_digit}]"

            else:
                # Не можем объединить - оставляем исходные диапазоны
                can_merge = False
                break
        
        # Если не можем объединить все диапазоны, добавляем все исходные паттерны
        if not can_merge or len(merged_ranges) != len(position_ranges):
            for pattern, _ in group_patterns:
                merged_patterns.append(pattern)
            continue
        
        # Создаем объединенный паттерн
        result_mask = build_result_mask(mask_template, merged_ranges, group_patterns)
        logger.debug(f'{result_mask}')

        # Создаем новый паттерн
        new_pattern = f"exten = _[78]{prefix}{''.join(result_mask)},1,GoSub(${{ARG1}},${{EXTEN}},1)"
        merged_patterns.append(new_pattern)
    logger.debug(f'{merged_patterns=}')

    logger.info(f"После объединения: {len(merged_patterns)} паттернов")
    return merged_patterns


def build_result_mask(
        mask_template: str, 
        merged_ranges: dict[int, str], 
        group_patterns: list[tuple[str, list[tuple[int, str]]]]) -> list[int]: 
    
    result_mask = []
    marker_index = 0
    
    # Подготавливаем источник замен
    replacement_source = create_replacement_source(merged_ranges, group_patterns)
    logger.debug(f'{replacement_source=}')
    
    for char in mask_template:
        if char == 'R':
            replacement = replacement_source.get(marker_index, 'X')
            result_mask.append(replacement)
            marker_index += 1

        else:
            result_mask.append(char)
    
    logger.debug(f'{result_mask=}')
    return result_mask


def create_replacement_source(
        merged_ranges: dict[int, str],
        group_patterns: list[tuple[str, list[tuple[int, str]]]]) -> dict[int, str]:
    
    source = {}
    source.update(merged_ranges)  # Сначала объединенные диапазоны
    
    # Затем добавляем из первого шаблона (только недостающие)
    if group_patterns and group_patterns[0][1]:
        for pos, range_str in group_patterns[0][1]:
            if pos not in source:
                source[pos] = range_str
    logger.debug(f'{source=}')

    return source
