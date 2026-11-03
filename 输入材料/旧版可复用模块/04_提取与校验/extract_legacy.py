"""Offline, non-executing extraction of legacy reference materials.

Reads only the named source checkout and an already sanitized browser capture.
Does not connect to databases, models, production APIs, or execute legacy code.
"""
from __future__ import annotations

import ast
import collections
import hashlib
import json
import math
import re
import shutil
from pathlib import Path

OUT = Path(__file__).resolve().parents[1]
SRC = Path('D:/workspace/蜜獾原图')
V2 = Path('D:/workspace/蜜獾原图v2')
DATE = '2026-10-23'


def read(relative: str) -> str:
    return (SRC / relative).read_text(encoding='utf-8-sig')


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def write(relative: str, value: object) -> None:
    path = OUT / relative
    if OUT not in path.resolve().parents:
        raise ValueError('Output escapes the authorized directory')
    path.parent.mkdir(parents=True, exist_ok=True)
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
    path.write_text(text.rstrip() + '\n', encoding='utf-8')


TOKEN = re.compile(r'''\s+|//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|[A-Za-z_$][\w$]*|[\[\]{},:]''')


def parse_literal(text: str) -> object:
    """Strict literal-only parser: never eval/import/execute source code."""
    tokens: list[str] = []
    pos = 0
    for match in TOKEN.finditer(text):
        if text[pos:match.start()].strip():
            raise ValueError('Unsupported literal syntax: ' + text[pos:match.start()][:30])
        token = match.group()
        pos = match.end()
        if token.isspace() or token.startswith('//') or token.startswith('/*'):
            continue
        tokens.append(token)
    if text[pos:].strip():
        raise ValueError('Unsupported trailing literal syntax')
    index = 0

    def value() -> object:
        nonlocal index
        token = tokens[index]
        index += 1
        if token == '[':
            result = []
            while tokens[index] != ']':
                result.append(value())
                if tokens[index] == ',':
                    index += 1
                elif tokens[index] != ']':
                    raise ValueError('Expected array comma')
            index += 1
            return result
        if token == '{':
            result = {}
            while tokens[index] != '}':
                key = tokens[index]
                index += 1
                key = ast.literal_eval(key) if key[:1] in ('"', "'") else key
                if tokens[index] != ':':
                    raise ValueError('Expected object colon')
                index += 1
                if key in result:
                    raise ValueError('Duplicate literal key: ' + str(key))
                result[key] = value()
                if tokens[index] == ',':
                    index += 1
                elif tokens[index] != '}':
                    raise ValueError('Expected object comma')
            index += 1
            return result
        if token in ('true', 'false', 'null'):
            return {'true': True, 'false': False, 'null': None}[token]
        if token[:1] in ('"', "'"):
            return ast.literal_eval(token)
        if re.fullmatch(r'-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?', token):
            return float(token) if any(x in token.lower() for x in ('.', 'e')) else int(token)
        raise ValueError('Non-literal expression: ' + token)

    result = value()
    if index != len(tokens):
        raise ValueError('Unexpected trailing tokens')
    return result


def balanced(text: str, start: int) -> tuple[str, int]:
    stack = []
    close = {'[': ']', '{': '}'}
    pos = start
    while pos < len(text):
        if text.startswith('//', pos):
            end = text.find('\n', pos)
            pos = len(text) if end < 0 else end + 1
            continue
        if text.startswith('/*', pos):
            end = text.find('*/', pos + 2)
            if end < 0:
                raise ValueError('Unclosed comment')
            pos = end + 2
            continue
        char = text[pos]
        if char in ('"', "'", '`'):
            quote = char
            pos += 1
            while pos < len(text):
                if text[pos] == '\\':
                    pos += 2
                elif text[pos] == quote:
                    pos += 1
                    break
                else:
                    pos += 1
            continue
        if char in close:
            stack.append(close[char])
        elif char in (']', '}'):
            if not stack or stack.pop() != char:
                raise ValueError('Unbalanced literal')
            if not stack:
                return text[start:pos + 1], pos + 1
        pos += 1
    raise ValueError('Unterminated literal')


def constant(relative: str, name: str, after: int = 0) -> tuple[object, int, int]:
    text = read(relative)
    match = re.search(r'\bconst\s+' + re.escape(name) + r'\b[^=\n]*=\s*', text[after:])
    if not match:
        raise ValueError('Constant not found: ' + relative + ':' + name)
    start = after + match.end()
    literal, end = balanced(text, start)
    return parse_literal(literal), text.count('\n', 0, start) + 1, end


