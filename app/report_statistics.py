"""Read-only report statistics shared by the existing admin list and exports."""
from collections import Counter, defaultdict
from .report_data import normal

LOCATION_FIELDS = ('province', 'district', 'township', 'community')
UNSPECIFIED = 'No especificada'
TRACKING_LABELS = {'pending': 'Pendientes', 'followup': 'En seguimiento',
                   'attended': 'Con atención registrada', 'unspecified': 'Estado no especificado'}
FAMILY_METHOD = ('Familias reportadas: nombre de familia, teléfono y sector coincidentes. '
                 'No existe un identificador único de familia o vivienda; no representan un censo. '
                 'Los reportes sin nombre de familia o teléfono no se cuentan como familias identificadas.')
ATTENTION_METHOD = ('Atención registrada requiere ayuda parcial o completa con fecha de confirmación. '
                    'Contactado y visitado indican seguimiento, no ayuda recibida.')
NEED_SOURCE = {
    'Agua potable': 'Agua potable', 'Alimentos': 'Alimentos',
    'Materiales para reparar la vivienda': 'Materiales para reparar viviendas',
    'Medicamentos': 'Medicamentos', 'Ropa y cobijas': 'Ropa y artículos básicos',
    'Pañales para bebés': 'Ropa y artículos básicos', 'Pañales para adultos': 'Ropa y artículos básicos',
    'Artículos de higiene': 'Artículos de higiene',
    # A mattress is not evidence of temporary accommodation. Keep the supplied category.
    'Colchones o lugar para dormir': 'Colchones o lugar para dormir',
    'Otra necesidad': 'Otras necesidades',
}
NEED_CATEGORIES = ('Agua potable', 'Alimentos', 'Materiales para reparar viviendas', 'Medicamentos',
                   'Ropa y artículos básicos', 'Artículos de higiene', 'Alojamiento temporal',
                   'Colchones o lugar para dormir', 'Otras necesidades', UNSPECIFIED)

def unique_records(records):
    return list({r['id']: r for r in records}.values())

def location(record, anonymous=False):
    d = record['data']
    return tuple(str(d.get(k) or '').strip() or UNSPECIFIED for k in LOCATION_FIELDS[:3]) + (
        'Comunidad omitida' if anonymous else str(d.get('community') or '').strip() or UNSPECIFIED,)

def family_key(record):
    d = record['data']
    if not normal(d.get('family_name')) or not normal(d.get('phone')):
        return None
    return (normal(d['family_name']), normal(d['phone']), *(normal(d.get(k)) for k in LOCATION_FIELDS))

def tracking_group(record):
    if record.get('estado_ayuda') in ('parcial', 'completa') and record.get('ayuda_actualizada_at'):
        return 'attended'
    if record.get('status') == 'pendiente':
        return 'pending'
    if record.get('status') in ('contactado', 'visitado'):
        return 'followup'
    return 'unspecified'

def recorded_needs(record):
    raw = record['data'].get('needs') or []
    if not isinstance(raw, list):
        return {UNSPECIFIED}
    categories = {NEED_SOURCE.get(n, UNSPECIFIED) if isinstance(n, str) else UNSPECIFIED for n in raw}
    # Free text is retained in the private record, never interpreted as a diagnosis/category.
    return categories or {UNSPECIFIED}

def statistics(records, anonymous=False):
    records = unique_records(records)
    families = set(); unknown_families = 0; affected_people = 0
    tracking = Counter(); operational = Counter(); help_states = Counter(); damages = Counter()
    communities = {}; need_reports = Counter(); need_families = defaultdict(set)
    need_unknown = Counter(); need_communities = {}
    for r in records:
        count = r['data'].get('total_people')
        if isinstance(count, int) and not isinstance(count, bool) and count >= 0:
            affected_people += count
        loc = location(r, anonymous); family = family_key(r); group = tracking_group(r)
        if family is None:
            unknown_families += 1
        else:
            families.add(family)
        tracking[group] += 1
        operational[r.get('status') or UNSPECIFIED] += 1
        help_states[r.get('estado_ayuda') or 'pendiente_confirmar'] += 1
        damage = str(r['data'].get('damage_type') or '').strip() or UNSPECIFIED
        if anonymous and damage not in ('Paredes','Techo','Piso','Varios daños','Otro'):
            damage = UNSPECIFIED
        damages[damage] += 1
        community = communities.setdefault(loc, {'location': dict(zip(LOCATION_FIELDS, loc)),
            'reports': 0, 'families_set': set(), 'unidentified_family_reports': 0,
            **dict.fromkeys(TRACKING_LABELS, 0), 'partial_attention': 0, 'complete_attention': 0,
            'damages': Counter(), 'needs': Counter()})
        community['reports'] += 1; community[group] += 1; community['damages'][damage] += 1
        if family is None:
            community['unidentified_family_reports'] += 1
        else:
            community['families_set'].add(family)
        if group == 'attended':
            community['partial_attention' if r['estado_ayuda'] == 'parcial' else 'complete_attention'] += 1
        for need in recorded_needs(r):
            need_reports[need] += 1; community['needs'][need] += 1
            detail = need_communities.setdefault((loc, need), {'location': dict(zip(LOCATION_FIELDS, loc)),
                'category': need, 'reports': 0, 'families_set': set(), 'unidentified_family_reports': 0})
            detail['reports'] += 1
            if family is None:
                need_unknown[need] += 1; detail['unidentified_family_reports'] += 1
            else:
                need_families[need].add(family); detail['families_set'].add(family)
    def finish(row):
        return {**{k: dict(v) if isinstance(v, Counter) else v for k, v in row.items() if k != 'families_set'},
                'family_groups': len(row['families_set'])}
    by_location = sorted((finish(r) for r in communities.values()),
                         key=lambda r: (-r['reports'], tuple(r['location'].values())))
    needs = [{'category': n, 'reports': None if n == 'Alojamiento temporal' else need_reports[n],
              'family_groups': None if n == 'Alojamiento temporal' else len(need_families[n]),
              'unidentified_family_reports': None if n == 'Alojamiento temporal' else need_unknown[n],
              'availability': UNSPECIFIED if n == 'Alojamiento temporal' else 'Categoría registrada'}
             for n in NEED_CATEGORIES]
    return {'reports': len(records), 'family_groups': len(families),
            'affected_people_reported': affected_people,
            'unidentified_family_reports': unknown_families, 'housing_count': None,
            'tracking': {k: tracking[k] for k in TRACKING_LABELS},
            'operational_states': dict(operational), 'help_states': dict(help_states),
            'communities': by_location,
            'damages': [{'type': d, 'reports': n} for d, n in sorted(damages.items(), key=lambda x: (-x[1], x[0]))],
            'needs': needs,
            'needs_by_community': [finish(v) for _, v in sorted(need_communities.items())],
            'family_method': FAMILY_METHOD, 'attention_method': ATTENTION_METHOD,
            'needs_method': ('Solo categorías elegidas en el reporte. Sin clasificación de texto libre ni '
                             'inferencia por daños. Selección múltiple: las categorías no deben sumarse como familias únicas. '
                             'Alojamiento temporal no tiene una categoría inequívoca en los registros actuales.')}
