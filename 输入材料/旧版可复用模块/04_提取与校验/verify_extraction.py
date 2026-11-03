"""Validate preservation, provenance and extraction boundaries, not image quality."""
from __future__ import annotations

import collections
import hashlib
import json
import re
import runpy
import sys
from pathlib import Path

sys.dont_write_bytecode = True
OUT = Path(__file__).resolve().parents[1]
V2 = OUT.parents[1]
DATE = '2026-10-23'
CHECKS: list[dict] = []


def read_json(relative: str) -> object:
    return json.loads((OUT / relative).read_text(encoding='utf-8'))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def check(name: str, ok: bool, detail: object) -> None:
    CHECKS.append({'check': name, 'result': 'PASS' if ok else 'FAIL', 'detail': detail})


def main() -> None:
    module = runpy.run_path(str(OUT / '04_提取与校验/extract_legacy.py'), run_name='extraction_for_validation')
    parser = module['parse_literal']
    hint = module['family_hint']
    check('literal_comments_escapes_types',
          parser('/*a*/ { x: [1, -2.5, true, false, null, "a\\nb",], // b\n y: \'设备\', }')
          == {'x': [1, -2.5, True, False, None, 'a\nb'], 'y': '设备'},
          'Literal parser preserves Unicode, escapes, comments, trailing commas and types.')
    rejected = 0
    for sample in ['{x: process.exit()}', '{x: require("fs")}', '{x: 1 + 2}', '{x: 1, x: 2}']:
        try:
            parser(sample)
        except (ValueError, IndexError, SyntaxError):
            rejected += 1
    check('nonliteral_and_duplicate_key_rejection', rejected == 4,
          'Four executable/ambiguous fixtures rejected without executing source code.')
    check('name_classification_regressions',
          hint('vivo X100 Pro', 'phone') == 'phone'
          and hint('Fujifilm X100VI', 'mirrorless') == 'fixed_lens_candidate'
          and hint('Insta360 GO 3S', 'action') == 'action_camera'
          and hint('Insta360 X4', 'action') == 'panoramic_360_candidate'
          and hint('Unknown model', 'new_category') == 'unclassified_name_only',
          'Phone/model substring and non-360 Insta360 cases stay distinct; unknown names retained.')

    raw = read_json('02_设备参数/线上预设_脱敏原始.json')
    candidates = read_json('02_设备参数/设备模板候选_完整.json')['templates']
    stats = read_json('02_设备参数/提取统计.json')
    sources = read_json('04_提取与校验/来源清单.json')
    original = raw['items']
    original_by_id = {row['id']: row for row in original}
    candidate_by_id = {row['provenance']['source_id']: row for row in candidates}
    check('online_count_and_unique_ids',
          len(original) == raw['total'] == len(original_by_id) == 405,
          {'rows': len(original), 'unique': len(original_by_id), 'declared_total': raw['total']})
    check('candidate_coverage', len(candidates) == len(candidate_by_id)
          and set(original_by_id) == set(candidate_by_id), 'All source IDs appear exactly once in the complete candidate file.')
    mismatches = []
    for source_id, row in original_by_id.items():
        expected = {key: value for key, value in row.items() if key not in {'id', 'is_public', 'is_default'}}
        if candidate_by_id[source_id]['legacy_parameters'] != expected:
            mismatches.append(source_id)
    check('exact_preservation_of_retained_values', not mismatches, {'mismatching_source_ids': mismatches})
    forbidden = {'user_id', 'ownerId', 'ip_geo', 'gps_latitude', 'gps_longitude', 'gps_altitude',
                 'author', 'copyright', 'usage_count', 'created_at', 'updated_at', 'deleted_at'}
    retained_keys = set().union(*(row.keys() for row in original))
    check('runtime_and_identity_values_excluded', not (retained_keys & forbidden),
          {'retained_key_count': len(retained_keys), 'forbidden_keys_present': sorted(retained_keys & forbidden)})
    coverage = read_json('02_设备参数/线上字段覆盖核对.json')
    check('full_source_field_coverage_audit', coverage['audit_sample_rows'] == len(original)
          and set(coverage['retained_keys']) == retained_keys
          and set(coverage['source_keys']) == set(coverage['retained_keys']) | set(coverage['excluded_keys'])
          and not (set(coverage['retained_keys']) & set(coverage['excluded_keys']))
          and 'ai_img2img_strength' in retained_keys,
          {'audited_records': coverage['audit_sample_rows'], 'source_keys': len(coverage['source_keys']),
           'retained_keys': len(coverage['retained_keys']), 'extended_ai_strength_retained': True})
    category_ids = []
    for path in (OUT / '02_设备参数/按旧分类').glob('*.json'):
        group = json.loads(path.read_text(encoding='utf-8'))
        category_ids += [row['provenance']['source_id'] for row in group['templates']]
        if any(row['provenance']['legacy_category'] != group['legacy_category'] for row in group['templates']):
            category_ids.append('WRONG_CATEGORY')
    check('category_partition_no_loss_no_duplicates',
          collections.Counter(category_ids) == collections.Counter(original_by_id.keys()),
          dict(collections.Counter(row['category'] for row in original)))
    family_ids = []
    for path in (OUT / '02_设备参数/按建议设备形态').glob('*.json'):
        group = json.loads(path.read_text(encoding='utf-8'))
        family_ids += [row['provenance']['source_id'] for row in group['templates']]
        if any(row['family_hint'] != group['family_hint'] for row in group['templates']):
            family_ids.append('WRONG_FAMILY')
    check('advisory_family_partition_no_loss_no_duplicates',
          collections.Counter(family_ids) == collections.Counter(original_by_id.keys()),
          {'groups': len(stats['family_hint_counts']), 'total': sum(stats['family_hint_counts'].values())})
    check('private_provenance_and_activation_boundary',
          all(row['provenance']['legacy_visibility'] == 'PRIVATE' and row['activation_status'] == 'NOT_ACTIVATED'
              and row['classification_basis'] == 'ADVISORY_NAME_RULE_NOT_VENDOR_VERIFIED' for row in candidates),
          '405 private-source candidates retained; no automatic public/system activation.')
    check('review_bucket_and_flag_totals',
          sum(bool(row['review_flags']) for row in candidates) == stats['quarantine_review_count']
          and sum(not row['review_flags'] for row in candidates) == stats['structural_candidate_count']
          and stats['quarantine_review_count'] + stats['structural_candidate_count'] == len(candidates),
          {'structural_candidates': stats['structural_candidate_count'], 'review_needed': stats['quarantine_review_count']})
    unit_rows = [row for row in candidates if re.search(r'\d+s$', str(row['legacy_parameters']['shutter_speed']))]
    check('valid_long_exposure_units_preserved', len(unit_rows) == 10
          and all(row['normalization_proposals']['shutter_speed_without_unit']
                  == row['legacy_parameters']['shutter_speed'][:-1] for row in unit_rows),
          'Ten second-unit shutter values kept verbatim, with a separate normalization proposal.')

    fields = read_json('02_设备参数/参数字段与映射.json')['fields']
    import_data = read_json('02_设备参数/导入模板与四条示例.json')
    check('schema_and_import_columns_preserved',
          len(fields) == len({field['column'] for field in fields}) == stats['schema_field_count']
          and len(import_data['headers']) == len(set(import_data['headers'])) == stats['import_header_count']
          and all(set(sample['values']) == set(import_data['headers']) for sample in import_data['samples']),
          {'schema_fields': len(fields), 'import_columns': len(import_data['headers']), 'examples': len(import_data['samples'])})
    delta = read_json('02_设备参数/字段层级差异.json')
    check('schema_import_online_differences_visible',
          set(delta['import_headers_only_vs_schema']) == {'lighting', 'background', 'post_processing', 'prompt_template'}
          and 'ai_img2img_strength' in delta['online_non_alias_extra_vs_schema']
          and set(delta['retained_online_fields']) == retained_keys,
          'Template-only fields, missing fields and the deployed extension are explicitly retained.')
    specs = read_json('02_设备参数/源码机型规格.json')
    check('camera_spec_provenance_and_no_fake_defaults',
          len(specs['records']) == stats['camera_spec_records']
          and len({row['model'] for row in specs['records']}) == stats['camera_spec_unique_models']
          and all(row['status'] == 'REFERENCE_NOT_MANUFACTURER_VERIFIED' for row in specs['records'])
          and all(row['conditional_consistency_check']['assumed_resolution_unit'].startswith('cm') for row in specs['records']),
          {'records': len(specs['records']), 'unique_models': specs['unique_models'],
           'source_presence_differences': len(specs['differences'])})
    tag_data = read_json('02_设备参数/EXIF标签映射.json')
    check('exif_mapping_integrity', len(tag_data['assignments']) == stats['tag_assignment_count']
          and len({row['tag'] for row in tag_data['assignments']}) == stats['unique_assigned_tags']
          and {'ApertureValue', 'ShutterSpeedValue', 'MaxApertureValue'} <= {row['tag'] for row in tag_data['assignments']},
          {'assignments': len(tag_data['assignments']), 'apex_risk_tags_retained': True})

    source_changes = []
    snapshot_changes = []
    excerpt_changes = []
    for record in sources['sources']:
        source = Path(record['source'])
        if sha(source) != record['sha256']:
            source_changes.append(record['source'])
        if record.get('byte_exact'):
            if sha(OUT / record['output']) != record['sha256']:
                snapshot_changes.append(record['output'])
        elif record.get('line_start'):
            lines = source.read_text(encoding='utf-8-sig').splitlines()
            expected = '\n'.join(lines[record['line_start'] - 1:record['line_end']]).rstrip() + '\n'
            if (OUT / record['output']).read_text(encoding='utf-8') != expected:
                excerpt_changes.append(record['output'])
    check('source_fingerprints_unchanged', not source_changes,
          {'checked_sources': len(sources['sources']), 'changed': source_changes})
    check('byte_exact_source_snapshots', not snapshot_changes,
          {'files': stats['source_snapshot_files'], 'changed': snapshot_changes})
    check('source_excerpts_match_declared_lines', not excerpt_changes,
          {'files': stats['source_excerpt_files'], 'changed': excerpt_changes})
    check('online_capture_fingerprint', sha(OUT / '02_设备参数/线上预设_脱敏原始.json') == sources['online_capture_sha256'],
          sources['online_capture_sha256'])

    baselines = {
        'docs/蜜獾原图-v2-PRD-v1.0.md': '5BFCD928D215C99CE0E69480753B9805C5880F9FA2A30549ECE7B69B8C0BD460',
        'docs/蜜獾原图-v2-待决策清单-v1.0.md': 'D41D46865BA8D5CF6AFD46C62E78ECD8D918F9DB28A35654DE45FD622E7A5C3D',
        'docs/蜜獾原图-v2-项目架构-v1.0.md': '2E0AF8975E27741620B1789832F97A33804FA748424DAF13FE98B95FABF0C1DC',
        'docs/蜜獾原图-v2-生产物料清单-v1.0.md': 'D632AC97C61EAFBDD20B9E47382F94F2C38234C6B84CF7E86F20DC6CB9FCF997',
    }
    changes = [relative for relative, expected in baselines.items() if sha(V2 / relative) != expected]
    check('existing_requirement_architecture_material_baselines_unchanged', not changes,
          {'checked': len(baselines), 'changed': changes})
    missing_links = []
    deferred_links = []
    generated_reports = {(OUT / '04_提取与校验/文件指纹清单.json').resolve(),
                         (OUT / '04_提取与校验/校验结果.json').resolve()}
    links = 0
    for path in OUT.rglob('*.md'):
        for href in re.findall(r'\[[^\]]+\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
            if href.startswith(('https://', 'http://', '#')):
                continue
            links += 1
            target = (path.parent / href).resolve()
            if not target.is_file():
                if target in generated_reports:
                    deferred_links.append(target)
                else:
                    missing_links.append(str(path.relative_to(OUT)) + ':' + href)
    check('local_document_links', not missing_links, {'checked': links, 'missing': missing_links,
          'self_generated_report_links_checked_after_write': len(deferred_links)})
    table_issues = []
    for path in OUT.rglob('*.md'):
        width = 0
        for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            if line.startswith('|') and line.endswith('|'):
                columns = line.count('|') - 1
                if width and columns != width:
                    table_issues.append(str(path.relative_to(OUT)) + ':' + str(number))
                width = columns
            else:
                width = 0
    check('markdown_table_alignment', not table_issues, {'issues': table_issues})
    unapproved_files = [path.relative_to(OUT).as_posix() for path in OUT.rglob('*') if path.is_file()
                        and (path.name.startswith('.env') or path.name.endswith(('.pem', '.key')) or '.git' in path.parts)]
    check('no_credentials_or_repository_state_files_copied', not unapproved_files, {'unexpected_files': unapproved_files})
    secret_findings = []
    secret_pattern = re.compile(r'AKIA[0-9A-Z]{16}|LTAI[0-9A-Za-z]{16,}|sk-[A-Za-z0-9_-]{25,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')
    for path in OUT.rglob('*'):
        if path.is_file() and path.suffix in {'.json', '.ts', '.tsx', '.txt', '.md'}:
            if secret_pattern.search(path.read_text(encoding='utf-8')):
                secret_findings.append(path.relative_to(OUT).as_posix())
    check('common_secret_signature_scan', not secret_findings,
          {'flagged_files': secret_findings, 'scope': 'Heuristic common access-key/private-key patterns only; not a universal secret proof.'})

    excluded = {'文件指纹清单.json', '校验结果.json'}
    artifacts = [{'path': path.relative_to(OUT).as_posix(), 'bytes': path.stat().st_size, 'sha256': sha(path)}
                 for path in sorted(OUT.rglob('*')) if path.is_file() and path.name not in excluded]
    manifest = {'captured_on': DATE, 'algorithm': 'SHA-256', 'artifacts': artifacts,
                'excluded_self_referential_records': sorted(excluded),
                'additional_handoff_path': 'docs/architecture_decisions/蜜獾原图-v2-旧版复用材料提取交接-2026-10-23.md',
                'additional_handoff_sha256': sha(V2 / 'docs/architecture_decisions/蜜獾原图-v2-旧版复用材料提取交接-2026-10-23.md')}
    manifest_path = OUT / '04_提取与校验/文件指纹清单.json'
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    check('final_artifact_fingerprints', all(sha(OUT / row['path']) == row['sha256'] for row in artifacts),
          {'files': len(artifacts), 'manifest_and_result_excluded_to_avoid_self_reference': True})
    result = {'checked_on': DATE, 'status': 'PASS' if all(c['result'] == 'PASS' for c in CHECKS) else 'FAIL',
              'total': len(CHECKS), 'passed': sum(c['result'] == 'PASS' for c in CHECKS),
              'failed': sum(c['result'] == 'FAIL' for c in CHECKS), 'checks': CHECKS,
              'not_run': ['legacy_test_suite', 'manufacturer_specs', 'image_effects', 'exif_roundtrip',
                          'model_calls', 'v2_runtime_or_e2e', 'deployment'],
              'production_mutations': 'NONE'}
    (OUT / '04_提取与校验/校验结果.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    assert all(path.is_file() for path in deferred_links), 'A self-generated report was not written'
    print(json.dumps({key: result[key] for key in ('status', 'total', 'passed', 'failed')}, ensure_ascii=False))
    for failed in (c for c in CHECKS if c['result'] == 'FAIL'):
        print(json.dumps(failed, ensure_ascii=False))
    if result['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