SNAPSHOTS = [
    'server/imagePhysicalizer.ts', 'server/frequencyProcessor.ts',
    'server/fingerprintDestroyer.ts', 'server/exifToolWriter.ts',
    'server/exifVerifier.ts', 'server/uploadSimulator.ts', 'server/sizeOptimizer.ts',
    'server/presetSerializer.ts', 'server/exifWriter.ts',
    'client/src/lib/presetEchoFields.ts', 'shared/domain-dictionaries.ts',
    'server/presetSerializer.test.ts', 'client/src/lib/presetEchoFields.test.ts',
    'server/fingerprintDestroyer.test.ts', 'server/exifWriter.test.ts',
    'server/exifVerifier.test.ts', 'server/exifVerifier.keyType.test.ts',
    'server/normalizeParams.test.ts', 'server/sizeOptimizer.test.ts',
    'server/uploadSimulator.test.ts', 'server/categoryAndImport.test.ts',
]
EXCERPTS = [
    ('drizzle/schema.ts', 54, 209, 'parameters_schema.ts.txt'),
    ('client/src/pages/ParameterConfig.tsx', 774, 1000, 'import_template.tsx.txt'),
    ('server/routers.ts', 1741, 1771, 'parameters_list_route.ts.txt'),
    ('server/rds.ts', 272, 368, 'parameters_list_query.ts.txt'),
    ('client/src/App.tsx', 94, 99, 'parameters_route.tsx.txt'),
]


def positive(value: object) -> bool:
    try:
        number = float(value)
        return math.isfinite(number) and number > 0
    except (TypeError, ValueError):
        return False


def model_key(make: str, model: str) -> str:
    make = re.sub(r'\s+', ' ', make.strip())
    model = re.sub(r'\s+', ' ', model.strip())
    if make and model.casefold().startswith(make.casefold() + ' '):
        return model
    return (make + ' ' + model).strip()


def family_hint(model: str, category: str = '') -> str:
    """Advisory name rules, never a change to the legacy classification."""
    name = model.casefold()
    if category == 'phone':
        return 'phone'
    if 'pocket' in name:
        return 'gimbal_camera_candidate'
    if re.search(r'\b360\b|gopro max|insta360 x\d|one rs.*360', name):
        return 'panoramic_360_candidate'
    if 'gfx' in name or 'hasselblad' in name:
        return 'medium_format_candidate'
    if 'fujifilm x100' in name or 'leica q' in name or 'ricoh gr' in name:
        return 'fixed_lens_candidate'
    if 'leica m11' in name:
        return 'rangefinder_candidate'
    if category == 'action' or 'gopro' in name or 'osmo action' in name:
        return 'action_camera'
    if category == 'dslr':
        return 'legacy_dslr_pending_review'
    if category == 'mirrorless':
        return 'legacy_mirrorless_pending_review'
    return 'unclassified_name_only'


def main() -> None:
    online_path = OUT / '02_设备参数/线上预设_脱敏原始.json'
    online = json.loads(online_path.read_text(encoding='utf-8'))
    rows = online['items']
    assert len(rows) == online['total'] == len({r['id'] for r in rows})
    sources = []
    for relative in SNAPSHOTS:
        source = SRC / relative
        target = OUT / '01_源码参考/原样快照' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        sources.append({'source': str(source), 'sha256': sha(source),
                        'output': target.relative_to(OUT).as_posix(), 'byte_exact': True})
    for relative, start, end, filename in EXCERPTS:
        source = SRC / relative
        lines = read(relative).splitlines()
        output = '01_源码参考/边界片段/' + filename
        write(output, '\n'.join(lines[start - 1:end]))
        sources.append({'source': str(source), 'sha256': sha(source), 'output': output,
                        'line_start': start, 'line_end': end, 'byte_exact': False})
    for relative in ['client/src/pages/ParameterConfig.tsx', 'package.json', 'pnpm-lock.yaml']:
        if not any(s['source'] == str(SRC / relative) for s in sources):
            sources.append({'source': str(SRC / relative), 'sha256': sha(SRC / relative),
                            'output': None, 'purpose': 'literal extraction or dependency provenance'})

    categories, cat_line, _ = constant('shared/domain-dictionaries.ts', 'PARAMETER_CATEGORIES')
    dictionaries = {}
    for name in re.findall(r'export const (PARAMETER_\w+)\s*=', read('shared/domain-dictionaries.ts')):
        value, line, _ = constant('shared/domain-dictionaries.ts', name)
        dictionaries[name] = {'values': value, 'source_line': line}
    write('02_设备参数/旧版字段值字典.json', dictionaries)

    schema = read('drizzle/schema.ts').splitlines()
    fields = []
    for index in range(58, 207):
        match = re.match(r'\s+(\w+):\s*(\w+)\("([^"]+)"', schema[index - 1])
        if not match:
            continue
        alias, builder, column = match.groups()
        prior = schema[index - 2].strip()
        description = prior.removeprefix('/**').removesuffix('*/').strip() if prior.startswith('/**') else ''
        if column in {'user_id', 'usage_count', 'created_at', 'updated_at', 'deleted_at', 'id', 'is_public', 'is_default'}:
            policy = 'PROVENANCE_ONLY_DO_NOT_IMPORT'
        elif column in {'gps_latitude', 'gps_longitude', 'gps_altitude', 'author', 'copyright'}:
            policy = 'RUNTIME_OR_OWNERSHIP_DO_NOT_INHERIT'
        elif column in {'image_width', 'image_height', 'image_format', 'color_space', 'color_depth', 'image_orientation', 'file_number'}:
            policy = 'FINAL_IMAGE_OR_RUNTIME_OVERRIDE'
        else:
            policy = 'CANDIDATE_REQUIRES_TYPE_AND_SEMANTIC_VALIDATION'
        fields.append({'column': column, 'orm_alias': alias, 'legacy_builder': builder,
                       'description': description, 'definition': schema[index - 1].strip(),
                       'source_line': index, 'v2_policy': policy})
    serializer_aliases = [{'alias': a, 'column': c} for a, c in re.findall(
        r'^\s+(\w+): row\.(\w+)', read('server/presetSerializer.ts'), re.M)]
    write('02_设备参数/参数字段与映射.json', {'fields': fields, 'serializer_aliases': serializer_aliases,
          'note': '完整保留 schema 字段，不认为旧表、导入模板与线上列天然一致。摄影数值可有小数，项目资金另按整数账本。'})

    config = 'client/src/pages/ParameterConfig.tsx'
    descriptions, desc_line, desc_end = constant(config, 'fieldDescriptions')
    headers, header_line, _ = constant(config, 'headers', after=desc_end)
    samples = []
    for name in ['sampleRow', 'sampleDslr', 'sampleMirrorless', 'sampleAction']:
        values, line, _ = constant(config, name)
        if len(values) != len(headers):
            raise ValueError('Import sample columns disagree: ' + name)
        samples.append({'source_symbol': name, 'source_line': line,
                        'status': 'EXAMPLE_ONLY_NOT_PRODUCTION_PRESET', 'values': dict(zip(headers, values))})
    enum_ref, enum_line, _ = constant(config, 'enumRef')
    write('02_设备参数/导入模板与四条示例.json', {'source': config, 'description_line': desc_line,
        'headers_line': header_line, 'field_descriptions': descriptions, 'headers': headers,
        'samples': samples, 'enum_reference_line': enum_line, 'enum_reference': enum_ref,
        'warning': '示例含来源标签、类型及格式矛盾，不导入为真实设备模板。示例作者是旧源码示例文本，不授予新系统署名权限。'})
    coverage = json.loads((OUT / '02_设备参数/线上字段覆盖核对.json').read_text(encoding='utf-8'))
    schema_columns = {field['column'] for field in fields}
    online_columns = set(coverage['source_keys'])
    write('02_设备参数/字段层级差异.json', {
        'schema_only_vs_import_headers': sorted(schema_columns - set(headers)),
        'import_headers_only_vs_schema': sorted(set(headers) - schema_columns),
        'online_non_alias_extra_vs_schema': sorted(k for k in online_columns - schema_columns
                                                   if k.lower() == k and k not in {'ownerId'}),
        'retained_online_fields': coverage['retained_keys'],
        'note': '线上 ai_img2img_strength 已保留；ip_geo 仅登记列名，不保留值。导入模板注释声称 62 列，实提为 58 列。模板缺 AI 与 FocalPlane 等字段，不能替代完整 JSON。'})

    specs = []
    for relative in ['server/exifToolWriter.ts', 'server/exifWriter.ts']:
        data, line, _ = constant(relative, 'CAMERA_SPECS')
        for model, parameters in data.items():
            expected_x = parameters['pixelWidth'] * 10 / parameters['sensorWidth']
            expected_y = parameters['pixelHeight'] * 10 / parameters['sensorHeight']
            ratio_x = parameters['focalPlaneXRes'] / expected_x
            ratio_y = parameters['focalPlaneYRes'] / expected_y
            specs.append({'model': model, 'parameters': parameters, 'source': relative,
                'constant_line': line, 'status': 'REFERENCE_NOT_MANUFACTURER_VERIFIED',
                'conditional_consistency_check': {'assumed_resolution_unit': 'cm (schema default 3; assumption only)',
                    'expected_x_if_cm': expected_x, 'expected_y_if_cm': expected_y,
                    'relative_error_x': abs(ratio_x - 1), 'relative_error_y': abs(ratio_y - 1),
                    'needs_review_if_cm': abs(ratio_x - 1) > .05 or abs(ratio_y - 1) > .05}})
    grouped_specs = collections.defaultdict(dict)
    for item in specs:
        grouped_specs[item['model']][item['source']] = item['parameters']
    spec_differences = [{'model': model, 'variants': values} for model, values in grouped_specs.items()
                        if len(values) != 2 or len({json.dumps(x, sort_keys=True) for x in values.values()}) > 1]
    write('02_设备参数/源码机型规格.json', {'records': specs, 'unique_models': len(grouped_specs),
          'differences': spec_differences, 'warning': '像素宽高与传感器尺寸仅是旧表参考；不得用其强行改输出尺寸。FocalPlane 单位和数值均须实证。'})

    ui_options = []
    text = read(config)
    for match in re.finditer(r'options=\{\s*\[', text):
        start = text.index('[', match.start())
        literal, end = balanced(text, start)
        tail = text[end:text.find('/>', end) + 2]
        field = re.search(r'value=\{(?:newPreset|editForm)\.(\w+)\}', tail)
        if field:
            ui_options.append({'field': field.group(1), 'source_line': text.count('\n', 0, start) + 1,
                               'values': parse_literal(literal), 'status': 'UI_SUGGESTIONS_ONLY'})
    selects = []
    for match in re.finditer(r'<select\b[\s\S]*?</select>', text):
        fragment = match.group()
        field = re.search(r'value=\{(?:newPreset|editForm)\.(\w+)\}', fragment)
        if field:
            values = [{'value': v, 'label': label.strip()} for v, label in re.findall(
                r'<option\s+value="([^"]*)"[^>]*>([^<]*)</option>', fragment)]
            selects.append({'field': field.group(1), 'source_line': text.count('\n', 0, match.start()) + 1,
                            'values': values, 'status': 'UI_OPTIONS_ONLY'})
    write('02_设备参数/界面候选值.json', {'comboboxes': ui_options, 'selects': selects,
          'warning': '候选名称不等于完整参数、真实设备支持或可写 MakerNote。'})

    tags = []
    for line, content in enumerate(read('server/exifToolWriter.ts').splitlines(), 1):
        for match in re.finditer(r"tags\['([^']+)'\]\s*=\s*(.+?);", content):
            tags.append({'tag': match.group(1), 'expression': match.group(2), 'source_line': line,
                         'preset_fields': sorted(set(re.findall(r'preset\.(\w+)', match.group(2))))})
    write('02_设备参数/EXIF标签映射.json', {'source': 'server/exifToolWriter.ts', 'assignments': tags,
        'warning': '记录旧赋值表达式而非批准正确性。ShutterSpeedValue、ApertureValue、MaxApertureValue 的数值/APEX及 ExifTool 输入输出约定须单独验证；当前 writer 未实际使用 maker_note_template。'})
    platform, platform_line, _ = constant('server/uploadSimulator.ts', 'PLATFORM_PROFILES')
    write('02_设备参数/旧编码配置参考.json', {'source_line': platform_line, 'profiles': platform,
          'reuse': 'JPEG 编码字段参考；maxWidth/maxHeight、平台选择、颜色调整不得继承为 v2 默认。源码自称实测不等于本轮已验证。'})
    package = json.loads(read('package.json'))
    wanted = ['sharp', 'piexifjs', 'exiftool-vendored', 'xlsx', 'vitest']
    deps = {k: package.get('dependencies', {}).get(k) or package.get('devDependencies', {}).get(k) for k in wanted}
    write('01_源码参考/依赖说明.json', {'legacy_declared_versions': deps, 'lockfile_sha256': sha(SRC / 'pnpm-lock.yaml'),
          'status': 'REFERENCE_ONLY_NOT_INSTALL_INSTRUCTIONS', 'note': '源码快照没有复制数据库适配、API Key、模型账号及底座；不可直接启动。Python 迁移不自动继承 Node 依赖。'})

    templates = []
    for row in rows:
        flags = []
        required = ['name', 'category', 'camera_make', 'camera_model', 'iso', 'shutter_speed', 'aperture', 'focal_length']
        missing = [k for k in required if row.get(k) in (None, '')]
        if missing:
            flags.append('MISSING_REQUIRED:' + ','.join(missing))
        for field in ['iso', 'aperture', 'focal_length']:
            if not positive(row.get(field)):
                flags.append('INVALID_POSITIVE_NUMBER:' + field)
        shutter = str(row.get('shutter_speed') or '').strip()
        normalized_shutter = re.sub(r'\s*(?:seconds?|secs?|s|\")$', '', shutter, flags=re.I).strip()
        parts = normalized_shutter.split('/')
        if len(parts) not in (1, 2) or not all(positive(v) for v in parts):
            flags.append('INVALID_SHUTTER_SPEED')
        iso_range = str(row.get('iso_range') or '')
        limits = re.findall(r'\d+(?:\.\d+)?', iso_range.replace(',', ''))
        if len(limits) != 2 or float(limits[0]) > float(limits[-1]):
            flags.append('ISO_RANGE_NEEDS_REVIEW')
        elif positive(row.get('iso')) and not float(limits[0]) <= float(row['iso']) <= float(limits[1]):
            flags.append('ISO_OUTSIDE_DECLARED_RANGE')
        if row['category'] not in categories:
            flags.append('NEW_CATEGORY_REQUIRES_MAPPING')
        if row['category'] == 'phone' and positive(row.get('focal_length')) and float(row['focal_length']) > 30:
            flags.append('PHONE_ACTUAL_FOCAL_LENGTH_GT30MM_REVIEW_HEURISTIC')
        make = str(row.get('camera_make') or '')
        model = str(row.get('camera_model') or '')
        display = model_key(make, model)
        if row['category'] == 'dslr' and re.search(r'(Canon )?EOS R|Nikon Z|Sony (?:A\d|ILCE)|Leica (?:SL|M11)', display, re.I):
            flags.append('LEGACY_DSLR_LABEL_NEEDS_MODEL_REVIEW')
        values = {k: v for k, v in row.items() if k not in {'id', 'is_public', 'is_default'}}
        templates.append({'template_ref': 'legacy-online-' + str(row['id']),
            'provenance': {'source_id': row['id'], 'source_url': online['source_url'], 'captured_on': DATE,
                'legacy_category': row['category'], 'legacy_visibility': 'PRIVATE' if row.get('is_public') in (0, False) else 'PUBLIC_OR_UNKNOWN'},
            'device_display': display, 'family_hint': family_hint(display, row['category']),
            'classification_basis': 'ADVISORY_NAME_RULE_NOT_VENDOR_VERIFIED',
            'activation_status': 'NOT_ACTIVATED',
            'review_bucket': 'QUARANTINE_REVIEW' if flags else 'STRUCTURAL_CANDIDATE',
            'review_flags': flags, 'legacy_parameters': values,
            'normalization_proposals': {'shutter_speed_without_unit': normalized_shutter},
            'v2_runtime_overrides': {'dimensions': 'ACTUAL_FINAL_IMAGE', 'image_format': 'JPEG', 'color_space': 'sRGB',
                'gps': 'RESOLVE_PER_V2_TASK_POLICY_DO_NOT_INHERIT_FIXED_COORDINATES',
                'author_and_copyright': 'CONFIGURE_OWNERSHIP_SEPARATELY',
                'ai_strength_and_prompts': 'DO_NOT_ENABLE_LEGACY_LAYER0',
                'maker_note': 'REQUIRES_ACTUAL_WRITE_AND_READBACK'},
            'verification': {'manufacturer_specs': 'NOT_RUN', 'image_pipeline': 'NOT_RUN', 'exif_roundtrip': 'NOT_RUN'}})
    write('02_设备参数/设备模板候选_完整.json', {'schema_version': 'legacy-extraction-candidate/1.0',
          'not_an_executable_import_contract': True, 'templates': templates})
    category_counts = collections.Counter(r['category'] for r in rows)
    for category in sorted(category_counts):
        safe = re.sub(r'[^A-Za-z0-9_-]', '_', category)
        write('02_设备参数/按旧分类/' + safe + '.json', {'legacy_category': category,
            'templates': [t for t in templates if t['provenance']['legacy_category'] == category]})
    families = collections.Counter(t['family_hint'] for t in templates)
    for family in sorted(families):
        write('02_设备参数/按建议设备形态/' + family + '.json', {'family_hint': family,
            'classification_basis': 'ADVISORY_NAME_RULE_NOT_VENDOR_VERIFIED',
            'templates': [t for t in templates if t['family_hint'] == family]})

    registry: dict[str, dict] = {}

    def register(name: str, kind: str, reference: object, category: str = '') -> None:
        if not name:
            return
        key = name.casefold()
        entry = registry.setdefault(key, {'display_name': name, 'source_kinds': [], 'references': [], 'legacy_categories': []})
        if kind not in entry['source_kinds']:
            entry['source_kinds'].append(kind)
        if category and category not in entry['legacy_categories']:
            entry['legacy_categories'].append(category)
        entry['references'].append({'kind': kind, 'reference': reference})

    for template in templates:
        register(template['device_display'], 'ONLINE_PRESET', template['template_ref'], template['provenance']['legacy_category'])
    for record in specs:
        register(record['model'], 'SOURCE_SPEC', record['source'])
    for record in ui_options:
        if record['field'] == 'camera_model':
            for name in record['values']:
                register(name, 'UI_NAME_ONLY', config + ':' + str(record['source_line']))
    for record in selects:
        if record['field'] == 'maker_note_template':
            for option in record['values']:
                if option['value']:
                    register(option['value'], 'UI_MAKERNOTE_NAME_ONLY', config + ':' + str(record['source_line']))
    for entry in registry.values():
        entry['complete_preset_available'] = 'ONLINE_PRESET' in entry['source_kinds']
        entry['support_status'] = 'NOT_ACTIVATED_NOT_RUNTIME_VERIFIED'
        entry['alias_policy'] = 'ONLY_WHITESPACE_CASE_AND_DUPLICATE_BRAND_NORMALIZED_NO_PRODUCT_CODE_ALIAS_MERGE'
    write('02_设备参数/设备来源总目录.json', {'devices': sorted(registry.values(), key=lambda x: x['display_name'].casefold()),
          'warning': '品牌+型号显示键不是厂商唯一型号ID。ILCE 等别名未擅自合并；名称目录不能作为可用模板数量。'})
    flag_counts = collections.Counter(flag.split(':')[0] for t in templates for flag in t['review_flags'])
    summary = {'capture_date': DATE, 'online_total': len(rows), 'unique_source_ids': len({r['id'] for r in rows}),
        'legacy_category_counts': dict(category_counts), 'family_hint_counts': dict(families),
        'private_source_count': sum(t['provenance']['legacy_visibility'] == 'PRIVATE' for t in templates),
        'structural_candidate_count': sum(not t['review_flags'] for t in templates),
        'quarantine_review_count': sum(bool(t['review_flags']) for t in templates), 'review_flag_counts': dict(flag_counts),
        'schema_field_count': len(fields), 'import_header_count': len(headers),
        'import_example_count': len(samples), 'camera_spec_records': len(specs), 'camera_spec_unique_models': len(grouped_specs),
        'camera_spec_source_differences': len(spec_differences), 'tag_assignment_count': len(tags),
        'unique_assigned_tags': len({t['tag'] for t in tags}), 'ui_option_groups': len(ui_options) + len(selects),
        'device_directory_entries': len(registry), 'source_snapshot_files': len(SNAPSHOTS), 'source_excerpt_files': len(EXCERPTS),
        'manufacturer_and_runtime_verification': 'NOT_RUN'}
    write('02_设备参数/提取统计.json', summary)
    write('04_提取与校验/来源清单.json', {'captured_on': DATE, 'local_head_observed': '4a3f2ade0532cab1cd69f01b0b00cdce5c78c5e7',
          'sources': sources, 'online_capture_sha256': sha(online_path), 'online_read_only': True,
          'legacy_execution': 'NOT_RUN', 'production_mutations': 'NONE'})
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
